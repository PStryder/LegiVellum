"""
LegiVellum Receipt Models

Pydantic models for the LegiVellum receipt protocol.
Based on spec/receipt.rules.md and schema/receipts.sql
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
import ulid


class Phase(str, Enum):
    """Receipt lifecycle phases"""
    ACCEPTED = "accepted"
    COMPLETE = "complete"
    ESCALATE = "escalate"


class Status(str, Enum):
    """Task completion status"""
    NA = "NA"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELED = "canceled"


class OutcomeKind(str, Enum):
    """Type of task outcome"""
    NA = "NA"
    NONE = "none"
    RESPONSE_TEXT = "response_text"
    ARTIFACT_POINTER = "artifact_pointer"
    MIXED = "mixed"


class EscalationClass(str, Enum):
    """Reason category for escalation"""
    NA = "NA"
    OWNER = "owner"
    CAPABILITY = "capability"
    TRUST = "trust"
    POLICY = "policy"
    SCOPE = "scope"
    OTHER = "other"


def generate_receipt_id() -> str:
    """Generate a new ULID for receipt_id"""
    return str(ulid.new())


class Receipt(BaseModel):
    """
    LegiVellum Receipt Model

    Receipts are immutable records of obligation lifecycle events.
    - accepted: creates an obligation
    - complete: resolves an obligation
    - escalate: transfers responsibility
    """

    # Schema version
    schema_version: str = Field(default="1.0", description="Receipt schema version")

    # Multi-tenant identity
    tenant_id: str = Field(default="pstryder", description="Tenant identifier (server-assigned)")

    # Receipt identity
    receipt_id: str = Field(
        default_factory=generate_receipt_id,
        description="Client-generated ULID - stable wire identifier"
    )

    # Task correlation
    task_id: str = Field(..., description="Correlation key for task lifecycle")
    parent_task_id: str = Field(default="NA", description="Parent task for delegation trees")
    caused_by_receipt_id: str = Field(default="NA", description="Provenance chain link")
    dedupe_key: str = Field(default="NA", description="Idempotency key")
    attempt: int = Field(default=0, ge=0, description="Retry attempt number")

    # Routing and accountability
    from_principal: str = Field(..., description="Principal requesting the work")
    for_principal: str = Field(..., description="Principal the work is done for")
    source_system: str = Field(..., description="System emitting the receipt")
    recipient_ai: str = Field(..., description="Agent owning this receipt")
    trust_domain: str = Field(default="default", description="Trust boundary identifier")

    # Phase and status
    phase: Phase = Field(..., description="Lifecycle phase")
    status: Status = Field(default=Status.NA, description="Completion status")
    realtime: bool = Field(default=False, description="Whether this is realtime work")

    # Task definition
    task_type: str = Field(..., description="Category of task")
    task_summary: str = Field(..., description="Brief description of task")
    task_body: str = Field(default="", description="Full task specification")
    inputs: dict[str, Any] = Field(default_factory=dict, description="Task input parameters")
    expected_outcome_kind: OutcomeKind = Field(
        default=OutcomeKind.NA,
        description="Expected type of outcome"
    )
    expected_artifact_mime: str = Field(default="NA", description="Expected artifact MIME type")

    # Outcome and artifacts
    outcome_kind: OutcomeKind = Field(default=OutcomeKind.NA, description="Actual outcome type")
    outcome_text: str = Field(default="NA", description="Text outcome or summary")
    artifact_location: str = Field(default="NA", description="Artifact storage location type")
    artifact_pointer: str = Field(default="NA", description="Pointer to artifact")
    artifact_checksum: str = Field(default="NA", description="Artifact integrity checksum")
    artifact_size_bytes: int = Field(default=0, ge=0, description="Artifact size in bytes")
    artifact_mime: str = Field(default="NA", description="Artifact MIME type")

    # Escalation
    escalation_class: EscalationClass = Field(
        default=EscalationClass.NA,
        description="Escalation reason category"
    )
    escalation_reason: str = Field(default="NA", description="Detailed escalation reason")
    escalation_to: str = Field(default="NA", description="Escalation target")
    retry_requested: bool = Field(default=False, description="Whether retry is requested")

    # Timestamps
    created_at: Optional[datetime] = Field(default=None, description="Issuer clock timestamp")
    stored_at: Optional[datetime] = Field(default=None, description="MemoryGate clock (set on store)")
    started_at: Optional[datetime] = Field(default=None, description="Execution start time")
    completed_at: Optional[datetime] = Field(default=None, description="Execution completion time")
    read_at: Optional[datetime] = Field(default=None, description="Inbox read time")
    archived_at: Optional[datetime] = Field(default=None, description="Archive time")

    # Freeform metadata
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    @model_validator(mode='after')
    def validate_phase_constraints(self) -> 'Receipt':
        """Validate phase-specific constraints per spec/receipt.rules.md"""

        if self.phase == Phase.ACCEPTED:
            # accepted phase rules
            if self.status != Status.NA:
                raise ValueError("status must be 'NA' for accepted phase")
            if self.completed_at is not None:
                raise ValueError("completed_at must be null for accepted phase")
            if self.task_summary == "TBD":
                raise ValueError("task_summary must not be 'TBD' for accepted phase")
            if self.outcome_kind != OutcomeKind.NA:
                raise ValueError("outcome_kind must be 'NA' for accepted phase")
            if self.artifact_pointer != "NA":
                raise ValueError("artifact_pointer must be 'NA' for accepted phase")
            if self.artifact_location != "NA":
                raise ValueError("artifact_location must be 'NA' for accepted phase")
            if self.artifact_mime != "NA":
                raise ValueError("artifact_mime must be 'NA' for accepted phase")
            if self.escalation_class != EscalationClass.NA:
                raise ValueError("escalation_class must be 'NA' for accepted phase")
            if self.escalation_to != "NA":
                raise ValueError("escalation_to must be 'NA' for accepted phase")
            if self.retry_requested:
                raise ValueError("retry_requested must be false for accepted phase")

        elif self.phase == Phase.COMPLETE:
            # complete phase rules
            if self.status not in (Status.SUCCESS, Status.FAILURE, Status.CANCELED):
                raise ValueError("status must be 'success', 'failure', or 'canceled' for complete phase")
            if self.completed_at is None:
                raise ValueError("completed_at is required for complete phase")
            if self.outcome_kind not in (OutcomeKind.NONE, OutcomeKind.RESPONSE_TEXT,
                                          OutcomeKind.ARTIFACT_POINTER, OutcomeKind.MIXED):
                raise ValueError("outcome_kind must be a valid value for complete phase")
            if self.escalation_class != EscalationClass.NA:
                raise ValueError("escalation_class must be 'NA' for complete phase")
            # Check artifact requirements
            if self.outcome_kind in (OutcomeKind.ARTIFACT_POINTER, OutcomeKind.MIXED):
                if self.artifact_pointer == "NA":
                    raise ValueError("artifact_pointer required when outcome_kind is artifact_pointer or mixed")
                if self.artifact_location == "NA":
                    raise ValueError("artifact_location required when outcome_kind is artifact_pointer or mixed")
                if self.artifact_mime == "NA":
                    raise ValueError("artifact_mime required when outcome_kind is artifact_pointer or mixed")

        elif self.phase == Phase.ESCALATE:
            # escalate phase rules
            if self.status != Status.NA:
                raise ValueError("status must be 'NA' for escalate phase")
            if self.escalation_class not in (EscalationClass.OWNER, EscalationClass.CAPABILITY,
                                              EscalationClass.TRUST, EscalationClass.POLICY,
                                              EscalationClass.SCOPE, EscalationClass.OTHER):
                raise ValueError("escalation_class must be a valid escalation value for escalate phase")
            if self.escalation_reason in ("NA", "TBD"):
                raise ValueError("escalation_reason must be provided for escalate phase")
            if self.escalation_to == "NA":
                raise ValueError("escalation_to is required for escalate phase")
            # Routing invariant: recipient_ai must equal escalation_to
            if self.recipient_ai != self.escalation_to:
                raise ValueError("recipient_ai must equal escalation_to for escalate phase")

        # Retry rules
        if self.retry_requested and self.attempt < 1:
            raise ValueError("attempt must be >= 1 when retry_requested is true")

        return self

    class Config:
        use_enum_values = True


class ReceiptCreate(BaseModel):
    """
    Schema for creating a new receipt via API.
    tenant_id is intentionally excluded - server assigns from auth.
    """
    schema_version: str = Field(default="1.0")
    receipt_id: Optional[str] = Field(default=None, description="Client-generated ULID or auto-generated")

    # Task correlation
    task_id: str
    parent_task_id: str = "NA"
    caused_by_receipt_id: str = "NA"
    dedupe_key: str = "NA"
    attempt: int = 0

    # Routing and accountability
    from_principal: str
    for_principal: str
    source_system: str
    recipient_ai: str
    trust_domain: str = "default"

    # Phase and status
    phase: Phase
    status: Status = Status.NA
    realtime: bool = False

    # Task definition
    task_type: str
    task_summary: str
    task_body: str = ""
    inputs: dict[str, Any] = Field(default_factory=dict)
    expected_outcome_kind: OutcomeKind = OutcomeKind.NA
    expected_artifact_mime: str = "NA"

    # Outcome and artifacts
    outcome_kind: OutcomeKind = OutcomeKind.NA
    outcome_text: str = "NA"
    artifact_location: str = "NA"
    artifact_pointer: str = "NA"
    artifact_checksum: str = "NA"
    artifact_size_bytes: int = 0
    artifact_mime: str = "NA"

    # Escalation
    escalation_class: EscalationClass = EscalationClass.NA
    escalation_reason: str = "NA"
    escalation_to: str = "NA"
    retry_requested: bool = False

    # Timestamps
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    class Config:
        use_enum_values = True


class ReceiptResponse(BaseModel):
    """Response after storing a receipt"""
    receipt_id: str
    stored_at: datetime
    tenant_id: str


class InboxResponse(BaseModel):
    """Response for inbox query"""
    tenant_id: str
    recipient_ai: str
    count: int
    receipts: list[Receipt]


class BootstrapRequest(BaseModel):
    """Request for session bootstrap"""
    agent_name: str
    session_id: Optional[str] = None


class BootstrapConfig(BaseModel):
    """Configuration returned in bootstrap"""
    receipt_schema_version: str = "1.0"
    memorygate_url: Optional[str] = None
    asyncgate_url: Optional[str] = None
    delegate_url: Optional[str] = None
    capabilities: list[str] = Field(default_factory=lambda: ["receipts"])


class BootstrapInbox(BaseModel):
    """Inbox portion of bootstrap response"""
    count: int
    receipts: list[Receipt]


class BootstrapContext(BaseModel):
    """Recent context portion of bootstrap response"""
    last_10_receipts: list[Receipt]


class BootstrapResponse(BaseModel):
    """Full bootstrap response"""
    tenant_id: str
    agent_name: str
    session_id: Optional[str]
    config: BootstrapConfig
    inbox: BootstrapInbox
    recent_context: BootstrapContext


class TaskChainResponse(BaseModel):
    """Response for receipt chain query"""
    root_receipt_id: str
    chain: list[Receipt]


class TaskTimelineResponse(BaseModel):
    """Response for task timeline query"""
    tenant_id: str
    task_id: str
    receipts: list[Receipt]
