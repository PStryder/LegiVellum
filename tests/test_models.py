"""
Comprehensive Tests for LegiVellum Receipt Models

Tests Pydantic models, serialization, and field validation.
"""
import pytest
from datetime import datetime, timezone
from legivellum.models import (
    Receipt,
    ReceiptCreate,
    Phase,
    Status,
    OutcomeKind,
    EscalationClass,
)


class TestReceiptModel:
    """Test Receipt Pydantic model"""
    
    def test_minimal_accepted_receipt(self):
        """Create minimal accepted phase receipt"""
        receipt = Receipt(
            receipt_id="01JGXYZ123456789ABCDEFGHIJ",
            task_id="T-01JGXYZ123456789ABCDEFGHIJ",
            parent_task_id="NA",
            caused_by_receipt_id="NA",
            dedupe_key="NA",
            attempt=0,
            from_principal="user@example.com",
            for_principal="user@example.com",
            source_system="test",
            recipient_ai="worker1",
            trust_domain="default",
            phase=Phase.ACCEPTED,
            status=Status.NA,
            realtime=False,
            task_type="test.task",
            task_summary="Test task",
            task_body="Task details",
            inputs={},
            expected_outcome_kind=OutcomeKind.RESPONSE_TEXT,
            expected_artifact_mime="NA",
            outcome_kind=OutcomeKind.NA,
            outcome_text="NA",
            artifact_location="NA",
            artifact_pointer="NA",
            artifact_checksum="NA",
            artifact_size_bytes=0,
            artifact_mime="NA",
            escalation_class=EscalationClass.NA,
            escalation_reason="NA",
            escalation_to="NA",
            retry_requested=False,
            metadata={},
        )
        
        assert receipt.phase == Phase.ACCEPTED
        assert receipt.status == Status.NA
        assert receipt.task_summary == "Test task"
    
    def test_complete_receipt_with_outcome(self):
        """Create complete phase receipt with outcome"""
        receipt = Receipt(
            receipt_id="01JGXYZ123456789ABCDEFGHIJ",
            task_id="T-01JGXYZ123456789ABCDEFGHIJ",
            parent_task_id="NA",
            caused_by_receipt_id="NA",
            dedupe_key="NA",
            attempt=0,
            from_principal="user@example.com",
            for_principal="user@example.com",
            source_system="test",
            recipient_ai="worker1",
            trust_domain="default",
            phase=Phase.COMPLETE,
            status=Status.SUCCESS,
            realtime=False,
            task_type="test.task",
            task_summary="Test task",
            task_body="Task details",
            inputs={},
            expected_outcome_kind=OutcomeKind.RESPONSE_TEXT,
            expected_artifact_mime="NA",
            outcome_kind=OutcomeKind.RESPONSE_TEXT,
            outcome_text="Task completed successfully",
            artifact_location="NA",
            artifact_pointer="NA",
            artifact_checksum="NA",
            artifact_size_bytes=0,
            artifact_mime="NA",
            escalation_class=EscalationClass.NA,
            escalation_reason="NA",
            escalation_to="NA",
            retry_requested=False,
            completed_at=datetime.now(timezone.utc),
            metadata={},
        )
        
        assert receipt.phase == Phase.COMPLETE
        assert receipt.status == Status.SUCCESS
        assert receipt.outcome_text == "Task completed successfully"
        assert receipt.completed_at is not None
    
    def test_escalate_receipt(self):
        """Create escalate phase receipt"""
        receipt = Receipt(
            receipt_id="01JGXYZ123456789ABCDEFGHIJ",
            task_id="T-01JGXYZ123456789ABCDEFGHIJ",
            parent_task_id="NA",
            caused_by_receipt_id="NA",
            dedupe_key="NA",
            attempt=1,
            from_principal="user@example.com",
            for_principal="user@example.com",
            source_system="test",
            recipient_ai="delegate",
            trust_domain="default",
            phase=Phase.ESCALATE,
            status=Status.NA,
            realtime=False,
            task_type="test.task",
            task_summary="Test task",
            task_body="Task details",
            inputs={},
            expected_outcome_kind=OutcomeKind.RESPONSE_TEXT,
            expected_artifact_mime="NA",
            outcome_kind=OutcomeKind.NA,
            outcome_text="NA",
            artifact_location="NA",
            artifact_pointer="NA",
            artifact_checksum="NA",
            artifact_size_bytes=0,
            artifact_mime="NA",
            escalation_class=EscalationClass.CAPABILITY,
            escalation_reason="Worker lacks required capability",
            escalation_to="delegate",
            retry_requested=False,
            metadata={},
        )
        
        assert receipt.phase == Phase.ESCALATE
        assert receipt.escalation_class == EscalationClass.CAPABILITY
        assert receipt.recipient_ai == receipt.escalation_to
    
    def test_json_serialization(self):
        """Test receipt serialization to JSON"""
        receipt = Receipt(
            receipt_id="01JGXYZ123456789ABCDEFGHIJ",
            task_id="T-01JGXYZ123456789ABCDEFGHIJ",
            parent_task_id="NA",
            caused_by_receipt_id="NA",
            dedupe_key="NA",
            attempt=0,
            from_principal="user@example.com",
            for_principal="user@example.com",
            source_system="test",
            recipient_ai="worker1",
            trust_domain="default",
            phase=Phase.ACCEPTED,
            status=Status.NA,
            realtime=False,
            task_type="test.task",
            task_summary="Test task",
            task_body="Task details",
            inputs={"key": "value"},
            expected_outcome_kind=OutcomeKind.RESPONSE_TEXT,
            expected_artifact_mime="NA",
            outcome_kind=OutcomeKind.NA,
            outcome_text="NA",
            artifact_location="NA",
            artifact_pointer="NA",
            artifact_checksum="NA",
            artifact_size_bytes=0,
            artifact_mime="NA",
            escalation_class=EscalationClass.NA,
            escalation_reason="NA",
            escalation_to="NA",
            retry_requested=False,
            metadata={"note": "test"},
        )
        
        json_data = receipt.model_dump()
        assert json_data["receipt_id"] == "01JGXYZ123456789ABCDEFGHIJ"
        assert json_data["inputs"] == {"key": "value"}
        assert json_data["metadata"] == {"note": "test"}


