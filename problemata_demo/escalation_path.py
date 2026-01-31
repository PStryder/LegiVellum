"""Escalation demo: force lease expiry -> escalation -> fallback completion."""

from __future__ import annotations

import sys
import time
from typing import Any

from demo_client import AsyncGateClient, DepotGateClient, ReceiptGateClient, _env, wait_for


def _build_artifact_ref(stage_result: dict[str, Any], *, mime: str) -> dict[str, Any]:
    return {
        "type": "depotgate",
        "uri": f"depotgate://{stage_result['artifact_id']}",
        "mime": mime,
        "size_bytes": stage_result.get("size_bytes", 0),
        "checksum": stage_result.get("content_hash", "NA"),
        "location": stage_result.get("location", "NA"),
    }


def _build_chain(receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not receipts:
        return []

    by_id = {r["receipt_id"]: r for r in receipts if "receipt_id" in r}
    terminal = None
    for receipt in reversed(receipts):
        if receipt.get("phase") in {"complete", "escalate"}:
            terminal = receipt
            break
    if terminal is None:
        terminal = receipts[-1]

    chain: list[dict[str, Any]] = []
    current_id = terminal.get("receipt_id")
    while current_id:
        node = by_id.get(current_id)
        if not node:
            break
        chain.append(node)
        payload = node.get("payload") or {}
        current_id = payload.get("caused_by_receipt_id")
        if not current_id or current_id == "NA":
            break
    chain.reverse()
    return chain


def _wait_for_escalation(
    receiptgate: ReceiptGateClient,
    *,
    task_id: str,
    fallback_id: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    last_receipts: list[dict[str, Any]] = []

    while time.time() < deadline:
        payload = receiptgate.list_task_receipts(task_id)
        receipts = payload.get("receipts", [])
        last_receipts = receipts
        for receipt in receipts:
            if receipt.get("phase") != "escalate":
                continue
            if receipt.get("recipient_ai") == fallback_id:
                return receipt
        time.sleep(1.0)

    raise RuntimeError(f"Escalation receipt not observed (receipts={last_receipts})")


def _wait_for_requeue(
    asyncgate: AsyncGateClient,
    *,
    worker_id: str,
    task_type: str,
    timeout_seconds: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = asyncgate.claim_lease(
            worker_id=worker_id,
            capabilities=["demo"],
            accept_types=[task_type],
            max_tasks=1,
        )
        tasks = response.get("tasks", [])
        if tasks:
            return tasks[0]
        time.sleep(1.0)
    raise RuntimeError("Fallback worker did not receive requeued task")


def main() -> int:
    asyncgate_url = _env("ASYNCGATE_URL", "http://localhost:8400")
    receiptgate_url = _env("RECEIPTGATE_URL", "http://localhost:8300")
    depotgate_url = _env("DEPOTGATE_URL", "http://localhost:8200")

    asyncgate_key = _env("ASYNCGATE_API_KEY")
    receiptgate_key = _env("RECEIPTGATE_API_KEY")
    depotgate_key = _env("DEPOTGATE_API_KEY")
    tenant_id = _env("PROBLEMATA_TENANT_ID")

    principal_id = _env("PROBLEMATA_OWNER_ID", "principal-demo")
    primary_worker = _env("PROBLEMATA_WORKER_ID", "demo-worker-1")
    fallback_worker = _env("PROBLEMATA_FALLBACK_WORKER_ID", "fallback-worker")
    task_type = _env("PROBLEMATA_TASK_TYPE", "demo.task")
    lease_ttl_seconds = int(_env("PROBLEMATA_LEASE_TTL_SECONDS", "5"))

    asyncgate = AsyncGateClient(asyncgate_url, api_key=asyncgate_key, tenant_id=tenant_id)
    receiptgate = ReceiptGateClient(receiptgate_url, api_key=receiptgate_key)
    depotgate = DepotGateClient(depotgate_url, api_key=depotgate_key)

    print("Waiting for services...")
    wait_for(asyncgate.health)
    wait_for(receiptgate.health)
    wait_for(depotgate.health)

    payload = {
        "task_summary": "Escalation demo task",
        "message": "Force escalation via lease expiry.",
        "task_type": task_type,
        "escalation_class": 1,
    }

    print("Creating task...")
    create_response = asyncgate.create_task(
        principal_id=principal_id,
        task_type=task_type,
        payload=payload,
        principal_ai=principal_id,
        expected_outcome_kind="artifact_pointer",
        expected_artifact_mime="text/plain",
    )
    task_id = str(create_response["task_id"])
    print(f"Task created: {task_id}")

    print("Primary worker claiming lease (will expire)...")
    lease_response = asyncgate.claim_lease(
        worker_id=primary_worker,
        capabilities=["demo"],
        accept_types=[task_type],
        max_tasks=1,
        lease_ttl_seconds=lease_ttl_seconds,
    )
    tasks = lease_response.get("tasks", [])
    if not tasks:
        raise RuntimeError("Primary worker failed to claim task")

    lease_id = str(tasks[0]["lease_id"])
    print(f"Lease claimed (id={lease_id}, ttl={lease_ttl_seconds}s). Waiting for expiry...")

    time.sleep(lease_ttl_seconds + 2)

    escalation_receipt = _wait_for_escalation(
        receiptgate,
        task_id=task_id,
        fallback_id=fallback_worker,
        timeout_seconds=30.0,
    )
    print(f"Escalation receipt observed for fallback: {escalation_receipt['receipt_id']}")

    print("Fallback worker claiming requeued task...")
    fallback_lease = _wait_for_requeue(
        asyncgate,
        worker_id=fallback_worker,
        task_type=task_type,
        timeout_seconds=30.0,
    )

    fallback_lease_id = str(fallback_lease["lease_id"])
    fallback_task_id = str(fallback_lease["task_id"])

    asyncgate.start_task(task_id=fallback_task_id, worker_id=fallback_worker, lease_id=fallback_lease_id)

    artifact_content = f"Fallback completed task {fallback_task_id}.\n"
    stage_result = depotgate.stage_artifact(
        root_task_id=fallback_task_id,
        content=artifact_content,
        mime_type="text/plain",
        artifact_role="final_output",
    )

    artifacts = [_build_artifact_ref(stage_result, mime="text/plain")]
    result = {
        "summary": "Fallback completion",
        "artifact_id": stage_result.get("artifact_id"),
    }

    print("Completing task via fallback...")
    asyncgate.complete_task(
        task_id=fallback_task_id,
        worker_id=fallback_worker,
        lease_id=fallback_lease_id,
        result=result,
        artifacts=artifacts,
    )

    time.sleep(1.0)

    receipts_payload = receiptgate.list_task_receipts(task_id)
    receipts = receipts_payload.get("receipts", [])
    phases = {r.get("phase") for r in receipts}
    if "escalate" not in phases or "complete" not in phases:
        raise RuntimeError(f"Expected escalate + complete receipts, saw phases={phases}")

    chain = _build_chain(receipts)
    print("Receipt chain:")
    for entry in chain:
        print(f"  - {entry.get('phase')} {entry.get('receipt_id')}")

    owner_inbox = receiptgate.list_inbox(principal_id)
    open_owner = [item for item in owner_inbox.get("receipts", []) if item.get("task_id") == task_id]
    if open_owner:
        raise RuntimeError("Owner inbox still shows open obligation")

    print("Escalation path complete. Owner inbox closed for task.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
