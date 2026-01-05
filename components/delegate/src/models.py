"""
DeleGate Models

Plan creation and delegation models.
"""
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import ulid


def generate_plan_id() -> str:
    """Generate a new plan ID"""
    return f"plan-{ulid.new()}"


def generate_step_id() -> str:
    """Generate a new step ID"""
    return f"step-{ulid.new()}"


class StepType(str, Enum):
    """Type of plan step"""
    QUEUE_EXECUTION = "queue_execution"  # Queue work via AsyncGate
    CALL_WORKER = "call_worker"          # Direct worker call (fast)
    WAIT_FOR = "wait_for"                # Wait for async completion
    AGGREGATE = "aggregate"              # Synthesize results
    ESCALATE = "escalate"                # Report upward


class WorkerCapability(str, Enum):
    """Known worker capabilities"""
    CODE_GENERATE = "code.generate"
    CODE_REVIEW = "code.review"
    CODE_REFACTOR = "code.refactor"
    DATA_ANALYZE = "data.analyze"
    DATA_TRANSFORM = "data.transform"
    TEXT_SUMMARIZE = "text.summarize"
    TEXT_TRANSLATE = "text.translate"
    IMAGE_GENERATE = "image.generate"
    SEARCH = "search"
    GENERIC = "generic"


# =============================================================================
# Plan Models
# =============================================================================

class PlanStep(BaseModel):
    """A single step in a delegation plan"""
    step_id: str = Field(default_factory=generate_step_id)
    step_type: StepType
    description: str = Field(default="", description="Human-readable step description")

    # For queue_execution / call_worker
    worker_id: Optional[str] = None
    task_type: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)
    estimated_runtime_seconds: Optional[int] = None

    # For wait_for
    wait_for_step_ids: list[str] = Field(default_factory=list)

    # For aggregate
    aggregate_step_ids: list[str] = Field(default_factory=list)
    synthesis_instructions: Optional[str] = None
    executor: Optional[str] = None  # "principal" or worker_id

    # For escalate
    report_summary: Optional[str] = None
    recommendation: Optional[str] = None

    # Execution dependencies
    depends_on: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    """A complete delegation plan"""
    plan_id: str = Field(default_factory=generate_plan_id)
    principal_ai: str = Field(..., description="Agent that requested the plan")
    intent: str = Field(..., description="Original intent/request")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0, description="Plan confidence")

    # Plan steps
    steps: list[PlanStep] = Field(default_factory=list)

    # Metadata
    estimated_total_runtime_seconds: Optional[int] = None
    notes: Optional[str] = None


class PlanRequest(BaseModel):
    """Request to create a delegation plan"""
    intent: str = Field(..., description="What should be accomplished")
    principal_ai: str = Field(..., description="Agent making the request")

    # Context for planning
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    constraints: list[str] = Field(default_factory=list, description="Constraints to respect")

    # Chain linking
    caused_by_receipt_id: Optional[str] = None
    parent_task_id: Optional[str] = None


class PlanResponse(BaseModel):
    """Response containing the created plan"""
    plan: Plan
    receipt_id: str
    created_at: datetime


# =============================================================================
# Worker Registry Models
# =============================================================================

class WorkerInfo(BaseModel):
    """Information about a registered worker"""
    worker_id: str
    worker_type: str
    capabilities: list[str]
    task_types: list[str]
    description: Optional[str] = None
    endpoint: Optional[str] = None
    is_async: bool = True  # Most workers are async (via AsyncGate)
    estimated_runtime_seconds: int = 60  # Default estimate
    last_seen: Optional[datetime] = None
    status: str = "unknown"  # unknown, healthy, unhealthy


class WorkerRegisterRequest(BaseModel):
    """Request to register a worker"""
    worker_id: str
    worker_type: str
    capabilities: list[str] = Field(default_factory=list)
    task_types: list[str] = Field(default_factory=list)
    description: Optional[str] = None
    endpoint: Optional[str] = None
    is_async: bool = True
    estimated_runtime_seconds: int = 60


class WorkerListResponse(BaseModel):
    """Response listing registered workers"""
    workers: list[WorkerInfo]
    count: int


# =============================================================================
# Execution Models
# =============================================================================

class ExecutePlanRequest(BaseModel):
    """Request to execute a plan"""
    plan_id: str
    dry_run: bool = False  # If true, validate but don't execute


class ExecutePlanResponse(BaseModel):
    """Response from plan execution"""
    plan_id: str
    status: str  # "started", "completed", "failed"
    steps_queued: int
    receipt_ids: list[str]


class PlanStatusResponse(BaseModel):
    """Status of a plan's execution"""
    plan_id: str
    status: str  # "pending", "in_progress", "completed", "failed"
    total_steps: int
    completed_steps: int
    failed_steps: int
    pending_steps: int
