"""
Tests for LegiVellum Receipt Validation

Tests the shared validation library that enforces:
- Phase-specific constraints
- Routing invariant
- Field size limits
"""
import pytest
from legivellum.models import Receipt, ReceiptCreate, Phase
from legivellum.validation import (
    validate_receipt,
    validate_phase_constraints,
    validate_routing_invariant,
    validate_field_sizes,
    ValidationError,
)


class TestPhaseValidation:
    """Test phase-specific constraint validation"""
    
    def test_accepted_phase_valid(self):
        """Accepted phase with correct fields"""
        receipt = {
            "phase": "accepted",
            "status": "NA",
            "task_summary": "Process data",
            "completed_at": None,
            "escalation_class": "NA",
        }
        errors = validate_phase_constraints(receipt)
        assert len(errors) == 0
    
    def test_accepted_phase_invalid_status(self):
        """Accepted phase cannot have non-NA status"""
        receipt = {
            "phase": "accepted",
            "status": "success",
            "task_summary": "Process data",
            "completed_at": None,
            "escalation_class": "NA",
        }
        errors = validate_phase_constraints(receipt)
        assert len(errors) > 0
        assert any("status must be 'NA'" in e.message for e in errors)
    
    def test_complete_phase_valid(self):
        """Complete phase with correct fields"""
        receipt = {
            "phase": "complete",
            "status": "success",
            "completed_at": "2026-01-05T12:00:00Z",
            "outcome_kind": "response_text",
            "escalation_class": "NA",
        }
        errors = validate_phase_constraints(receipt)
        assert len(errors) == 0
    
    def test_complete_phase_requires_completion_time(self):
        """Complete phase must have completed_at"""
        receipt = {
            "phase": "complete",
            "status": "success",
            "completed_at": None,
            "outcome_kind": "response_text",
            "escalation_class": "NA",
        }
        errors = validate_phase_constraints(receipt)
        assert len(errors) > 0


class TestRoutingInvariant:
    """Test routing invariant: recipient_ai == escalation_to for escalate phase"""
    
    def test_routing_invariant_enforced(self):
        """Escalate receipts must route to escalation_to"""
        receipt = {
            "phase": "escalate",
            "recipient_ai": "worker1",
            "escalation_to": "worker2",
        }
        errors = validate_routing_invariant(receipt)
        assert len(errors) > 0
    
    def test_routing_invariant_satisfied(self):
        """Correct routing for escalate phase"""
        receipt = {
            "phase": "escalate",
            "recipient_ai": "delegate",
            "escalation_to": "delegate",
        }
        errors = validate_routing_invariant(receipt)
        assert len(errors) == 0


class TestFieldSizeLimits:
    """Test field size limit enforcement"""
    
    def test_inputs_size_limit(self):
        """Inputs should be under 64KB"""
        large_inputs = {"data": "x" * 70000}
        receipt = {"inputs": large_inputs}
        errors = validate_field_sizes(receipt)
        assert len(errors) > 0
    
    def test_valid_sizes(self):
        """Fields within size limits"""
        receipt = {
            "inputs": {"data": "small"},
            "task_body": "valid",
            "metadata": {"note": "ok"},
        }
        errors = validate_field_sizes(receipt)
        assert len(errors) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
