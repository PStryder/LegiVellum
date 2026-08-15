"""Load and evaluate the principal/authority model.

`schemas/authority.v1.json` answers, as data ReceiptGate executes:

    Is actor A permitted to accept obligation O?
    Is actor A the current custodian of O?
    Is actor A permitted to complete O?
    Is actor A permitted to transfer O to actor B?
    May principal P observe O?

Authority is not implemented from prose. The Exit Criteria template's
`owner_principal_id` ownership rules were written as prose, never entered the
schema, and were therefore enforced by nothing while both AsyncGate and
ReceiptGate ticked the box for implementing them.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

AUTHORITY_FILENAME = "authority.v1.json"
AUTHORITY_DIR_ENV = "LEGIVELLUM_AUTHORITY_DIR"


class AuthorityModelError(RuntimeError):
    """The authority model is missing or unusable."""


class NotPermitted(Exception):
    """An actor may not perform the proposed action."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Principal:
    """An authenticated actor.

    Constructed from a verified credential, never from request body fields.
    `id` is the principal identifier; `role` selects what it may propose;
    `visibility` is the scope it may observe within.
    """

    id: str
    role: str
    visibility: str

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("principal id must be non-empty")
        if self.id in {"NA", "TBD"}:
            raise ValueError(
                f"principal id {self.id!r} is a sentinel, not an identity; "
                f"receipts addressed to it are deliverable to nobody"
            )


def model_path() -> Path:
    """Locate the authority model, package copy first, failing closed."""
    override = os.environ.get(AUTHORITY_DIR_ENV)
    if override:
        candidate = Path(override) / AUTHORITY_FILENAME
        if candidate.exists():
            return candidate
        raise AuthorityModelError(
            f"{AUTHORITY_DIR_ENV} is set to {override!r} but {candidate} does not exist"
        )

    packaged = Path(__file__).resolve().parent / "schemas" / AUTHORITY_FILENAME
    if packaged.exists():
        return packaged

    raise AuthorityModelError(
        f"Authority model {AUTHORITY_FILENAME} not found at {packaged}. "
        f"Refusing to evaluate authority without the rules that define it."
    )


@lru_cache(maxsize=1)
def load_model() -> dict[str, Any]:
    with open(model_path(), encoding="utf-8") as handle:
        return json.load(handle)


def roles() -> dict[str, dict[str, Any]]:
    return dict(load_model()["roles"])


def identities() -> list[dict[str, Any]]:
    return list(load_model()["identities"])


def role_may_propose(role: str, transition: str) -> bool:
    defined = roles()
    if role not in defined:
        raise AuthorityModelError(
            f"unknown role {role!r}; the model defines {', '.join(sorted(defined))}"
        )
    return transition in defined[role]["may_propose"]


def check_may_propose(actor: Principal, transition: str) -> None:
    """Whether this actor's role permits proposing this transition at all.

    Role check only. Custody and state guards live in `transitions.py`; both
    must pass.
    """
    if not role_may_propose(actor.role, transition):
        raise NotPermitted(
            "ACTOR_NOT_PERMITTED",
            f"role {actor.role!r} may not propose {transition}",
        )


def check_is_custodian(actor: Principal, current_custodian: str | None) -> None:
    """Whether this actor currently holds the obligation."""
    if current_custodian is None:
        raise NotPermitted(
            "ACTOR_NOT_CUSTODIAN",
            "obligation has no current custodian; nothing to discharge",
        )
    if actor.id != current_custodian:
        raise NotPermitted(
            "ACTOR_NOT_CUSTODIAN",
            f"{actor.id!r} is not the current custodian ({current_custodian!r})",
        )


def check_may_observe(actor: Principal, visibility_principal: str) -> None:
    """Whether this actor may see an obligation and its evidence.

    The read path had no authorization at all: any holder of the single shared
    key could list any agent's inbox and read full receipt bodies.
    """
    if actor.visibility != visibility_principal:
        raise NotPermitted(
            "NOT_VISIBLE",
            f"principal {actor.id!r} (visibility {actor.visibility!r}) may not "
            f"observe an obligation scoped to {visibility_principal!r}",
        )


def bind_identity(actor: Principal, claimed: dict[str, Any]) -> None:
    """Reject caller-supplied identity that contradicts the credential.

    A component holding a shared key must not be able to assert
    "principal X completed obligation Y" by putting those strings in a body.
    Conflicting values are refused rather than silently overwritten, so a
    caller learns its claim was wrong instead of believing it was honoured.
    """
    claimed_actor = claimed.get("source_system")
    if claimed_actor and claimed_actor != actor.id:
        raise NotPermitted(
            "IDENTITY_MISMATCH",
            f"receipt claims source_system={claimed_actor!r} but the "
            f"authenticated principal is {actor.id!r}",
        )

    claimed_tenant = claimed.get("tenant_id")
    if claimed_tenant and claimed_tenant != actor.visibility:
        raise NotPermitted(
            "TENANT_MISMATCH",
            f"receipt claims tenant_id={claimed_tenant!r} but the authenticated "
            f"principal is scoped to {actor.visibility!r}",
        )
