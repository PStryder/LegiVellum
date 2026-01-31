#!/usr/bin/env python
"""Minimal worker: bootstrap -> accept -> execute -> complete."""

import base64
import json
import os
import uuid
from datetime import datetime, timezone
from urllib import error, request


def _now():
    return datetime.now(timezone.utc).isoformat()


def _normalize(endpoint: str) -> str:
    endpoint = (endpoint or "").rstrip("/")
    return f"{endpoint}/mcp" if endpoint and not endpoint.endswith("/mcp") else endpoint


def _mcp_call(endpoint: str, api_key: str, tool: str, arguments: dict) -> dict:
    payload = {"jsonrpc": "2.0", "id": str(uuid.uuid4()), "method": "tools/call", "params": {"name": tool, "arguments": arguments}}
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    req = request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}: {exc.read().decode('utf-8')}") from exc
    if "error" in data:
        raise RuntimeError(f"MCP error: {data['error']}")
    return data.get("result", {})


def _service_endpoint(packet: dict, key: str) -> str:
    services = packet.get("services", {}) if isinstance(packet, dict) else {}
    entry = services.get(key) or services.get(key.lower()) or {}
    if isinstance(entry, dict):
        return entry.get("endpoint") or entry.get("mcp_endpoint") or entry.get("url") or ""
    return ""


def _build_receipt(*, task_id, tenant_id, principal_ai, recipient_ai, phase, status, started_at, completed_at, artifact, outcome_text):
    artifact = artifact or {}
    artifact_id = artifact.get("artifact_id")
    pointer = f"depotgate://artifact/{artifact_id}" if artifact_id else "NA"
    base = dict(
        schema_version="1.0", tenant_id=tenant_id, receipt_id=str(uuid.uuid4()), task_id=task_id,
        parent_task_id="NA", caused_by_receipt_id="NA", dedupe_key=f"demo:{task_id}:{phase}", attempt=0,
        from_principal=principal_ai, for_principal=principal_ai, source_system="worker.minimal", recipient_ai=recipient_ai,
        trust_domain="local", phase=phase, status=status, realtime=False, task_type="demo",
        task_summary="minimal worker demo", task_body="Demonstrate bootstrap -> accept -> complete", inputs={},
        expected_outcome_kind="artifact_pointer", expected_artifact_mime="application/json", outcome_text=outcome_text,
        escalation_class="NA", escalation_reason="NA", escalation_to="NA", retry_requested=False,
        created_at=_now(), stored_at=_now(), started_at=started_at, completed_at=completed_at, read_at=None, archived_at=None,
        metadata={"worker_id": recipient_ai},
    )
    if phase == "accepted":
        base.update(outcome_kind="NA", artifact_location="NA", artifact_pointer="NA", artifact_checksum="NA", artifact_size_bytes=0, artifact_mime="NA")
    else:
        base.update(
            outcome_kind="artifact_pointer", artifact_location=artifact.get("location", "NA"), artifact_pointer=pointer,
            artifact_checksum=artifact.get("content_hash", "NA"), artifact_size_bytes=artifact.get("size_bytes", 0), artifact_mime="application/json",
        )
    return base


def main() -> int:
    metagate_endpoint = _normalize(os.environ.get("METAGATE_ENDPOINT", ""))
    metagate_key = os.environ.get("METAGATE_API_KEY", "")
    if not metagate_endpoint:
        raise RuntimeError("METAGATE_ENDPOINT is required")

    component_key = os.environ.get("WORKER_COMPONENT_KEY", "worker_minimal")
    bootstrap = _mcp_call(metagate_endpoint, metagate_key, "metagate.bootstrap", {"component_key": component_key})
    packet = bootstrap.get("packet", bootstrap)

    receipt_endpoint = _normalize(os.environ.get("RECEIPTGATE_ENDPOINT") or _service_endpoint(packet, "receiptgate"))
    depot_endpoint = _normalize(os.environ.get("DEPOTGATE_ENDPOINT") or _service_endpoint(packet, "depotgate"))
    if not receipt_endpoint or not depot_endpoint:
        raise RuntimeError("ReceiptGate and DepotGate endpoints required")

    receipt_key = os.environ.get("RECEIPTGATE_API_KEY", "")
    depot_key = os.environ.get("DEPOTGATE_API_KEY", "")
    task_id = os.environ.get("TASK_ID", "task-demo-001")
    tenant_id = os.environ.get("TENANT_ID", "default")
    principal_ai = os.environ.get("PRINCIPAL_AI", "principal.demo")
    worker_id = os.environ.get("WORKER_ID", "worker.minimal")

    started_at = _now()
    accepted = _build_receipt(task_id=task_id, tenant_id=tenant_id, principal_ai=principal_ai, recipient_ai=worker_id,
        phase="accepted", status="NA", started_at=started_at, completed_at=None, artifact=None, outcome_text="NA")
    _mcp_call(receipt_endpoint, receipt_key, "receiptgate.submit_receipt", {"receipt": accepted})

    payload = json.dumps({"task_id": task_id, "result": "hello from minimal worker"}).encode("utf-8")
    artifact = _mcp_call(depot_endpoint, depot_key, "stage_artifact", {"root_task_id": task_id,
        "content_base64": base64.b64encode(payload).decode("utf-8"), "mime_type": "application/json", "artifact_role": "final_output"})

    complete = _build_receipt(task_id=task_id, tenant_id=tenant_id, principal_ai=principal_ai, recipient_ai=principal_ai,
        phase="complete", status="success", started_at=started_at, completed_at=_now(), artifact=artifact, outcome_text="artifact staged")
    _mcp_call(receipt_endpoint, receipt_key, "receiptgate.submit_receipt", {"receipt": complete})

    print(json.dumps({"accepted": accepted["receipt_id"], "complete": complete["receipt_id"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
