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


class TestEndpointOverrides:
    """endpoint_base alone assumes one gateway host with per-type paths.

    A real mesh addresses each primitive separately, so a Problemata that
    cannot express that cannot describe the deployment it governs.
    """

    def _blueprint(self, **kwargs):
        from legivellum.problemata_control import ProblemataBlueprint

        base = dict(
            problemata_id="override-test",
            tenant_id="default",
            owner_principal="principal-demo",
            description="d",
        )
        base.update(kwargs)
        return ProblemataBlueprint(**base)

    def _compile(self, blueprint):
        from legivellum.problemata_control import compile_problemata_blueprint

        return compile_problemata_blueprint(blueprint)

    def test_override_replaces_derived_endpoint(self):
        spec = self._compile(
            self._blueprint(endpoints={"receiptgate": "http://receiptgate:8000/mcp"})
        )
        assert spec["primitives"]["receiptgate-main"]["endpoint"] == "http://receiptgate:8000/mcp"

    def test_unoverridden_primitives_still_derive(self):
        spec = self._compile(
            self._blueprint(
                endpoint_base="http://gw.example",
                endpoints={"receiptgate": "http://receiptgate:8000/mcp"},
            )
        )
        assert spec["primitives"]["metagate-main"]["endpoint"] == "http://gw.example/metagate/mcp"

    def test_every_primitive_can_be_overridden(self):
        spec = self._compile(
            self._blueprint(
                endpoints={
                    "metagate": "http://metagate:8000/mcp",
                    "receiptgate": "http://receiptgate:8000/mcp",
                    "depotgate": "http://depotgate:8000/mcp",
                    "asyncgate": "http://asyncgate:8080/mcp",
                }
            )
        )
        endpoints = {p["type"]: p["endpoint"] for p in spec["primitives"].values()}
        assert endpoints["metagate"] == "http://metagate:8000/mcp"
        assert endpoints["asyncgate"] == "http://asyncgate:8080/mcp"

    def test_no_overrides_preserves_existing_behaviour(self):
        spec = self._compile(self._blueprint(endpoint_base="http://gw.example"))
        for primitive in spec["primitives"].values():
            assert primitive["endpoint"].startswith("http://gw.example/")

    def test_malformed_override_is_refused(self):
        """A bad override would be published as world-truth to every component."""
        import pytest

        with pytest.raises(Exception, match="must start with http"):
            self._blueprint(endpoints={"receiptgate": "receiptgate:8000"})

    def test_override_trailing_slash_is_normalized(self):
        spec = self._compile(
            self._blueprint(endpoints={"receiptgate": "http://receiptgate:8000/mcp/"})
        )
        assert spec["primitives"]["receiptgate-main"]["endpoint"] == "http://receiptgate:8000/mcp"
