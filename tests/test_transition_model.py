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

    @pytest.mark.parametrize("terminal", ["CLOSED", "TRANSFERRED"])
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

    @pytest.mark.parametrize("terminal", ["CLOSED", "TRANSFERRED"])
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

    def test_unknown_phase_from_state_is_refused(self):
        with pytest.raises(IllegalTransition):
            transitions.transition_for_phase("complete", from_state="CLOSED")


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
