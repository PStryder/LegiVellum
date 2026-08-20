"""The constitution is data, and the data has to be right.

Phase 1 requires tests for the transition model itself, not only for code that
reads it. These assert the properties Slice Zero depends on:

- every governance transition is notarized, and the contested ones cannot be
  buffered
- reaching a deadline is not a transition
- terminal states are terminal
- the error codes the model promises actually exist

A transition table that is internally inconsistent is worse than none, because
ReceiptGate will enforce it confidently.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from legivellum import authority, transitions
from legivellum.authority import NotPermitted, Principal
from legivellum.transitions import GOVERNANCE, OPERATIONAL, IllegalTransition

MODEL = transitions.load_model()

# Every state the model calls terminal. Derived so these guards follow the
# constitution instead of a hand-maintained copy of it.
TERMINAL_STATES = sorted(
    name for name, spec in MODEL["obligation_states"].items() if spec.get("terminal")
)


class TestModelShape:
    def test_model_loads_from_the_package(self):
        assert transitions.model_path().exists()
        assert MODEL["version"] == "1.0"

    def test_missing_model_fails_closed(self, monkeypatch):
        monkeypatch.setenv(transitions.TRANSITIONS_DIR_ENV, "/nonexistent")
        with pytest.raises(transitions.TransitionModelError):
            transitions.model_path()

    def test_every_transition_is_classified(self):
        for entry in MODEL["transitions"]:
            assert entry["classification"] in {GOVERNANCE, OPERATIONAL}, entry["name"]

    def test_every_transition_targets_a_defined_state(self):
        states = set(MODEL["obligation_states"])
        for entry in MODEL["transitions"]:
            assert entry["to_state"] in states, entry["name"]
            for src in entry["from_states"]:
                assert src in states, f"{entry['name']} from {src}"

    def test_error_codes_are_declared_for_every_guard_failure(self):
        """A guard with no code produces an untyped rejection."""
        for entry in MODEL["transitions"]:
            assert entry.get("errors"), f"{entry['name']} declares no error codes"


class TestGovernanceClassification:
    def test_all_four_transitions_are_governance(self):
        """Nothing that moves custody may be classified operational."""
        for name in transitions.transition_names():
            assert transitions.requires_notarization(name), name

    def test_accept_cannot_be_buffered(self):
        """The load-bearing rule for Phase 3A.

        Acceptance is contested: two workers may want one obligation and
        neither can settle it locally. A buffered acceptance is a second
        custodian waiting to happen.
        """
        assert transitions.may_buffer("ACCEPT") is False

    def test_recover_cannot_be_buffered(self):
        """Recovery is contested for the same reason acceptance is."""
        assert transitions.may_buffer("RECOVER") is False

    def test_terminal_transitions_may_buffer(self):
        """Only the established custodian may issue them, so there is no race.

        Bufferable does not mean authoritative -- that is asserted where the
        outbox is implemented.
        """
        assert transitions.may_buffer("COMPLETE") is True
        assert transitions.may_buffer("ESCALATE") is True

    def test_no_operational_event_changes_custody(self):
        for event in MODEL["operational_events"]:
            assert event["changes_custody"] is False, event["name"]
            assert event["classification"] == OPERATIONAL, event["name"]


class TestDeadlineIsNotATransition:
    """Wall-clock passage must not perform a governance transition."""

    def test_lease_expiry_is_operational(self):
        expiry = next(
            e for e in MODEL["operational_events"] if e["name"] == "LEASE_EXPIRED"
        )
        assert expiry["classification"] == OPERATIONAL
        assert expiry["changes_custody"] is False
        assert expiry["marks_overdue"] is True

    def test_overdue_is_open_and_not_terminal(self):
        """An overdue obligation is still owed by the same custodian."""
        assert transitions.is_open_state("OVERDUE")
        assert not transitions.is_terminal_state("OVERDUE")

    def test_accept_is_not_permitted_from_overdue(self):
        """Another worker cannot take an expired obligation without recovery."""
        with pytest.raises(IllegalTransition):
            transitions.check_transition(
                "ACCEPT",
                current_state="OVERDUE",
                actor_is_custodian=False,
                obligation_exists=True,
            )

    def test_recovery_is_the_only_way_out_of_overdue_for_a_third_party(self):
        recover = transitions.get_transition("RECOVER")
        assert recover.from_states == ("OVERDUE",)
        assert transitions.requires_notarization("RECOVER")


class TestStateGuards:
    def test_complete_requires_an_existing_obligation(self):
        with pytest.raises(IllegalTransition) as exc:
            transitions.check_transition(
                "COMPLETE",
                current_state="NONE",
                actor_is_custodian=True,
                obligation_exists=False,
            )
        assert exc.value.code == "COMPLETE_WITHOUT_ACCEPT"

    def test_escalate_requires_an_existing_obligation(self):
        with pytest.raises(IllegalTransition) as exc:
            transitions.check_transition(
                "ESCALATE",
                current_state="NONE",
                actor_is_custodian=True,
                obligation_exists=False,
            )
        assert exc.value.code == "ESCALATE_WITHOUT_ACCEPT"

    @pytest.mark.parametrize("terminal", TERMINAL_STATES)
    @pytest.mark.parametrize("name", ["COMPLETE", "ESCALATE"])
    def test_terminal_obligations_cannot_be_closed_again(self, name, terminal):
        with pytest.raises(IllegalTransition) as exc:
            transitions.check_transition(
                name,
                current_state=terminal,
                actor_is_custodian=True,
                obligation_exists=True,
            )
        assert exc.value.code == "OBLIGATION_ALREADY_TERMINATED"

    @pytest.mark.parametrize("terminal", TERMINAL_STATES)
    def test_terminal_obligations_cannot_be_accepted(self, terminal):
        """An accepted receipt after termination used to store and vanish."""
        with pytest.raises(IllegalTransition) as exc:
            transitions.check_transition(
                "ACCEPT",
                current_state=terminal,
                actor_is_custodian=False,
                obligation_exists=True,
            )
        assert exc.value.code == "OBLIGATION_ALREADY_TERMINATED"

    def test_non_custodian_cannot_complete(self):
        with pytest.raises(IllegalTransition) as exc:
            transitions.check_transition(
                "COMPLETE",
                current_state="OPEN",
                actor_is_custodian=False,
                obligation_exists=True,
            )
        assert exc.value.code == "ACTOR_NOT_CUSTODIAN"

    def test_custodian_may_complete_an_open_obligation(self):
        transitions.check_transition(
            "COMPLETE",
            current_state="OPEN",
            actor_is_custodian=True,
            obligation_exists=True,
        )

    def test_accept_is_permitted_only_from_none(self):
        transitions.check_transition(
            "ACCEPT", current_state="NONE", actor_is_custodian=False, obligation_exists=False
        )
        with pytest.raises(IllegalTransition):
            transitions.check_transition(
                "ACCEPT", current_state="OPEN", actor_is_custodian=False, obligation_exists=True
            )


class TestPhaseResolution:
    def test_escalate_from_open_is_a_transfer(self):
        assert transitions.transition_for_phase("escalate", from_state="OPEN").name == "ESCALATE"

    def test_escalate_from_overdue_resolves_to_recover(self):
        """Same phase, different transition, decided by state not by string."""
        assert transitions.transition_for_phase("escalate", from_state="OVERDUE").name == "RECOVER"

    def test_a_phase_illegal_from_this_state_still_resolves(self):
        """Resolution answers "which transition is this", not "is it legal".

        Legality is the guard's job, and separating them is what lets the
        rejection carry the documented code -- COMPLETE_WITHOUT_ACCEPT rather
        than a generic TRANSITION_NOT_PERMITTED for every illegal move.
        """
        assert transitions.transition_for_phase("complete", from_state="CLOSED").name == "COMPLETE"
        with pytest.raises(IllegalTransition) as exc:
            transitions.check_transition(
                "COMPLETE",
                current_state="CLOSED",
                actor_is_custodian=True,
                obligation_exists=True,
            )
        assert exc.value.code == "OBLIGATION_ALREADY_TERMINATED"

    def test_a_phase_no_transition_declares_is_refused(self):
        with pytest.raises(IllegalTransition):
            transitions.transition_for_phase("cancel", from_state="OPEN")


class TestAuthorityModel:
    def test_model_loads_and_fails_closed(self, monkeypatch):
        assert authority.model_path().exists()
        monkeypatch.setenv(authority.AUTHORITY_DIR_ENV, "/nonexistent")
        with pytest.raises(authority.AuthorityModelError):
            authority.model_path()

    def test_all_six_identities_are_defined(self):
        roles = {i["role"] for i in authority.identities()}
        assert roles == {
            "authorizer_principal",
            "beneficiary_principal",
            "visibility_principal",
            "current_custodian",
            "transition_actor",
            "service_emitter",
        }

    def test_every_identity_declares_where_it_is_derived_from(self):
        """Otherwise the projection cannot be rebuilt from the ledger."""
        for identity in authority.identities():
            assert identity["derived_from"], identity["role"]
            assert identity["storage"], identity["role"]

    def test_observer_may_propose_nothing(self):
        observer = Principal(id="agent:auditor", role="observer", visibility="default")
        for name in transitions.transition_names():
            with pytest.raises(NotPermitted):
                authority.check_may_propose(observer, name)

    def test_worker_may_propose_terminal_transitions(self):
        worker = Principal(id="worker:1", role="worker", visibility="default")
        authority.check_may_propose(worker, "COMPLETE")
        authority.check_may_propose(worker, "ESCALATE")

    def test_non_custodian_is_refused(self):
        actor = Principal(id="worker:2", role="worker", visibility="default")
        with pytest.raises(NotPermitted) as exc:
            authority.check_is_custodian(actor, "worker:1")
        assert exc.value.code == "ACTOR_NOT_CUSTODIAN"

    def test_uncustodied_obligation_cannot_be_discharged(self):
        actor = Principal(id="worker:1", role="worker", visibility="default")
        with pytest.raises(NotPermitted):
            authority.check_is_custodian(actor, None)

    def test_visibility_is_enforced_on_reads(self):
        actor = Principal(id="agent:a", role="worker", visibility="tenant-a")
        authority.check_may_observe(actor, "tenant-a")
        with pytest.raises(NotPermitted) as exc:
            authority.check_may_observe(actor, "tenant-b")
        assert exc.value.code == "NOT_VISIBLE"

    def test_claimed_identity_that_contradicts_the_credential_is_refused(self):
        """A shared key must not let one component speak as another."""
        actor = Principal(id="svc:cognigate", role="service", visibility="default")
        with pytest.raises(NotPermitted) as exc:
            authority.bind_identity(actor, {"source_system": "delegate"})
        assert exc.value.code == "IDENTITY_MISMATCH"

    def test_claimed_tenant_that_contradicts_the_credential_is_refused(self):
        actor = Principal(id="svc:a", role="service", visibility="tenant-a")
        with pytest.raises(NotPermitted) as exc:
            authority.bind_identity(actor, {"tenant_id": "tenant-b"})
        assert exc.value.code == "TENANT_MISMATCH"

    def test_sentinel_principal_ids_are_rejected(self):
        """recipient_ai: 'NA' addresses an inbox nobody polls."""
        for sentinel in ("NA", "TBD"):
            with pytest.raises(ValueError):
                Principal(id=sentinel, role="worker", visibility="default")


class TestInvariantsAreDeclared:
    """The invariants list is what later phases are held to."""

    def test_declared_invariants_cover_the_slice_zero_thesis(self):
        ids = {i["id"] for i in MODEL["invariants"]}
        assert {
            "one-custodian",
            "receipts-immutable",
            "atomic-append-and-project",
            "projection-rebuildable",
            "deadline-is-not-a-transition",
            "obligation-scoped-termination",
        } <= ids

    def test_every_invariant_names_a_mechanism_from_the_vocabulary(self):
        """An invariant with no enforcement mechanism is prose.

        `mechanism` is a closed enum declared in the same file, so this is a
        machine-checkable claim rather than a test grepping a sentence for
        hopeful keywords -- which is what this assertion was first written as,
        and it passed for the wrong reasons.
        """
        vocabulary = set(MODEL["enforcement_mechanisms"])
        for invariant in MODEL["invariants"]:
            assert invariant["enforced_by"], invariant["id"]
            assert invariant["mechanism"] in vocabulary, (
                f"{invariant['id']} declares mechanism {invariant.get('mechanism')!r}, "
                f"which is not one of {sorted(vocabulary)}"
            )

    def test_the_contested_invariants_use_structural_enforcement(self):
        """Uniqueness and atomicity may not rest on application logic.

        'check current state, then write if empty' is the pattern the brief
        forbids for custody exclusion, so these two must name a database
        mechanism rather than a code convention.
        """
        by_id = {i["id"]: i for i in MODEL["invariants"]}
        assert by_id["one-custodian"]["mechanism"] == "db_constraint"
        assert by_id["atomic-append-and-project"]["mechanism"] == "single_transaction"


class TestEveryDeclaredStateCanOccur:
    """A state the model declares but nothing can reach is a decorative claim.

    `TRANSFERRED` was exactly that: declared here, permitted by two CHECK
    constraints in ReceiptGate's 006_obligations.sql, targeted by no transition,
    reachable by no operational event, and written by no code. It survived the
    decision that custody transfer keeps an obligation OPEN under a new
    custodian -- responsibility moves, it does not end -- which is what made it
    unreachable.

    The risk is not the unused row. It is that a reader of the constitution, or
    of the CHECK constraint, reasonably concludes the system can express
    "transferred away and no longer mine" when it cannot.
    """

    def _reachable(self) -> set[str]:
        reachable = {"NONE"}  # the absence of an obligation, not a stored value
        for transition in MODEL["transitions"]:
            reachable.add(transition["to_state"])
        for event in MODEL.get("operational_events", []):
            if event.get("marks_overdue"):
                reachable.add("OVERDUE")
        return reachable

    def test_every_declared_state_is_reachable(self):
        declared = set(MODEL["obligation_states"])
        unreachable = declared - self._reachable()
        assert not unreachable, (
            f"{sorted(unreachable)} declared but reachable by no transition and "
            "no operational event. Either something must be able to reach it or "
            "it must not be declared."
        )

    def test_overdue_is_reached_by_an_event_not_a_transition(self):
        """OVERDUE is the one state a deadline produces rather than a proposal.

        It is reachable, so the test above passes, but it must stay reachable
        the *right* way: if some transition started targeting OVERDUE, a
        deadline would have become a self-executing transition, which is the
        thing the custody model refuses.
        """
        assert "OVERDUE" in MODEL["obligation_states"]
        assert not [t for t in MODEL["transitions"] if t["to_state"] == "OVERDUE"]
        assert [e for e in MODEL["operational_events"] if e.get("marks_overdue")]

    def test_receiptgate_state_constraint_matches_the_declared_states(self):
        """The CHECK constraint and the constitution must permit the same set.

        They are two expressions of one rule, in different languages, and only
        one of them is loaded by the code that evaluates transitions.
        """
        schema = (
            Path(__file__).resolve().parents[2]
            / "ReceiptGate" / "schema" / "006_obligations.sql"
        )
        if not schema.exists():
            pytest.skip("ReceiptGate checkout not present")

        import re

        text = schema.read_text(encoding="utf-8")
        match = re.search(r"CHECK \(state IN \(([^)]*)\)\)", text)
        assert match, "no state CHECK constraint found in 006_obligations.sql"
        constrained = set(re.findall(r"'([A-Z]+)'", match.group(1)))

        # NONE is the absence of a row, so it is never a stored value.
        declared = set(MODEL["obligation_states"]) - {"NONE"}
        assert constrained == declared, (
            f"CHECK permits {sorted(constrained)} but the model declares "
            f"{sorted(declared)}"
        )
