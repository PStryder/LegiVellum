"""Load and evaluate the obligation transition model.

`schemas/transitions.v1.json` is data that ReceiptGate reads at runtime, not a
document describing what ReceiptGate does. A transition that does not appear
there is refused. That is the difference this module exists to enforce: the
project's diagnosed failure mode is specification outrunning implementation,
so the rules live in one machine-readable file that the enforcing component
actually loads.

The distinction the file encodes, and the reason it is executable:

    GOVERNANCE    changes who owes what. Requires a committed ReceiptGate
                  transition. ACCEPT additionally cannot be buffered, because
                  it is contested -- two workers may want one obligation and
                  neither can settle that locally.

    OPERATIONAL   machinery that reflects governance state. May happen locally,
                  may be lost and rebuilt, never moves custody. A lease expiring
                  is the load-bearing case: it marks an obligation OVERDUE and
                  changes the custodian not at all.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

TRANSITIONS_FILENAME = "transitions.v1.json"
TRANSITIONS_DIR_ENV = "LEGIVELLUM_TRANSITIONS_DIR"

GOVERNANCE = "GOVERNANCE"
OPERATIONAL = "OPERATIONAL"


class TransitionModelError(RuntimeError):
    """The transition model is missing or unusable."""


class IllegalTransition(Exception):
    """A proposed transition is not permitted.

    Carries the typed protocol code from the model so callers return a code
    rather than a sentence.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Transition:
    name: str
    classification: str
    phase: str
    from_states: tuple[str, ...]
    to_state: str
    bufferable: bool
    guards: tuple[str, ...]
    errors: dict[str, str]
    sets: dict[str, str]

    @property
    def is_governance(self) -> bool:
        return self.classification == GOVERNANCE


def model_path() -> Path:
    """Locate the transition model, package copy first.

    Same resolution order and same fail-closed posture as the receipt schema:
    a component that cannot find its rules is misconfigured, not permissive.
    """
    override = os.environ.get(TRANSITIONS_DIR_ENV)
    if override:
        candidate = Path(override) / TRANSITIONS_FILENAME
        if candidate.exists():
            return candidate
        raise TransitionModelError(
            f"{TRANSITIONS_DIR_ENV} is set to {override!r} but {candidate} does not exist"
        )

    packaged = Path(__file__).resolve().parent / "schemas" / TRANSITIONS_FILENAME
    if packaged.exists():
        return packaged

    raise TransitionModelError(
        f"Transition model {TRANSITIONS_FILENAME} not found at {packaged}. "
        f"Refusing to evaluate transitions without the rules that define them."
    )


@lru_cache(maxsize=1)
def load_model() -> dict[str, Any]:
    """Load and cache the raw transition model."""
    with open(model_path(), encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def _transitions() -> dict[str, Transition]:
    model = load_model()
    out: dict[str, Transition] = {}
    for entry in model["transitions"]:
        out[entry["name"]] = Transition(
            name=entry["name"],
            classification=entry["classification"],
            phase=entry["phase"],
            from_states=tuple(entry["from_states"]),
            to_state=entry["to_state"],
            bufferable=entry["bufferable"],
            guards=tuple(entry.get("guards", ())),
            errors=dict(entry.get("errors", {})),
            sets=dict(entry.get("sets", {})),
        )
    return out


def transition_names() -> tuple[str, ...]:
    return tuple(_transitions())


def get_transition(name: str) -> Transition:
    try:
        return _transitions()[name]
    except KeyError:
        raise IllegalTransition(
            "UNKNOWN_TRANSITION",
            f"{name!r} is not a transition in the model; known transitions are "
            f"{', '.join(sorted(_transitions()))}",
        ) from None


def obligation_states() -> dict[str, dict[str, Any]]:
    return dict(load_model()["obligation_states"])


def is_terminal_state(state: str) -> bool:
    states = obligation_states()
    if state not in states:
        raise TransitionModelError(f"unknown obligation state {state!r}")
    return bool(states[state]["terminal"])


def is_open_state(state: str) -> bool:
    states = obligation_states()
    if state not in states:
        raise TransitionModelError(f"unknown obligation state {state!r}")
    return bool(states[state]["open"])


def requires_notarization(name: str) -> bool:
    """Whether this transition may only become authoritative via ReceiptGate."""
    return get_transition(name).is_governance


def may_buffer(name: str) -> bool:
    """Whether a transition may sit in a durable outbox during an outage.

    False for ACCEPT and RECOVER: both are contested, and a buffered claim on a
    contested obligation is a second custodian waiting to happen.
    """
    return get_transition(name).bufferable


def transition_for_phase(phase: str, *, from_state: str) -> Transition:
    """Resolve which transition a receipt phase represents from a given state.

    `escalate` maps to two different transitions depending on the state it
    starts from -- ESCALATE from OPEN, RECOVER from OVERDUE -- which is exactly
    why this is a lookup against the model rather than a match on the phase
    string.
    """
    candidates = [
        t for t in _transitions().values()
        if t.phase == phase and from_state in t.from_states
    ]
    if not candidates:
        raise IllegalTransition(
            "TRANSITION_NOT_PERMITTED",
            f"no transition with phase {phase!r} is permitted from state {from_state!r}",
        )
    # ESCALATE and RECOVER both accept OVERDUE; ESCALATE is the ordinary act by
    # the custodian, RECOVER the reclaim by another party. Prefer the narrower
    # one whose from_states are exactly this state.
    candidates.sort(key=lambda t: len(t.from_states))
    return candidates[0]


def check_transition(
    name: str,
    *,
    current_state: str,
    actor_is_custodian: bool,
    obligation_exists: bool,
) -> None:
    """Evaluate the model's guards for a proposed transition.

    Raises IllegalTransition with the typed code the model names. This is the
    state-machine half of validation; authority and routing checks belong to
    the caller, which has the authenticated principal.
    """
    transition = get_transition(name)

    if not obligation_exists and current_state != "NONE":
        raise IllegalTransition(
            transition.errors.get("missing", "OBLIGATION_NOT_FOUND"),
            f"{name} proposed for an obligation that does not exist",
        )

    if current_state not in transition.from_states:
        if is_terminal_state(current_state):
            code = transition.errors.get("terminal", "OBLIGATION_ALREADY_TERMINATED")
            raise IllegalTransition(
                code, f"{name} is not permitted from terminal state {current_state}"
            )
        if current_state == "NONE":
            code = transition.errors.get("missing", "OBLIGATION_NOT_FOUND")
            raise IllegalTransition(
                code, f"{name} requires an existing obligation; none is committed"
            )
        code = transition.errors.get("already_custodied", "TRANSITION_NOT_PERMITTED")
        raise IllegalTransition(
            code, f"{name} is not permitted from state {current_state}"
        )

    if "actor_is_current_custodian" in transition.guards and not actor_is_custodian:
        raise IllegalTransition(
            transition.errors.get("not_custodian", "ACTOR_NOT_CUSTODIAN"),
            f"{name} may only be issued by the current custodian",
        )
