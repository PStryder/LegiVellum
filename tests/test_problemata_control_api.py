"""API tests for Problemata control UI service."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from legivellum.problemata_control import InMemoryProblemataRepository, ProblemataControlService
from legivellum.problemata_control_ui import create_app


@pytest.fixture(autouse=True)
def cleanup_database():
    """Override global DB cleanup fixture for this pure-unit module."""
    yield


@pytest.fixture
def client() -> TestClient:
    service = ProblemataControlService(repository=InMemoryProblemataRepository())
    app = create_app(service=service)
    return TestClient(app)


def _blueprint_payload(problemata_id: str = "prob-ui") -> dict:
    return {
        "problemata_id": problemata_id,
        "version": "0.1.0",
        "tenant_id": "tenant-ui",
        "owner_principal": "agent.ui",
        "description": "UI-driven Problemata",
        "endpoint_base": "http://localhost",
        "trust_domain": "default",
        "include_asyncgate": True,
        "include_cognigate": False,
        "include_delegategate": False,
        "include_interrogate": True,
        "include_interview": False,
        "include_memorygate": True,
        "receipt_schema_version": "1.0",
        "depot_default_sink": "filesystem",
        "cgn_model": "anthropic/claude-3-opus",
        "dlg_model": "gpt-4.1",
        "interrogate_policy_profile_id": "default-policy",
        "async_lease_ttl_seconds": 300,
        "async_max_attempts": 3,
        "async_retry_backoff_seconds": 15,
    }


def test_health_endpoint(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "problemata-control-ui"
    assert payload["storage_backend"] == "memory"
    assert payload["total_problemata"] == 0


def test_preview_then_validate_passes(client: TestClient):
    preview = client.post("/api/problemata/preview", json=_blueprint_payload(problemata_id="prob-preview"))
    assert preview.status_code == 200
    spec = preview.json()
    assert spec["problemata"]["id"] == "prob-preview"

    validate = client.post("/api/problemata/validate", json={"spec": spec})
    assert validate.status_code == 200
    result = validate.json()
    assert result["status"] == "passed"
    assert result["errors"] == []


def test_validate_invalid_spec_returns_failed(client: TestClient):
    invalid_spec = {
        "problemata": {
            "id": "prob-invalid",
            "version": "0.1.0",
            "tenant_id": "tenant-invalid",
            "owner_principal": "agent.invalid",
        },
        "primitives": {},
        "topology": [],
    }
    response = client.post("/api/problemata/validate", json={"spec": invalid_spec})
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "failed"
    assert len(result["errors"]) > 0


def test_create_from_blueprint_then_get_and_list(client: TestClient):
    create = client.post("/api/problemata/from-blueprint", json=_blueprint_payload(problemata_id="prob-created"))
    assert create.status_code == 201
    record = create.json()
    assert record["problemata_id"] == "prob-created"
    assert record["status"] == "validated"

    list_response = client.get("/api/problemata")
    assert list_response.status_code == 200
    records = list_response.json()
    assert len(records) == 1
    assert records[0]["problemata_id"] == "prob-created"

    get_response = client.get("/api/problemata/prob-created")
    assert get_response.status_code == 200
    assert get_response.json()["problemata_id"] == "prob-created"


def test_get_missing_problemata_returns_404(client: TestClient):
    response = client.get("/api/problemata/does-not-exist")
    assert response.status_code == 404


def test_health_requires_auth_when_mode_strict(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LEGIVELLUM_AUTH_MODE", "strict")
    service = ProblemataControlService(repository=InMemoryProblemataRepository())
    strict_client = TestClient(create_app(service=service))

    unauthorized = strict_client.get("/api/health")
    assert unauthorized.status_code == 401

    authorized = strict_client.get("/api/health", headers={"X-API-Key": "dev-key-pstryder"})
    assert authorized.status_code == 200


def test_update_existing_problemata_roundtrip(client: TestClient):
    create = client.post("/api/problemata/from-blueprint", json=_blueprint_payload(problemata_id="prob-edit"))
    assert create.status_code == 201

    record = create.json()
    spec = record["spec"]
    spec["problemata"]["description"] = "Updated from UI"

    update = client.put(
        "/api/problemata/prob-edit",
        json={
            "source": "ui.update",
            "spec": spec,
        },
    )
    assert update.status_code == 200
    updated = update.json()
    assert updated["problemata_id"] == "prob-edit"
    assert updated["source"] == "ui.update"
    assert updated["spec"]["problemata"]["description"] == "Updated from UI"


def test_diagnostics_endpoint_returns_edge_details(client: TestClient):
    preview = client.post("/api/problemata/preview", json=_blueprint_payload(problemata_id="prob-diagnostics"))
    assert preview.status_code == 200
    spec = preview.json()

    diagnostics = client.post("/api/problemata/diagnostics", json={"spec": spec})
    assert diagnostics.status_code == 200
    payload = diagnostics.json()
    assert payload["validation"]["status"] == "passed"
    assert len(payload["nodes"]) > 0
    assert len(payload["edges"]) > 0
    assert all("status" in edge for edge in payload["edges"])
