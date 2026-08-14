"""Tests for Problemata control architecture scaffolding."""

from __future__ import annotations

import pytest

from legivellum.problemata_control import (
    ProblemataBlueprint,
    ProblemataControlService,
    ProblemataStatus,
    compile_problemata_blueprint,
)


@pytest.fixture(autouse=True)
def cleanup_database():
    """Override global DB cleanup fixture for this pure-unit module."""
    yield


def test_compile_blueprint_includes_required_primitives_and_edges():
    blueprint = ProblemataBlueprint(
        problemata_id="prob-demo",
        tenant_id="tenant-demo",
        owner_principal="agent.demo",
        include_asyncgate=True,
        include_interrogate=True,
        include_memorygate=True,
    )
    spec = compile_problemata_blueprint(blueprint)

    primitives = spec["primitives"]
    topology = spec["topology"]

    assert "metagate-main" in primitives
    assert "receiptgate-main" in primitives
    assert "depotgate-main" in primitives
    assert "asyncgate-main" in primitives
    assert "interrogate-main" in primitives

    assert any(edge["from"] == "asyncgate-main" and edge["purpose"] == "receipt_emit" for edge in topology)
    assert any(edge["from"] == "asyncgate-main" and edge["purpose"] == "artifact_store" for edge in topology)
    assert any(edge["from"] == "interrogate-main" and edge["purpose"] == "receipt_emit" for edge in topology)


def test_control_service_registers_validated_spec():
    service = ProblemataControlService()
    blueprint = ProblemataBlueprint(
        problemata_id="prob-valid",
        tenant_id="tenant-valid",
        owner_principal="agent.valid",
        include_cognigate=False,
        include_delegategate=False,
        include_interview=False,
    )

    record = service.create_from_blueprint(blueprint)
    assert record.problemata_id == "prob-valid"
    assert record.status == ProblemataStatus.VALIDATED
    assert record.validation.status == "passed"
    assert service.get("prob-valid") is not None


def test_control_service_marks_invalid_spec_as_rejected():
    service = ProblemataControlService()
    invalid_spec = {
        "problemata": {
            "id": "prob-invalid",
            "version": "0.1.0",
            "tenant_id": "tenant-invalid",
            "owner_principal": "agent.invalid",
        },
        "primitives": {
            "metagate-main": {"type": "metagate", "endpoint": "http://localhost/metagate/mcp", "config": {}},
        },
        "topology": [],
    }

    record = service.register_spec(invalid_spec, source="test")
    assert record.status == ProblemataStatus.REJECTED
    assert record.validation.status == "failed"
    assert len(record.validation.errors) > 0


def test_control_service_list_returns_insertion_order():
    service = ProblemataControlService()
    first = ProblemataBlueprint(
        problemata_id="prob-a",
        tenant_id="tenant-a",
        owner_principal="agent.a",
    )
    second = ProblemataBlueprint(
        problemata_id="prob-b",
        tenant_id="tenant-b",
        owner_principal="agent.b",
    )

    service.create_from_blueprint(first)
    service.create_from_blueprint(second)

    records = service.list()
    assert [record.problemata_id for record in records] == ["prob-a", "prob-b"]


def test_control_service_update_spec_rewrites_existing_record():
    service = ProblemataControlService()
    blueprint = ProblemataBlueprint(
        problemata_id="prob-update",
        tenant_id="tenant-update",
        owner_principal="agent.update",
    )
    created = service.create_from_blueprint(blueprint)
    spec = created.spec
    spec["problemata"]["description"] = "Updated description"

    updated = service.update_spec("prob-update", spec, source="unit.update")

    assert updated.problemata_id == "prob-update"
    assert updated.source == "unit.update"
    assert updated.spec["problemata"]["description"] == "Updated description"


def test_control_service_diagnostics_marks_invalid_edge_error():
    service = ProblemataControlService()
    blueprint = ProblemataBlueprint(
        problemata_id="prob-diagnostics",
        tenant_id="tenant-diagnostics",
        owner_principal="agent.diag",
    )
    spec = compile_problemata_blueprint(blueprint)
    spec["topology"][0]["to"] = "missing-node"

    diagnostics = service.diagnose_spec(spec)

    assert diagnostics.validation.status == "failed"
    assert any(edge.status == "error" for edge in diagnostics.edges)
