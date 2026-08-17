#!/usr/bin/env python3
"""Adversarially probe the invariants the architecture claims to enforce.

The other demo paths show the stack working when used correctly. This one tries
to break it: every probe below sends something the canonical specs say MUST be
refused, and passes only if the stack refuses it.

That distinction matters. A golden path proves the happy case; it says nothing
about whether the rules are enforced or merely documented. `docs/canonical/
receipt.rules.md` is written in RFC 2119 MUSTs, and an unenforced MUST is a
comment.

Probes are grouped by the claim they defend:

  Receipt protocol   phase-specific field rules (receipt.rules.md sections 1-3)
  Routing            recipient_ai == escalation_to on escalate
  Immutability       same receipt_id with different content is a conflict
  Authority          MetaGate is describe-only and admission requires attestation

A probe that *fails* means the stack accepted something it should have refused,
which is a real finding rather than a flaky test.

Usage:
    python invariant_probe.py            # requires the stack to be running
    METAGATE_API_KEY=mgk_... python invariant_probe.py   # includes MetaGate probes
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Callable


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return default if value is None or value == "" else value


RECEIPTGATE_URL = _env("RECEIPTGATE_URL", "http://localhost:8300")
METAGATE_URL = _env("METAGATE_URL", "http://localhost:8100")
METAGATE_API_KEY = _env("METAGATE_API_KEY")

# The tenant the probe's receipts claim. It must be the one ReceiptGate's
# principal is scoped to, or every submission is refused TENANT_MISMATCH before
# the invariant under test is ever reached -- and a probe that only ever sees
# refusals passes its "this must be refused" cases for the wrong reason.
# Matches PROBLEMATA_ASYNCGATE_TENANT in docker-compose.yml.
TENANT_ID = _env("PROBLEMATA_ASYNCGATE_TENANT", "00000000-0000-0000-0000-000000000000")


class ProbeFailure(Exception):
    """Raised when the stack accepted something it should have refused."""


def _mcp(base_url: str, tool: str, arguments: dict[str, Any], api_key: str | None = None) -> dict[str, Any]:
    """Call an MCP tool, returning the full JSON-RPC envelope (errors included)."""
    endpoint = base_url if base_url.endswith("/mcp") else f"{base_url.rstrip('/')}/mcp"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
             "params": {"name": tool, "arguments": arguments}}
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    if api_key:
        request.add_header("X-API-Key", api_key)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        # A transport-level rejection is still a refusal.
        return {"error": {"code": exc.code, "message": exc.read().decode("utf-8", "replace")[:200]}}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _receipt(**overrides: Any) -> dict[str, Any]:
    """A well-formed accepted receipt, before a probe corrupts one field."""
    task_id = overrides.pop("_task_id", f"probe-{uuid.uuid4()}")
    base = {
        "schema_version": "1.0",
        "tenant_id": TENANT_ID,
        "receipt_id": str(uuid.uuid4()),
        "task_id": task_id,
        # Derived from the task rather than random, so the accept/complete pairs
        # these probes build address the same obligation. A fresh id per receipt
        # would make every completion target an obligation that was never
        # opened, and the probe would "pass" on a refusal that had nothing to do
        # with the invariant under test.
        "obligation_id": f"obl-{task_id}",
        "parent_task_id": "NA",
        "caused_by_receipt_id": "NA",
        "dedupe_key": "NA",
        "attempt": 0,
        "from_principal": "principal:probe",
        "for_principal": "principal:probe",
        "source_system": "invariant-probe",
        "recipient_ai": "agent:probe",
        "trust_domain": "probe",
        "phase": "accepted",
        "status": "NA",
        "realtime": False,
        "task_type": "probe.task",
        "task_summary": "Invariant probe",
        "task_body": "Deliberately malformed receipt used to test enforcement.",
        "inputs": {},
        "expected_outcome_kind": "response_text",
        "expected_artifact_mime": "NA",
        "outcome_kind": "NA",
        "outcome_text": "NA",
        "artifact_location": "NA",
        "artifact_pointer": "NA",
        "artifact_checksum": "NA",
        "artifact_size_bytes": 0,
        "artifact_mime": "NA",
        "escalation_class": "NA",
        "escalation_reason": "NA",
        "escalation_to": "NA",
        "retry_requested": False,
        "body": {},
        "created_at": _now(),
        "stored_at": None,
        "started_at": _now(),
        "completed_at": None,
        "read_at": None,
        "archived_at": None,
        "metadata": {},
    }
    base.update(overrides)
    return base


def _complete(**overrides: Any) -> dict[str, Any]:
    defaults = {
        "phase": "complete",
        "status": "success",
        "outcome_kind": "response_text",
        "outcome_text": "done",
        "completed_at": _now(),
        "body": {"result": {"summary": "done"}},
    }
    defaults.update(overrides)
    return _receipt(**defaults)


def _escalate(**overrides: Any) -> dict[str, Any]:
    defaults = {
        "phase": "escalate",
        "status": "NA",
        "escalation_class": "capability",
        "escalation_reason": "Probe escalation",
        "escalation_to": "agent:probe-target",
        "recipient_ai": "agent:probe-target",
        "body": {"escalation": {"to": "agent:probe-target", "reason": "Probe escalation"}},
    }
    defaults.update(overrides)
    return _receipt(**defaults)


def _submit(receipt: dict[str, Any]) -> dict[str, Any]:
    return _mcp(RECEIPTGATE_URL, "receiptgate.submit_receipt", {"receipt": receipt})


def _must_refuse(what: str, response: dict[str, Any]) -> None:
    if "error" not in response:
        raise ProbeFailure(f"{what}: accepted, but the spec says it MUST be refused")


def _must_accept(what: str, response: dict[str, Any]) -> None:
    if "error" in response:
        raise ProbeFailure(f"{what}: refused, but this is legal — {response['error']}")


# --- receipt protocol: accepted ---------------------------------------------

def probe_accepted_rejects_terminal_status() -> None:
    """accepted opens an obligation; a status would claim it also closed it."""
    _must_refuse("accepted with status=success", _submit(_receipt(status="success")))


def probe_accepted_rejects_completed_at() -> None:
    _must_refuse("accepted with completed_at set", _submit(_receipt(completed_at=_now())))


def probe_accepted_rejects_placeholder_summary() -> None:
    """A receipt whose summary is TBD explains nothing to a future reader."""
    _must_refuse("accepted with task_summary=TBD", _submit(_receipt(task_summary="TBD")))


def probe_accepted_rejects_artifact_fields() -> None:
    """Nothing has been produced yet, so claiming an artifact is a lie."""
    _must_refuse(
        "accepted with artifact_pointer set",
        _submit(_receipt(artifact_pointer="depotgate://not-real", artifact_mime="text/plain")),
    )


def probe_accepted_rejects_escalation_fields() -> None:
    _must_refuse(
        "accepted with escalation_to set",
        _submit(_receipt(escalation_to="agent:elsewhere", escalation_class="owner")),
    )


# --- receipt protocol: complete ---------------------------------------------

def probe_complete_rejects_na_status() -> None:
    """A completion must say how it ended."""
    _must_refuse("complete with status=NA", _submit(_complete(status="NA")))


def probe_complete_rejects_missing_completed_at() -> None:
    _must_refuse("complete without completed_at", _submit(_complete(completed_at=None)))


def probe_complete_rejects_unknown_outcome_kind() -> None:
    _must_refuse("complete with invalid outcome_kind", _submit(_complete(outcome_kind="telepathy")))


def probe_complete_rejects_artifact_claim_without_pointer() -> None:
    """outcome_kind=artifact_pointer with no pointer is an unlocatable claim."""
    _must_refuse(
        "complete claiming an artifact with pointer=NA",
        _submit(_complete(outcome_kind="artifact_pointer")),
    )


def probe_complete_rejects_escalation_class() -> None:
    """Completing and escalating are different terminal acts."""
    _must_refuse(
        "complete with escalation_class set",
        _submit(_complete(escalation_class="capability")),
    )


# --- routing invariant ------------------------------------------------------

def probe_escalate_enforces_routing_invariant() -> None:
    """recipient_ai MUST equal escalation_to.

    If they differ, the ledger says responsibility moved to one party while the
    inbox delivers it to another -- the obligation is owed by nobody.
    """
    _must_refuse(
        "escalate with recipient_ai != escalation_to",
        _submit(_escalate(recipient_ai="agent:someone-else")),
    )


def probe_escalate_rejects_unknown_class() -> None:
    _must_refuse("escalate with invalid escalation_class", _submit(_escalate(escalation_class="vibes")))


def probe_escalate_rejects_placeholder_reason() -> None:
    _must_refuse("escalate with reason=TBD", _submit(_escalate(escalation_reason="TBD")))


def probe_escalate_rejects_missing_target() -> None:
    _must_refuse(
        "escalate with escalation_to=NA",
        _submit(_escalate(escalation_to="NA", recipient_ai="NA")),
    )


def probe_escalate_accepts_valid_routing() -> None:
    """The positive control: a correct escalation must still be accepted.

    Without this, every probe above would pass if the ledger simply refused
    everything.

    The escalation has to follow an acceptance. Escalating transfers custody of
    an obligation, so there must be an obligation to transfer: a bare escalate
    is refused ESCALATE_WITHOUT_ACCEPT, which is the ledger behaving correctly
    and would leave this control unable to distinguish that from a ledger that
    refuses everything.
    """
    task_id = f"probe-{uuid.uuid4()}"
    _must_accept("opening acceptance", _submit(_receipt(_task_id=task_id)))
    _must_accept("well-formed escalate", _submit(_escalate(_task_id=task_id)))


# --- immutability -----------------------------------------------------------

def probe_receipt_id_reuse_with_different_content_conflicts() -> None:
    """Receipts are append-only: no retroactive truth.

    Re-using a receipt_id with different content is an attempt to rewrite
    history and must be refused rather than silently overwriting.
    """
    original = _receipt()
    _must_accept("first submission", _submit(original))

    mutated = dict(original)
    mutated["task_summary"] = "Rewritten after the fact"
    _must_refuse("same receipt_id with different content", _submit(mutated))


def probe_identical_resubmission_is_idempotent() -> None:
    """Retries are safe: the same receipt submitted twice is not an error."""
    receipt = _receipt()
    _must_accept("first submission", _submit(receipt))
    response = _submit(receipt)
    _must_accept("identical resubmission", response)
    if not response.get("result", {}).get("idempotent_replay"):
        raise ProbeFailure("identical resubmission was accepted but not marked as a replay")


# --- authority boundaries ---------------------------------------------------

def probe_metagate_refuses_orchestration_keys() -> None:
    """MetaGate is describe-only.

    A Problemata carrying deploy/execute/tasks is trying to make the bootstrap
    authority an orchestrator.
    """
    if not METAGATE_API_KEY:
        raise RuntimeError("skip")
    spec = {
        "problemata": {"id": "probe-forbidden", "version": "0.1.0", "owner_principal": "principal:probe"},
        "primitives": {"receiptgate-main": {"type": "receiptgate", "endpoint": "http://receiptgate:8000/mcp"}},
        "deploy": {"replicas": 3},
    }
    _must_refuse(
        "instantiate_problemata carrying a deploy key",
        _mcp(METAGATE_URL, "metagate.instantiate_problemata",
             {"spec": spec, "validation": {"status": "passed"}}, METAGATE_API_KEY),
    )


def probe_metagate_requires_validation_attestation() -> None:
    """MetaGate does not validate specs, but must refuse unattested ones."""
    if not METAGATE_API_KEY:
        raise RuntimeError("skip")
    spec = {
        "problemata": {"id": "probe-unvalidated", "version": "0.1.0", "owner_principal": "principal:probe"},
        "primitives": {"receiptgate-main": {"type": "receiptgate", "endpoint": "http://receiptgate:8000/mcp"}},
    }
    _must_refuse(
        "instantiate_problemata without a passing attestation",
        _mcp(METAGATE_URL, "metagate.instantiate_problemata",
             {"spec": spec, "validation": {"status": "failed"}}, METAGATE_API_KEY),
    )


def probe_metagate_admin_requires_authentication() -> None:
    """Minting identity is privileged."""
    _must_refuse(
        "admin_api_keys without credentials",
        _mcp(METAGATE_URL, "metagate.admin_api_keys", {"action": "list"}),
    )


PROBES: list[tuple[str, Callable[[], None]]] = [
    ("accepted rejects terminal status", probe_accepted_rejects_terminal_status),
    ("accepted rejects completed_at", probe_accepted_rejects_completed_at),
    ("accepted rejects placeholder summary", probe_accepted_rejects_placeholder_summary),
    ("accepted rejects artifact fields", probe_accepted_rejects_artifact_fields),
    ("accepted rejects escalation fields", probe_accepted_rejects_escalation_fields),
    ("complete rejects NA status", probe_complete_rejects_na_status),
    ("complete rejects missing completed_at", probe_complete_rejects_missing_completed_at),
    ("complete rejects unknown outcome_kind", probe_complete_rejects_unknown_outcome_kind),
    ("complete rejects artifact claim without pointer", probe_complete_rejects_artifact_claim_without_pointer),
    ("complete rejects escalation_class", probe_complete_rejects_escalation_class),
    ("escalate enforces routing invariant", probe_escalate_enforces_routing_invariant),
    ("escalate rejects unknown class", probe_escalate_rejects_unknown_class),
    ("escalate rejects placeholder reason", probe_escalate_rejects_placeholder_reason),
    ("escalate rejects missing target", probe_escalate_rejects_missing_target),
    ("escalate accepts valid routing (control)", probe_escalate_accepts_valid_routing),
    ("receipt_id reuse with different content conflicts", probe_receipt_id_reuse_with_different_content_conflicts),
    ("identical resubmission is idempotent", probe_identical_resubmission_is_idempotent),
    ("metagate refuses orchestration keys", probe_metagate_refuses_orchestration_keys),
    ("metagate requires validation attestation", probe_metagate_requires_validation_attestation),
    ("metagate admin requires authentication", probe_metagate_admin_requires_authentication),
]


def main() -> int:
    print(f"Probing invariants against {RECEIPTGATE_URL} and {METAGATE_URL}\n")
    held, broken, skipped = [], [], []

    for name, probe in PROBES:
        try:
            probe()
        except ProbeFailure as exc:
            broken.append((name, str(exc)))
            print(f"  BROKEN  {name}\n            {exc}")
        except RuntimeError as exc:
            if str(exc) == "skip":
                skipped.append(name)
                print(f"  skipped {name} (needs METAGATE_API_KEY)")
                continue
            broken.append((name, str(exc)))
            print(f"  ERROR   {name}: {exc}")
        else:
            held.append(name)
            print(f"  held    {name}")

    print(f"\n{len(held)} invariants held, {len(broken)} broken, {len(skipped)} skipped")
    if broken:
        print("\nThe stack accepted something the canonical specs say MUST be refused:")
        for name, detail in broken:
            print(f"  - {name}: {detail}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
