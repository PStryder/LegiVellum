"""
AsyncGate Models

Task queue and worker coordination models.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import ulid


class TaskStatus(str, Enum):
    """Task queue status"""
    QUEUED = "queued"
    LEASED = "leased"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"


def generate_task_id() -> str:
    """Generate a new task ID"""
    return f"T-{ulid.new()}"


def generate_lease_id() -> str:
    """Generate a new lease ID"""
    return f"lease-{ulid.new()}"


# =============================================================================
# Task Models
# =============================================================================

class TaskCreate(BaseModel):
    """Request to create a new task"""
    task_type: str = Field(..., description="Category of task (e.g., 'code.generate')")
    task_summary: str = Field(..., description="Brief description")
    task_body: str = Field(default="", description="Full task specification")
    inputs: dict[str, Any] = Field(default_factory=dict, description="Task parameters")

    # Routing
    recipient_ai: str = Field(..., description="Agent that owns this task")
    from_principal: str = Field(..., description="Who requested the work")
    for_principal: str = Field(..., description="Who the work is for")

    # Expected outcome
    expected_outcome_kind: str = Field(default="NA", description="Expected outcome type")
    expected_artifact_mime: str = Field(default="NA", description="Expected MIME type")

    # Chain linking
    caused_by_receipt_id: Optional[str] = Field(default=None, description="Receipt that caused this")
    parent_task_id: Optional[str] = Field(default=None, description="Parent task ID")

    # Priority (for future use)
    priority: int = Field(default=0, ge=0, le=10, description="Task priority (0=normal, 10=highest)")


class TaskResponse(BaseModel):
    """Response after creating a task"""
    task_id: str
    receipt_id: str
    status: TaskStatus
    created_at: datetime


class Task(BaseModel):
    """Internal task representation"""
    task_id: str
    tenant_id: str
    task_type: str
    task_summary: str
    task_body: str
    inputs: dict[str, Any]

    # Routing
    recipient_ai: str
    from_principal: str
    for_principal: str

    # Expected outcome
    expected_outcome_kind: str
    expected_artifact_mime: str

    # Chain linking
    caused_by_receipt_id: Optional[str]
    parent_task_id: Optional[str]

    # Status
    status: TaskStatus
    priority: int

    # Lease tracking
    lease_id: Optional[str] = None
    worker_id: Optional[str] = None
    lease_expires_at: Optional[datetime] = None

    # Retry tracking
    attempt: int = 0
    max_attempts: int = 3

    # Timestamps
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# =============================================================================
# Lease Models
# =============================================================================

class LeaseRequest(BaseModel):
    """Worker request to lease a task"""
    worker_id: str = Field(..., description="Unique worker identifier (format: {type}.{instance})")
    capabilities: list[str] = Field(default_factory=list, description="Worker capabilities")
    max_tasks: int = Field(default=1, ge=1, le=10, description="Max tasks to lease")
    preferred_kinds: list[str] = Field(default_factory=list, description="Preferred task types")


class LeaseTask(BaseModel):
    """Task details in a lease offer"""
    task_id: str
    task_type: str
    task_summary: str
    task_body: str
    inputs: dict[str, Any]
    expected_outcome_kind: str
    expected_artifact_mime: str


class LeaseResponse(BaseModel):
    """Response with leased task"""
    lease_id: str
    lease_expires_at: datetime
    task: LeaseTask


class HeartbeatRequest(BaseModel):
    """Worker heartbeat to extend lease"""
    worker_id: str


class HeartbeatResponse(BaseModel):
    """Response to heartbeat"""
    lease_id: str
    lease_expires_at: datetime
    status: str = "extended"


# =============================================================================
# Completion Models
# =============================================================================

class TaskCompleteRequest(BaseModel):
    """Worker request to mark task complete"""
    worker_id: str
    status: str = Field(..., regex="^(success|failure|canceled)$")

    # Outcome
    outcome_kind: str = Field(default="none", description="Type of outcome")
    outcome_text: str = Field(default="", description="Text outcome or summary")

    # Artifact (if outcome_kind is artifact_pointer or mixed)
    artifact_pointer: Optional[str] = None
    artifact_location: Optional[str] = None
    artifact_mime: Optional[str] = None
    artifact_checksum: Optional[str] = None
    artifact_size_bytes: int = 0


class TaskCompleteResponse(BaseModel):
    """Response after completing task"""
    task_id: str
    lease_id: str
    status: str
    receipt_id: str
    completed_at: datetime


class TaskFailRequest(BaseModel):
    """Worker request to mark task failed"""
    worker_id: str
    error_message: str
    retryable: bool = True


class TaskFailResponse(BaseModel):
    """Response after failing task"""
    task_id: str
    lease_id: str
    status: str
    retry_scheduled: bool
    next_attempt: Optional[int] = None
