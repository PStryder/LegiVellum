"""Tests for publishing validated Problemata specs to MetaGate."""

from __future__ import annotations

import json
from typing import Any

import pytest

from legivellum.problemata_control import (
    InMemoryProblemataRepository,
    ProblemataBlueprint,
    ProblemataControlService,
    ProblemataStatus,
)
from legivellum.problemata_publish import MetaGatePublisher, ProblemataPublishError


def _record():
    service = ProblemataControlService(repository=InMemoryProblemataRepository())
    blueprint = ProblemataBlueprint(
        problemata_id="demo-curation",
        tenant_id="default",
        owner_principal="principal-demo",
        description="demo problemata",
    )
    return service.create_from_blueprint(blueprint)


class _FakePublisher(MetaGatePublisher):
    """Captures the MCP call instead of performing it."""

    def __init__(self, result: dict[str, Any] | None = None) -> None:
        super().__init__("http://metagate.invalid")
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._result = result if result is not None else {"manifest_key": "problemata:x:0.1.0:manifest"}

    def _mcp_call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((tool, arguments))
        return self._result


def test_publishes_spec_and_attestation_together() -> None:
    record = _record()
    publisher = _FakePublisher()
    publisher.publish_record(record, deployment_key="local")

    tool, arguments = publisher.calls[0]
    assert tool == "metagate.instantiate_problemata"
    assert arguments["spec"] == record.spec
    assert arguments["validation"]["status"] == "passed"
    assert arguments["deployment_key"] == "local"


def test_attestation_is_json_serializable() -> None:
    """It crosses an MCP boundary, so datetimes must already be encoded."""
    record = _record()
    publisher = _FakePublisher()
    publisher.publish_record(record)
    json.dumps(publisher.calls[0][1])


def test_optional_arguments_omitted_when_unset() -> None:
    record = _record()
    publisher = _FakePublisher()
    publisher.publish_record(record)
    arguments = publisher.calls[0][1]
    assert "tenant_key" not in arguments
    assert "auth_subject" not in arguments


def test_optional_arguments_passed_when_set() -> None:
    record = _record()
    publisher = _FakePublisher()
    publisher.publish_record(record, tenant_key="acme", auth_subject="svc:demo")
    arguments = publisher.calls[0][1]
    assert arguments["tenant_key"] == "acme"
    assert arguments["auth_subject"] == "svc:demo"


def test_unvalidated_record_refused_locally() -> None:
    """A rejected spec is a control-plane state error, not a transport failure."""
    record = _record().model_copy(update={"status": ProblemataStatus.REJECTED})
    publisher = _FakePublisher()
    with pytest.raises(ProblemataPublishError, match="only validated specs"):
        publisher.publish_record(record)
    assert publisher.calls == []


def test_metagate_error_surfaces_as_publish_error() -> None:
    class _Rejecting(MetaGatePublisher):
        def _mcp_call(self, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
            raise ProblemataPublishError("MetaGate rejected: PROBLEMATA_UNVALIDATED")

    with pytest.raises(ProblemataPublishError):
        _Rejecting("http://metagate.invalid").publish_record(_record())


def test_endpoint_normalization() -> None:
    """Callers pass a base URL or a full /mcp path; both must work."""
    for endpoint in ("http://metagate:8000", "http://metagate:8000/", "http://metagate:8000/mcp"):
        publisher = MetaGatePublisher(endpoint)
        resolved = publisher._endpoint
        url = resolved if resolved.endswith("/mcp") else f"{resolved}/mcp"
        assert url == "http://metagate:8000/mcp"
