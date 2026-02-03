"""Integration tests for minimal LegiVellum problemata."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from sqlalchemy import text


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _receipt_payload(
    *,
    receipt_id: str,
    task_id: str,
    phase: str,
    status: str,
    recipient_ai: str,
    caused_by_receipt_id: str = "NA",
    escalation_class: str = "NA",
    escalation_reason: str = "NA",
    escalation_to: str = "NA",
    outcome_kind: str = "NA",
    outcome_text: str = "NA",
    artifact_pointer: str = "NA",
    artifact_location: str = "NA",
    artifact_mime: str = "NA",
    completed_at: str | None = None,
):
    return {
        "schema_version": "1.0",
        "receipt_id": receipt_id,
        "task_id": task_id,
        "parent_task_id": "NA",
        "caused_by_receipt_id": caused_by_receipt_id,
        "dedupe_key": "NA",
        "attempt": 0,
        "from_principal": "principal.alice",
        "for_principal": "principal.alice",
        "source_system": "test",
        "recipient_ai": recipient_ai,
        "trust_domain": "default",
        "phase": phase,
        "status": status,
        "realtime": False,
        "task_type": "test.task",
        "task_summary": "integration test",
        "task_body": "integration test",
        "inputs": {},
        "expected_outcome_kind": "NA",
        "expected_artifact_mime": "NA",
        "outcome_kind": outcome_kind,
        "outcome_text": outcome_text,
        "artifact_location": artifact_location,
        "artifact_pointer": artifact_pointer,
        "artifact_checksum": "NA",
        "artifact_size_bytes": 0,
        "artifact_mime": artifact_mime,
        "escalation_class": escalation_class,
        "escalation_reason": escalation_reason,
        "escalation_to": escalation_to,
        "retry_requested": False,
        "created_at": _now(),
        "started_at": None,
        "completed_at": completed_at,
        "metadata": {},
    }


@pytest.mark.asyncio
@pytest.mark.integration
async def test_task_submission_accept_complete_inbox_closed(asyncgate_mcp, memorygate_mcp):
    payload = {
        "task_type": "demo",
        "task_summary": "integration task",
        "task_body": "demo",
        "inputs": {"value": 1},
        "recipient_ai": "worker.alice",
        "from_principal": "principal.alice",
        "for_principal": "principal.alice",
        "expected_outcome_kind": "none",
        "expected_artifact_mime": "NA",
    }

    response = await asyncgate_mcp.queue_task(**payload)
    task_id = response["task_id"]

    inbox = await memorygate_mcp.memory_get_inbox(recipient_ai="worker.alice")
    assert inbox["count"] == 1

    lease = await asyncgate_mcp.lease_task(
        worker_id="worker.alice",
        capabilities=[],
        preferred_kinds=[],
    )
    assert lease["status"] == "leased"
    lease_id = lease["lease_id"]

    complete = await asyncgate_mcp.complete_task(
        lease_id=lease_id,
        worker_id="worker.alice",
        status="success",
        outcome_kind="none",
        outcome_text="done",
    )
    assert complete["status"] == "success"

    timeline = await memorygate_mcp.memory_get_task_timeline(task_id)
    receipts = timeline["receipts"]
    accepted = next(r for r in receipts if r["phase"] == "accepted")

    archive = await memorygate_mcp.memory_archive_receipt(accepted["receipt_id"])
    assert archive["status"] == "archived"

    inbox_after = await memorygate_mcp.memory_get_inbox(recipient_ai="worker.alice")
    assert inbox_after["count"] == 0


@pytest.mark.asyncio
@pytest.mark.integration
async def test_idempotency_duplicate_receipt_rejected(memorygate_mcp):
    receipt_id = "01JGTESTDUPLICATE00000000001"
    task_id = "T-dup-001"
    payload = _receipt_payload(
        receipt_id=receipt_id,
        task_id=task_id,
        phase="accepted",
        status="NA",
        recipient_ai="worker.alice",
    )

    first = await memorygate_mcp.memory_submit_receipt(payload)
    assert "error" not in first

    second = await memorygate_mcp.memory_submit_receipt(payload)
    assert second["error"] == "duplicate_receipt_id"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_provenance_chain_traversal(memorygate_mcp):
    root_id = "01JGCHAINROOT00000000000001"
    mid_id = "01JGCHAINMID00000000000001"
    leaf_id = "01JGCHAINLEAF00000000000001"
    task_id = "T-chain-001"

    root = _receipt_payload(
        receipt_id=root_id,
        task_id=task_id,
        phase="accepted",
        status="NA",
        recipient_ai="worker.alice",
    )
    mid = _receipt_payload(
        receipt_id=mid_id,
        task_id=task_id,
        phase="escalate",
        status="NA",
        recipient_ai="delegate",
        caused_by_receipt_id=root_id,
        escalation_class="policy",
        escalation_reason="lease_expired",
        escalation_to="delegate",
        outcome_kind="NA",
        outcome_text="NA",
    )
    leaf = _receipt_payload(
        receipt_id=leaf_id,
        task_id=task_id,
        phase="complete",
        status="success",
        recipient_ai="principal.alice",
        caused_by_receipt_id=mid_id,
        outcome_kind="none",
        outcome_text="done",
        completed_at=_now(),
    )

    for payload in (root, mid, leaf):
        resp = await memorygate_mcp.memory_submit_receipt(payload)
        assert "error" not in resp

    chain = await memorygate_mcp.memory_get_receipt_chain(root_id)
    chain_ids = [r["receipt_id"] for r in chain["chain"]]
    assert chain_ids[0] == root_id
    assert set(chain_ids) == {root_id, mid_id, leaf_id}


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.xfail(reason="Single-tenant v1; multi-tenant isolation deferred", strict=True)
async def test_multi_tenant_isolation(memorygate_mcp):
    alice_receipt = _receipt_payload(
        receipt_id="01JGALICE0000000000000001",
        task_id="T-alice-001",
        phase="accepted",
        status="NA",
        recipient_ai="worker.alice",
    )
    bob_receipt = _receipt_payload(
        receipt_id="01JGBOB00000000000000001",
        task_id="T-bob-001",
        phase="accepted",
        status="NA",
        recipient_ai="worker.bob",
    )

    resp_a = await memorygate_mcp.memory_submit_receipt(alice_receipt)
    resp_b = await memorygate_mcp.memory_submit_receipt(bob_receipt)
    assert "error" not in resp_a
    assert "error" not in resp_b

    inbox_alice = await memorygate_mcp.memory_get_inbox(recipient_ai="worker.alice")
    assert inbox_alice["count"] == 1

    inbox_bob = await memorygate_mcp.memory_get_inbox(recipient_ai="worker.alice")
    assert inbox_bob["count"] == 0

    unauthorized = await memorygate_mcp.memory_get_receipt(alice_receipt["receipt_id"])
    assert unauthorized["error"] == "not_found"


@pytest.mark.asyncio
@pytest.mark.integration
async def test_concurrent_workers_claim_different_tasks(asyncgate_mcp):
    for idx in range(2):
        payload = {
            "task_type": "demo",
            "task_summary": f"task-{idx}",
            "task_body": "demo",
            "inputs": {"idx": idx},
            "recipient_ai": "worker.alice",
            "from_principal": "principal.alice",
            "for_principal": "principal.alice",
            "expected_outcome_kind": "none",
            "expected_artifact_mime": "NA",
        }
        resp = await asyncgate_mcp.queue_task(**payload)
        assert resp["status"] == "queued"

    async def lease(worker_id: str):
        return await asyncgate_mcp.lease_task(
            worker_id=worker_id,
            capabilities=[],
            preferred_kinds=[],
        )

    lease_one, lease_two = await asyncio.gather(lease("worker.a"), lease("worker.b"))
    assert lease_one["status"] == "leased"
    assert lease_two["status"] == "leased"
    assert lease_one["task"]["task_id"] != lease_two["task"]["task_id"]


@pytest.mark.asyncio
@pytest.mark.integration
async def test_worker_crash_second_worker_picks_up(asyncgate_mcp, integration_session):
    payload = {
        "task_type": "demo",
        "task_summary": "crash-task",
        "task_body": "demo",
        "inputs": {},
        "recipient_ai": "worker.alice",
        "from_principal": "principal.alice",
        "for_principal": "principal.alice",
        "expected_outcome_kind": "none",
        "expected_artifact_mime": "NA",
    }

    created = await asyncgate_mcp.queue_task(**payload)
    task_id = created["task_id"]

    lease = await asyncgate_mcp.lease_task(
        worker_id="worker.alice",
        capabilities=[],
        preferred_kinds=[],
    )
    assert lease["status"] == "leased"

    await integration_session.execute(
        text(
            "UPDATE tasks SET lease_expires_at = NOW() - interval '1 minute' "
            "WHERE task_id = :task_id AND tenant_id = :tenant_id"
        ),
        {"task_id": task_id, "tenant_id": "alice"},
    )
    await integration_session.commit()

    expired = await asyncgate_mcp.expire_leases()
    assert expired["expired"] == 1

    new_lease = await asyncgate_mcp.lease_task(
        worker_id="worker.bob",
        capabilities=[],
        preferred_kinds=[],
    )
    assert new_lease["status"] == "leased"
    assert new_lease["task"]["task_id"] == task_id


@pytest.mark.asyncio
@pytest.mark.integration
async def test_lease_expiry_emits_escalation(asyncgate_mcp, memorygate_mcp, integration_session):
    payload = {
        "task_type": "demo",
        "task_summary": "expire-task",
        "task_body": "demo",
        "inputs": {},
        "recipient_ai": "worker.alice",
        "from_principal": "principal.alice",
        "for_principal": "principal.alice",
        "expected_outcome_kind": "none",
        "expected_artifact_mime": "NA",
    }

    created = await asyncgate_mcp.queue_task(**payload)
    task_id = created["task_id"]

    lease = await asyncgate_mcp.lease_task(
        worker_id="worker.alice",
        capabilities=[],
        preferred_kinds=[],
    )
    assert lease["status"] == "leased"

    await integration_session.execute(
        text(
            "UPDATE tasks SET lease_expires_at = NOW() - interval '1 minute', attempt = 2, max_attempts = 3 "
            "WHERE task_id = :task_id AND tenant_id = :tenant_id"
        ),
        {"task_id": task_id, "tenant_id": "alice"},
    )
    await integration_session.commit()

    expired = await asyncgate_mcp.expire_leases()
    assert expired["expired"] == 1

    timeline = await memorygate_mcp.memory_get_task_timeline(task_id)
    receipts = timeline["receipts"]
    phases = {r["phase"] for r in receipts}
    assert "escalate" in phases
