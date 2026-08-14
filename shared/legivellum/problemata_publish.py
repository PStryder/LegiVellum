"""Publish validated Problemata specs to MetaGate.

The control plane authors and validates Problemata specs; MetaGate is the
bootstrap authority components resolve their world-truth from. Nothing
connected the two, so an authored spec described a topology that nothing could
boot into, and the demo stack seeded MetaGate with raw SQL instead.

This is the control-plane half of that link. It does not decide whether a spec
is valid -- ProblemataControlService already did that -- it carries the spec
and its validation attestation across, and MetaGate refuses anything without a
passing attestation.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Optional

from .problemata_control import ProblemataRecord, ProblemataStatus


class ProblemataPublishError(RuntimeError):
    """Raised when MetaGate refuses or cannot be reached."""


class MetaGatePublisher:
    """Minimal MCP client for `metagate.instantiate_problemata`."""

    def __init__(
        self,
        endpoint: str,
        *,
        api_key: Optional[str] = None,
        bearer_token: Optional[str] = None,
        api_key_header: str = "X-API-Key",
        timeout_seconds: float = 30.0,
    ) -> None:
        """MetaGate accepts either an issued API key or a JWT.

        `metagate.admin_principals` issues keys of the form `mgk_...`, sent in
        the X-API-Key header; JWTs go in Authorization: Bearer. Which one a
        deployment uses is a deployment decision, so support both rather than
        assuming.
        """
        self._endpoint = endpoint.rstrip("/")
        self._api_key = api_key
        self._bearer_token = bearer_token
        self._api_key_header = api_key_header
        self._timeout = timeout_seconds

    def _mcp_call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
        url = self._endpoint if self._endpoint.endswith("/mcp") else f"{self._endpoint}/mcp"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        if self._api_key:
            request.add_header(self._api_key_header, self._api_key)
        if self._bearer_token:
            request.add_header("Authorization", f"Bearer {self._bearer_token}")
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                body = json.load(response)
        except urllib.error.HTTPError as exc:
            raise ProblemataPublishError(f"MetaGate returned HTTP {exc.code}: {exc.reason}") from exc
        except (urllib.error.URLError, OSError) as exc:
            raise ProblemataPublishError(f"MetaGate unreachable at {url}: {exc}") from exc

        if "error" in body:
            raise ProblemataPublishError(f"MetaGate rejected {tool}: {body['error']}")
        result = body.get("result")
        if result is None:
            raise ProblemataPublishError(f"MetaGate returned no result for {tool}: {body}")
        return result

    def publish_record(
        self,
        record: ProblemataRecord,
        *,
        deployment_key: str = "default",
        tenant_key: Optional[str] = None,
        auth_subject: Optional[str] = None,
    ) -> dict[str, Any]:
        """Materialize a registered Problemata as MetaGate world-truth.

        Refuses locally rather than letting MetaGate reject the call, so the
        failure names the actual problem: an unvalidated spec is a control-plane
        state error, not a transport one.
        """
        if record.status is not ProblemataStatus.VALIDATED:
            raise ProblemataPublishError(
                f"Problemata '{record.problemata_id}' is {record.status.value}; "
                "only validated specs may be published to MetaGate."
            )

        arguments: dict[str, Any] = {
            "spec": record.spec,
            "validation": record.validation.model_dump(mode="json"),
            "deployment_key": deployment_key,
        }
        if tenant_key:
            arguments["tenant_key"] = tenant_key
        if auth_subject:
            arguments["auth_subject"] = auth_subject

        return self._mcp_call("metagate.instantiate_problemata", arguments)