class TestReceiptCreate:
    """Test ReceiptCreate model (excludes tenant_id)"""
    
    def test_receipt_create_excludes_tenant(self):
        """ReceiptCreate should not include tenant_id"""
        receipt = ReceiptCreate(
            receipt_id="01JGXYZ123456789ABCDEFGHIJ",
            task_id="T-01JGXYZ123456789ABCDEFGHIJ",
            parent_task_id="NA",
            caused_by_receipt_id="NA",
            dedupe_key="NA",
            attempt=0,
            from_principal="user@example.com",
            for_principal="user@example.com",
            source_system="test",
            recipient_ai="worker1",
            trust_domain="default",
            phase=Phase.ACCEPTED,
            status=Status.NA,
            realtime=False,
            task_type="test.task",
            task_summary="Test task",
            task_body="Task details",
            inputs={},
            expected_outcome_kind=OutcomeKind.RESPONSE_TEXT,
            expected_artifact_mime="NA",
            outcome_kind=OutcomeKind.NA,
            outcome_text="NA",
            artifact_location="NA",
            artifact_pointer="NA",
            artifact_checksum="NA",
            artifact_size_bytes=0,
            artifact_mime="NA",
            escalation_class=EscalationClass.NA,
            escalation_reason="NA",
            escalation_to="NA",
            retry_requested=False,
            metadata={},
        )
        
        # Verify tenant_id is not in model
        json_data = receipt.model_dump()
        assert "tenant_id" not in json_data


class TestEnums:
    """Test enum values"""
    
    def test_phase_enum(self):
        """Test Phase enum values"""
        assert Phase.ACCEPTED == "accepted"
        assert Phase.COMPLETE == "complete"
        assert Phase.ESCALATE == "escalate"
    
    def test_status_enum(self):
        """Test Status enum values"""
        assert Status.NA == "NA"
        assert Status.SUCCESS == "success"
        assert Status.FAILURE == "failure"
        assert Status.CANCELED == "canceled"
    
    def test_outcome_kind_enum(self):
        """Test OutcomeKind enum values"""
        assert OutcomeKind.NA == "NA"
        assert OutcomeKind.NONE == "none"
        assert OutcomeKind.RESPONSE_TEXT == "response_text"
        assert OutcomeKind.ARTIFACT_POINTER == "artifact_pointer"
        assert OutcomeKind.MIXED == "mixed"
    
    def test_escalation_class_enum(self):
        """Test EscalationClass enum values"""
        assert EscalationClass.NA == "NA"
        assert EscalationClass.OWNER == "owner"
        assert EscalationClass.CAPABILITY == "capability"
        assert EscalationClass.TRUST == "trust"
        assert EscalationClass.POLICY == "policy"
        assert EscalationClass.SCOPE == "scope"
        assert EscalationClass.OTHER == "other"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
