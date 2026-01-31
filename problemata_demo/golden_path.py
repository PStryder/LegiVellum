"""Golden path demo: submit -> accept -> complete -> verify receipts."""

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


def main() -> int:
    asyncgate_url = _env("ASYNCGATE_URL", "http://localhost:8400")
    receiptgate_url = _env("RECEIPTGATE_URL", "http://localhost:8300")
    depotgate_url = _env("DEPOTGATE_URL", "http://localhost:8200")

    asyncgate_key = _env("ASYNCGATE_API_KEY")
    receiptgate_key = _env("RECEIPTGATE_API_KEY")
    depotgate_key = _env("DEPOTGATE_API_KEY")
    tenant_id = _env("PROBLEMATA_TENANT_ID")

    principal_id = _env("PROBLEMATA_OWNER_ID", "principal-demo")
    worker_id = _env("PROBLEMATA_WORKER_ID", "demo-worker-1")
    task_type = _env("PROBLEMATA_TASK_TYPE", "demo.task")

    asyncgate = AsyncGateClient(asyncgate_url, api_key=asyncgate_key, tenant_id=tenant_id)
    receiptgate = ReceiptGateClient(receiptgate_url, api_key=receiptgate_key)
    depotgate = DepotGateClient(depotgate_url, api_key=depotgate_key)

    print("Waiting for services...")
    wait_for(asyncgate.health)
    wait_for(receiptgate.health)
    wait_for(depotgate.health)

    payload = {
        "task_summary": "Golden path demo task",
        "message": "Generate a short demo artifact.",
        "task_type": task_type,
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

    print("Claiming lease...")
    lease_response = asyncgate.claim_lease(
        worker_id=worker_id,
        capabilities=["demo"],
        accept_types=[task_type],
        max_tasks=1,
    )
    tasks = lease_response.get("tasks", [])
    if not tasks:
        raise RuntimeError("No tasks claimed; is AsyncGate running and task queued?")

    lease = tasks[0]
    lease_id = str(lease["lease_id"])
    print(f"Lease claimed: {lease_id}")

    asyncgate.start_task(task_id=task_id, worker_id=worker_id, lease_id=lease_id)

    artifact_content = f"Golden path complete for task {task_id}.\n"
    stage_result = depotgate.stage_artifact(
        root_task_id=task_id,
        content=artifact_content,
        mime_type="text/plain",
        artifact_role="final_output",
    )

    artifacts = [_build_artifact_ref(stage_result, mime="text/plain")]
    result = {
        "summary": "Golden path success",
        "artifact_id": stage_result.get("artifact_id"),
    }

    print("Completing task...")
    asyncgate.complete_task(
        task_id=task_id,
        worker_id=worker_id,
        lease_id=lease_id,
        result=result,
        artifacts=artifacts,
    )

    time.sleep(1.0)

    receipts_payload = receiptgate.list_task_receipts(task_id)
    receipts = receipts_payload.get("receipts", [])
    phases = {r.get("phase") for r in receipts}
    if "accepted" not in phases or "complete" not in phases:
        raise RuntimeError(f"Expected accepted + complete receipts, saw phases={phases}")

    chain = _build_chain(receipts)
    print("Receipt chain:")
    for entry in chain:
        print(f"  - {entry.get('phase')} {entry.get('receipt_id')}")

    inbox = receiptgate.list_inbox(principal_id)
    open_items = [item for item in inbox.get("receipts", []) if item.get("task_id") == task_id]
    if open_items:
        raise RuntimeError("Inbox still shows open obligation for task")

    print("Golden path complete. Inbox closed for task.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
