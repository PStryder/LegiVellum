#!/usr/bin/env python3
"""Observation path: run a task, then answer "what happened?" through InterView.

golden_path.py proves work gets done and receipted. This proves the result is
legible afterwards without reading logs or querying each primitive directly --
the claim LEGIVELLUM_STORY.md leads with.

Everything here goes through InterView, which is read-only by contract: it
reads the ReceiptGate ledger, polls AsyncGate, and lists DepotGate artifacts,
but never writes. The task itself is created through AsyncGate exactly as in
golden_path.py, so the observation is of real work, not a fixture.

Usage:
    python observe_path.py                 # run a task, then observe it
    python observe_path.py --task-id UUID  # observe an existing task
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any

from demo_client import (
    AsyncGateClient,
    DepotGateClient,
    InterViewClient,
    wait_for,
)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    return default if value is None or value == "" else value


def _run_task(asyncgate: AsyncGateClient, depotgate: DepotGateClient, *,
              principal_id: str, worker_id: str, task_type: str) -> str:
    """Drive one task to completion so there is something to observe."""
    print("Running a task to observe...")
    created = asyncgate.create_task(
        principal_id=principal_id,
        task_type=task_type,
        payload={"task_summary": "Observation path demo task", "task_type": task_type},
        principal_ai=principal_id,
        expected_outcome_kind="artifact_pointer",
        expected_artifact_mime="text/plain",
    )
    task_id = str(created["task_id"])

    lease = asyncgate.claim_lease(
        worker_id=worker_id, capabilities=["demo"], accept_types=[task_type], max_tasks=1
    )
    tasks = lease.get("tasks", [])
    if not tasks:
        raise RuntimeError("No tasks claimed; is AsyncGate running?")
    lease_id = str(tasks[0]["lease_id"])

    asyncgate.start_task(task_id=task_id, worker_id=worker_id, lease_id=lease_id)
    staged = depotgate.stage_artifact(
        root_task_id=task_id,
        content=f"Observation path artifact for task {task_id}.\n",
        mime_type="text/plain",
        artifact_role="final_output",
    )
    asyncgate.complete_task(
        task_id=task_id,
        worker_id=worker_id,
        lease_id=lease_id,
        result={"summary": "Observation path success", "artifact_id": staged.get("artifact_id")},
        artifacts=[{
            "type": "depotgate",
            "uri": f"depotgate://{staged['artifact_id']}",
            "mime": "text/plain",
            "size_bytes": staged.get("size_bytes", 0),
            "checksum": staged.get("content_hash", "NA"),
            "location": staged.get("location", "NA"),
        }],
    )
    print(f"Task complete: {task_id}\n")
    return task_id


def _report(interview: InterViewClient, tenant_id: str, task_id: str) -> dict[str, Any]:
    """Print the operator-facing 'what happened' view, all via InterView."""
    status = interview.status(tenant_id, task_id)["status"]
    receipts = interview.search_receipts(tenant_id, task_id).get("receipts", [])
    artifacts = interview.artifacts(tenant_id, task_id).get("artifact_pointers", [])

    print(f"What happened to task {task_id}?\n")
    print(f"  state                 : {status.get('state')}")
    print(f"  open obligations      : {status.get('open_obligations_count')}")
    print(f"  latest receipt        : {status.get('latest_receipt_id')}")
    print(f"  last updated          : {status.get('last_updated_at')}")

    print("\n  custody chain:")
    for receipt in sorted(receipts, key=lambda r: r.get("created_at") or ""):
        print(f"    {receipt.get('phase'):9} {receipt.get('receipt_id')}"
              f"  -> {receipt.get('recipient_ai')}")

    print("\n  artifacts produced:")
    if not artifacts:
        print("    (none)")
    for artifact in artifacts:
        print(f"    {artifact.get('artifact_role'):14} {artifact.get('artifact_id')}"
              f"  {artifact.get('mime_type')}  {artifact.get('size_bytes')} bytes")

    return {"status": status, "receipts": receipts, "artifacts": artifacts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-id", default=None, help="observe an existing task instead")
    args = parser.parse_args()

    tenant_id = _env("PROBLEMATA_TENANT_ID", "default")
    principal_id = _env("PROBLEMATA_OWNER_ID", "principal-demo")
    worker_id = _env("PROBLEMATA_WORKER_ID", "observe-worker-1")
    task_type = _env("PROBLEMATA_TASK_TYPE", "demo.task")

    asyncgate = AsyncGateClient(_env("ASYNCGATE_URL", "http://localhost:8400"),
                                api_key=_env("ASYNCGATE_API_KEY"))
    depotgate = DepotGateClient(_env("DEPOTGATE_URL", "http://localhost:8200"),
                                api_key=_env("DEPOTGATE_API_KEY"))
    interview = InterViewClient(_env("INTERVIEW_URL", "http://localhost:8600"),
                                api_key=_env("INTERVIEW_API_KEY"))

    print("Waiting for services...")
    wait_for(asyncgate.health)
    wait_for(depotgate.health)
    wait_for(interview.health)

    task_id = args.task_id or _run_task(
        asyncgate, depotgate,
        principal_id=principal_id, worker_id=worker_id, task_type=task_type,
    )

    # ReceiptGate stores asynchronously relative to complete_task returning.
    time.sleep(1.0)
    observed = _report(interview, tenant_id, task_id)

    status, receipts, artifacts = (
        observed["status"], observed["receipts"], observed["artifacts"],
    )
    phases = {r.get("phase") for r in receipts}

    if status.get("state") != "resolved":
        raise RuntimeError(f"Expected resolved state, saw {status.get('state')!r}")
    if status.get("open_obligations_count") != 0:
        raise RuntimeError(f"Expected no open obligations, saw {status.get('open_obligations_count')}")
    if not {"accepted", "complete"} <= phases:
        raise RuntimeError(f"Expected accepted + complete in chain, saw {phases}")
    if not artifacts:
        raise RuntimeError("Expected at least one artifact pointer from DepotGate")

    print("\nObservation path complete: custody chain and artifacts readable via InterView.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - demo script surfaces the reason
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
