"""Shared HTTP helpers for problemata demo scripts."""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


class HttpClient:
    def __init__(self, base_url: str, api_key: str | None = None, headers: dict[str, str] | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.headers: dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
        if headers:
            self.headers.update(headers)

    def request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        timeout: float = 10.0,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        if query:
            query = {k: v for k, v in query.items() if v is not None}
            if query:
                url = f"{url}?{urlencode(query)}"

        data = None
        if payload is not None:
            data = json.dumps(payload, default=str).encode("utf-8")

        req = Request(url, data=data, method=method)
        for key, value in self.headers.items():
            req.add_header(key, value)

        try:
            with urlopen(req, timeout=timeout) as response:
                raw = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{method} {url} failed: {exc.code} {exc.reason}: {detail}") from None

        if not raw:
            return {}

        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"{method} {url} returned invalid JSON: {exc}") from None


class AsyncGateClient:
    def __init__(self, base_url: str, api_key: str | None = None, tenant_id: str | None = None) -> None:
        self._tenant_id = tenant_id or "00000000-0000-0000-0000-000000000000"
        self._http = HttpClient(base_url, api_key=api_key)

    def _mcp_call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
        response = self._http.request_json("POST", "/mcp", payload)
        if "error" in response:
            raise RuntimeError(f"AsyncGate MCP error: {response['error']}")
        result = response.get("result")
        if result is None:
            raise RuntimeError(f"AsyncGate MCP returned no result: {response}")
        return result

    def health(self) -> dict[str, Any]:
        return self._mcp_call("asyncgate.health", {})

    def create_task(
        self,
        *,
        principal_id: str,
        principal_kind: str = "agent",
        task_type: str = "demo.task",
        payload: dict[str, Any] | None = None,
        payload_pointer: str | None = None,
        principal_ai: str | None = None,
        expected_outcome_kind: str | None = None,
        expected_artifact_mime: str | None = None,
    ) -> dict[str, Any]:
        body = {
            "type": task_type,
            "payload": payload or {},
            "payload_pointer": payload_pointer,
            "principal_ai": principal_ai or principal_id,
            "expected_outcome_kind": expected_outcome_kind,
            "expected_artifact_mime": expected_artifact_mime,
            "agent_id": principal_id,
            "tenant_id": self._tenant_id,
        }
        return self._mcp_call("asyncgate.create_task", body)

    def claim_lease(
        self,
        *,
        worker_id: str,
        capabilities: list[str] | None = None,
        accept_types: list[str] | None = None,
        max_tasks: int = 1,
        lease_ttl_seconds: int | None = None,
    ) -> dict[str, Any]:
        body = {
            "worker_id": worker_id,
            "capabilities": capabilities or [],
            "accept_types": accept_types,
            "max_tasks": max_tasks,
            "lease_ttl_seconds": lease_ttl_seconds,
            "tenant_id": self._tenant_id,
        }
        return self._mcp_call("asyncgate.lease_next", body)

    def start_task(self, *, task_id: str, worker_id: str, lease_id: str) -> dict[str, Any]:
        body = {
            "worker_id": worker_id,
            "task_id": task_id,
            "lease_id": lease_id,
            "progress": {"state": "running"},
            "tenant_id": self._tenant_id,
        }
        return self._mcp_call("asyncgate.report_progress", body)

    def complete_task(
        self,
        *,
        task_id: str,
        worker_id: str,
        lease_id: str,
        result: dict[str, Any],
        artifacts: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        body = {
            "worker_id": worker_id,
            "task_id": task_id,
            "lease_id": lease_id,
            "result": result,
            "artifacts": artifacts,
            "tenant_id": self._tenant_id,
        }
        return self._mcp_call("asyncgate.complete", body)

    def get_task(self, task_id: str) -> dict[str, Any]:
        return self._mcp_call("asyncgate.get_task", {"task_id": task_id, "tenant_id": self._tenant_id})


class DepotGateClient:
    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self._http = HttpClient(base_url, api_key=api_key)

    def health(self) -> dict[str, Any]:
        return self._mcp_call("depotgate.health", {})

    def _mcp_call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
        response = self._http.request_json("POST", "/mcp", payload)
        if "error" in response:
            raise RuntimeError(f"DepotGate MCP error: {response['error']}")
        result = response.get("result")
        if result is None:
            raise RuntimeError(f"DepotGate MCP returned no result: {response}")
        return result

    def stage_artifact(
        self,
        *,
        root_task_id: str,
        content: str,
        mime_type: str = "text/plain",
        artifact_role: str = "final_output",
    ) -> dict[str, Any]:
        content_base64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "stage_artifact",
                "arguments": {
                    "root_task_id": root_task_id,
                    "content_base64": content_base64,
                    "mime_type": mime_type,
                    "artifact_role": artifact_role,
                },
            },
        }
        return self._mcp_call("stage_artifact", payload["params"]["arguments"])


class ReceiptGateClient:
    def __init__(self, base_url: str, api_key: str | None = None) -> None:
        self._http = HttpClient(base_url, api_key=api_key)

    def health(self) -> dict[str, Any]:
        return self._mcp_call("receiptgate.health", {})

    def _mcp_call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
        response = self._http.request_json("POST", "/mcp", payload)
        if "error" in response:
            raise RuntimeError(f"ReceiptGate MCP error: {response['error']}")
        result = response.get("result")
        if result is None:
            raise RuntimeError(f"ReceiptGate MCP returned no result: {response}")
        return result

    def list_inbox(self, recipient_ai: str, limit: int = 50) -> dict[str, Any]:
        return self._mcp_call("receiptgate.list_inbox", {"recipient_ai": recipient_ai, "limit": limit})

    def list_task_receipts(self, task_id: str, include_payload: bool = True) -> dict[str, Any]:
        return self._mcp_call(
            "receiptgate.list_task_receipts",
            {"task_id": task_id, "sort": "asc", "include_payload": include_payload},
        )

    def search_receipts(
        self,
        *,
        root_task_id: str,
        phase: str | None = None,
        recipient_ai: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        arguments = {"root_task_id": root_task_id, "limit": limit}
        if phase:
            arguments["phase"] = phase
        if recipient_ai:
            arguments["recipient_ai"] = recipient_ai
        return self._mcp_call("receiptgate.search_receipts", arguments)


def wait_for(predicate, *, timeout_seconds: float = 30.0, interval_seconds: float = 2.0) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None

    while time.time() < deadline:
        try:
            predicate()
            return
        except Exception as exc:
            last_error = exc
            time.sleep(interval_seconds)

    raise RuntimeError(f"Timed out waiting for service: {last_error}")
