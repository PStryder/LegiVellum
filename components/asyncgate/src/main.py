"""
AsyncGate - The Execution Coordinator

FastAPI service for task queue management and worker coordination.
"""
import os
import json
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from legivellum.database import init_database, close_database, get_session_dependency
from legivellum.auth import get_current_tenant
from legivellum.models import Phase, Status, OutcomeKind, EscalationClass
from legivellum.observability import setup_metrics, track_gauge, observability_enabled

from models import (
    TaskCreate,
    TaskResponse,
    Task,
    TaskStatus,
    LeaseRequest,
    LeaseResponse,
    LeaseTask,
    HeartbeatRequest,
    HeartbeatResponse,
    TaskCompleteRequest,
    TaskCompleteResponse,
    TaskFailRequest,
    TaskFailResponse,
    generate_task_id,
    generate_lease_id,
)

from receipt_emitter import (
    emit_receipt_with_retry,
    retry_worker,
    stop_retry_worker,
    get_retry_queue_size,
    ReceiptEmissionError,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
LEASE_DURATION_SECONDS = int(os.environ.get("LEASE_DURATION_SECONDS", 900))  # 15 min default
MEMORYGATE_URL = os.environ.get("MEMORYGATE_URL", "http://memorygate:8001")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    init_database()
    
    # Start receipt retry worker
    retry_task = asyncio.create_task(retry_worker(interval_seconds=60))
    logger.info("Receipt retry worker started")
    
    # Start lease expiry worker
    lease_expiry_task = asyncio.create_task(lease_expiry_worker(interval_seconds=30))
    logger.info("Lease expiry worker started")
    
    logger.info("AsyncGate started with background workers")
    
    yield
    
    # Stop workers
    stop_retry_worker()
    await retry_task
    
    # Cancel lease expiry worker
    lease_expiry_task.cancel()
    try:
        await lease_expiry_task
    except asyncio.CancelledError:
        pass
    
    # Close database
    await close_database()
    logger.info("AsyncGate shutdown complete")


app = FastAPI(
    title="AsyncGate",
    description="The Execution Coordinator - LegiVellum task queue and worker coordination",
    version="0.1.0",
    lifespan=lifespan,
)

# Setup observability (no-op if ENABLE_METRICS != true)
setup_metrics(app, service_name="asyncgate")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Health Endpoints
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "asyncgate"}


@app.get("/ready")
async def readiness_check(session: AsyncSession = Depends(get_session_dependency)):
    """Readiness check - verifies database connectivity"""
    try:
        await session.execute(text("SELECT 1"))
        return {"status": "ready", "database": "connected"}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "database": str(e)}
        )


# =============================================================================
# Task Queue Endpoints
# =============================================================================

@app.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_create: TaskCreate,
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """
    Queue a new task for execution.

    Creates a task in the queue and emits an 'accepted' receipt to MemoryGate.
    """
    task_id = generate_task_id()
    created_at = datetime.utcnow()

    # Insert task into queue
    insert_sql = text("""
        INSERT INTO tasks (
            task_id, tenant_id, task_type, task_summary, task_body, inputs,
            recipient_ai, from_principal, for_principal,
            expected_outcome_kind, expected_artifact_mime,
            caused_by_receipt_id, parent_task_id,
            status, priority, attempt, max_attempts,
            created_at
        ) VALUES (
            :task_id, :tenant_id, :task_type, :task_summary, :task_body, :inputs,
            :recipient_ai, :from_principal, :for_principal,
            :expected_outcome_kind, :expected_artifact_mime,
            :caused_by_receipt_id, :parent_task_id,
            :status, :priority, :attempt, :max_attempts,
            :created_at
        )
    """)

    await session.execute(insert_sql, {
        "task_id": task_id,
        "tenant_id": tenant_id,
        "task_type": task_create.task_type,
        "task_summary": task_create.task_summary,
        "task_body": task_create.task_body,
        "inputs": json.dumps(task_create.inputs),
        "recipient_ai": task_create.recipient_ai,
        "from_principal": task_create.from_principal,
        "for_principal": task_create.for_principal,
        "expected_outcome_kind": task_create.expected_outcome_kind,
        "expected_artifact_mime": task_create.expected_artifact_mime,
        "caused_by_receipt_id": task_create.caused_by_receipt_id or "NA",
        "parent_task_id": task_create.parent_task_id or "NA",
        "status": TaskStatus.QUEUED.value,
        "priority": task_create.priority,
        "attempt": 0,
        "max_attempts": 3,
        "created_at": created_at,
    })
    await session.commit()

    # Emit accepted receipt to MemoryGate
    try:
        receipt_id = await _emit_receipt(
            tenant_id=tenant_id,
            task_id=task_id,
            phase="accepted",
            task_create=task_create,
            created_at=created_at,
        )
    except ReceiptEmissionError as e:
        logger.error(f"Failed to emit accepted receipt for task {task_id}: {e}")
        # Task created but receipt failed - escalate via queue
        # Task will still be visible in queue but audit trail has gap
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "receipt_emission_failed",
                "message": "Task created but receipt emission failed. Queued for retry.",
                "task_id": task_id,
            }
        )

    return TaskResponse(
        task_id=task_id,
        receipt_id=receipt_id,
        status=TaskStatus.QUEUED,
        created_at=created_at,
    )


@app.get("/tasks/{task_id}")
async def get_task(
    task_id: str,
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """Get task details by ID"""
    query = text("""
        SELECT * FROM tasks
        WHERE tenant_id = :tenant_id AND task_id = :task_id
    """)

    result = await session.execute(query, {"tenant_id": tenant_id, "task_id": task_id})
    row = result.mappings().first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Task not found"}
        )

    return _row_to_task(row)


# =============================================================================
# Lease Endpoints (Worker Coordination)
# =============================================================================

@app.post("/lease")
async def lease_task(
    request: LeaseRequest,
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """
    Worker polls for available task.

    Returns 204 No Content if no work available.
    Returns task offer if work is available.
    """
    # Find available task (prefer matching task_types if specified)
    if request.preferred_kinds:
        query = text("""
            SELECT * FROM tasks
            WHERE tenant_id = :tenant_id
              AND status = 'queued'
              AND task_type = ANY(:preferred_kinds)
            ORDER BY priority DESC, created_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """)
        result = await session.execute(query, {
            "tenant_id": tenant_id,
            "preferred_kinds": request.preferred_kinds,
        })
        row = result.mappings().first()
    else:
        row = None

    # If no preferred match, get any available task
    if not row:
        query = text("""
            SELECT * FROM tasks
            WHERE tenant_id = :tenant_id
              AND status = 'queued'
            ORDER BY priority DESC, created_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """)
        result = await session.execute(query, {"tenant_id": tenant_id})
        row = result.mappings().first()

    if not row:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # Create lease
    lease_id = generate_lease_id()
    lease_expires_at = datetime.utcnow() + timedelta(seconds=LEASE_DURATION_SECONDS)

    # Update task with lease
    update_sql = text("""
        UPDATE tasks SET
            status = 'leased',
            lease_id = :lease_id,
            worker_id = :worker_id,
            lease_expires_at = :lease_expires_at,
            started_at = NOW()
        WHERE task_id = :task_id AND tenant_id = :tenant_id
    """)

    await session.execute(update_sql, {
        "lease_id": lease_id,
        "worker_id": request.worker_id,
        "lease_expires_at": lease_expires_at,
        "task_id": row["task_id"],
        "tenant_id": tenant_id,
    })
    await session.commit()

    # Parse inputs
    inputs = row["inputs"]
    if isinstance(inputs, str):
        inputs = json.loads(inputs)

    return LeaseResponse(
        lease_id=lease_id,
        lease_expires_at=lease_expires_at,
        task=LeaseTask(
            task_id=row["task_id"],
            task_type=row["task_type"],
            task_summary=row["task_summary"],
            task_body=row["task_body"],
            inputs=inputs,
            expected_outcome_kind=row["expected_outcome_kind"],
            expected_artifact_mime=row["expected_artifact_mime"],
        ),
    )


@app.post("/lease/{lease_id}/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    lease_id: str,
    request: HeartbeatRequest,
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """
    Worker heartbeat to extend lease.
    """
    # Find the task with this lease
    query = text("""
        SELECT * FROM tasks
        WHERE tenant_id = :tenant_id
          AND lease_id = :lease_id
          AND worker_id = :worker_id
          AND status = 'leased'
    """)

    result = await session.execute(query, {
        "tenant_id": tenant_id,
        "lease_id": lease_id,
        "worker_id": request.worker_id,
    })
    row = result.mappings().first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Lease not found or expired"}
        )

    # Extend lease
    new_expires_at = datetime.utcnow() + timedelta(seconds=LEASE_DURATION_SECONDS)

    update_sql = text("""
        UPDATE tasks SET
            lease_expires_at = :lease_expires_at
        WHERE lease_id = :lease_id AND tenant_id = :tenant_id
    """)

    await session.execute(update_sql, {
        "lease_expires_at": new_expires_at,
        "lease_id": lease_id,
        "tenant_id": tenant_id,
    })
    await session.commit()

    return HeartbeatResponse(
        lease_id=lease_id,
        lease_expires_at=new_expires_at,
        status="extended",
    )


@app.post("/lease/{lease_id}/complete", response_model=TaskCompleteResponse)
async def complete_task(
    lease_id: str,
    request: TaskCompleteRequest,
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """
    Worker marks task as complete.

    Emits 'complete' receipt to MemoryGate.
    """
    # Find the task
    query = text("""
        SELECT * FROM tasks
        WHERE tenant_id = :tenant_id
          AND lease_id = :lease_id
          AND worker_id = :worker_id
          AND status = 'leased'
    """)

    result = await session.execute(query, {
        "tenant_id": tenant_id,
        "lease_id": lease_id,
        "worker_id": request.worker_id,
    })
    row = result.mappings().first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Lease not found or already completed"}
        )

    completed_at = datetime.utcnow()

    # Update task status
    update_sql = text("""
        UPDATE tasks SET
            status = 'completed',
            completed_at = :completed_at
        WHERE lease_id = :lease_id AND tenant_id = :tenant_id
    """)

    await session.execute(update_sql, {
        "completed_at": completed_at,
        "lease_id": lease_id,
        "tenant_id": tenant_id,
    })
    await session.commit()

    # Emit complete receipt to MemoryGate
    receipt_id = await _emit_complete_receipt(
        tenant_id=tenant_id,
        task_row=row,
        request=request,
        completed_at=completed_at,
    )

    return TaskCompleteResponse(
        task_id=row["task_id"],
        lease_id=lease_id,
        status=request.status,
        receipt_id=receipt_id,
        completed_at=completed_at,
    )


@app.post("/lease/{lease_id}/fail", response_model=TaskFailResponse)
async def fail_task(
    lease_id: str,
    request: TaskFailRequest,
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """
    Worker marks task as failed.

    May schedule retry if retryable and attempts remaining.
    """
    # Find the task
    query = text("""
        SELECT * FROM tasks
        WHERE tenant_id = :tenant_id
          AND lease_id = :lease_id
          AND worker_id = :worker_id
          AND status = 'leased'
    """)

    result = await session.execute(query, {
        "tenant_id": tenant_id,
        "lease_id": lease_id,
        "worker_id": request.worker_id,
    })
    row = result.mappings().first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Lease not found"}
        )

    current_attempt = row["attempt"]
    max_attempts = row["max_attempts"]
    can_retry = request.retryable and (current_attempt + 1) < max_attempts

    if can_retry:
        # Re-queue for retry
        update_sql = text("""
            UPDATE tasks SET
                status = 'queued',
                lease_id = NULL,
                worker_id = NULL,
                lease_expires_at = NULL,
                attempt = attempt + 1
            WHERE lease_id = :lease_id AND tenant_id = :tenant_id
        """)
        await session.execute(update_sql, {
            "lease_id": lease_id,
            "tenant_id": tenant_id,
        })
    else:
        # Mark as failed
        update_sql = text("""
            UPDATE tasks SET
                status = 'failed',
                completed_at = NOW()
            WHERE lease_id = :lease_id AND tenant_id = :tenant_id
        """)
        await session.execute(update_sql, {
            "lease_id": lease_id,
            "tenant_id": tenant_id,
        })

        # Emit escalation receipt (max retries exceeded)
        await _emit_escalate_receipt(
            tenant_id=tenant_id,
            task_row=row,
            reason=f"Max retries exceeded: {request.error_message}",
            escalation_class="policy",
        )

    await session.commit()

    return TaskFailResponse(
        task_id=row["task_id"],
        lease_id=lease_id,
        status="retry_scheduled" if can_retry else "failed",
        retry_scheduled=can_retry,
        next_attempt=current_attempt + 1 if can_retry else None,
    )


# =============================================================================
# Background Tasks
# =============================================================================

@app.get("/admin/expire-leases")
async def expire_leases(
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """
    Admin endpoint to expire stale leases.

    In production, this would be a background job.
    """
    now = datetime.utcnow()

    # Find expired leases
    query = text("""
        SELECT * FROM tasks
        WHERE tenant_id = :tenant_id
          AND status = 'leased'
          AND lease_expires_at < :now
    """)

    result = await session.execute(query, {"tenant_id": tenant_id, "now": now})
    expired_rows = result.mappings().all()

    for row in expired_rows:
        can_retry = row["attempt"] + 1 < row["max_attempts"]

        if can_retry:
            update_sql = text("""
                UPDATE tasks SET
                    status = 'queued',
                    lease_id = NULL,
                    worker_id = NULL,
                    lease_expires_at = NULL,
                    attempt = attempt + 1
                WHERE task_id = :task_id AND tenant_id = :tenant_id
            """)
            await session.execute(update_sql, {
                "task_id": row["task_id"],
                "tenant_id": tenant_id,
            })
        else:
            update_sql = text("""
                UPDATE tasks SET
                    status = 'expired',
                    completed_at = NOW()
                WHERE task_id = :task_id AND tenant_id = :tenant_id
            """)
            await session.execute(update_sql, {
                "task_id": row["task_id"],
                "tenant_id": tenant_id,
            })

            # Emit escalation
            try:
                await _emit_escalate_receipt(
                    tenant_id=tenant_id,
                    task_row=row,
                    reason="Lease expired, max retries exceeded",
                    escalation_class="policy",
                )
            except ReceiptEmissionError as e:
                logger.error(f"Failed to emit escalation receipt: {e}")

    await session.commit()

    return {"expired": len(expired_rows)}


@app.get("/admin/receipt-queue")
async def get_receipt_queue_status(tenant_id: str = Depends(get_current_tenant)):
    """
    Admin endpoint to check receipt retry queue status.
    """
    return {
        "queue_size": get_retry_queue_size(),
        "status": "operational" if get_retry_queue_size() < 100 else "warning",
    }


# =============================================================================
# Helper Functions
# =============================================================================

async def _emit_receipt(
    tenant_id: str,
    task_id: str,
    phase: str,
    task_create: TaskCreate,
    created_at: datetime,
) -> str:
    """Emit an accepted receipt to MemoryGate with retry logic"""
    import ulid

    receipt_id = str(ulid.new())

    receipt_data = {
        "schema_version": "1.0",
        "receipt_id": receipt_id,
        "task_id": task_id,
        "parent_task_id": task_create.parent_task_id or "NA",
        "caused_by_receipt_id": task_create.caused_by_receipt_id or "NA",
        "dedupe_key": "NA",
        "attempt": 0,
        "from_principal": task_create.from_principal,
        "for_principal": task_create.for_principal,
        "source_system": "asyncgate",
        "recipient_ai": task_create.recipient_ai,
        "trust_domain": "default",
        "phase": phase,
        "status": "NA",
        "realtime": False,
        "task_type": task_create.task_type,
        "task_summary": task_create.task_summary,
        "task_body": task_create.task_body,
        "inputs": task_create.inputs,
        "expected_outcome_kind": task_create.expected_outcome_kind,
        "expected_artifact_mime": task_create.expected_artifact_mime,
        "outcome_kind": "NA",
        "outcome_text": "NA",
        "artifact_location": "NA",
        "artifact_pointer": "NA",
        "artifact_checksum": "NA",
        "artifact_size_bytes": 0,
        "artifact_mime": "NA",
        "escalation_class": "NA",
        "escalation_reason": "NA",
        "escalation_to": "NA",
        "retry_requested": False,
        "created_at": created_at.isoformat(),
        "metadata": {},
    }

    return await emit_receipt_with_retry(
        memorygate_url=MEMORYGATE_URL,
        tenant_id=tenant_id,
        receipt_data=receipt_data,
    )


async def _emit_complete_receipt(
    tenant_id: str,
    task_row: dict,
    request: TaskCompleteRequest,
    completed_at: datetime,
) -> str:
    """Emit a complete receipt to MemoryGate with retry logic"""
    import ulid

    receipt_id = str(ulid.new())
    inputs = task_row["inputs"]
    if isinstance(inputs, str):
        inputs = json.loads(inputs)

    receipt_data = {
        "schema_version": "1.0",
        "receipt_id": receipt_id,
        "task_id": task_row["task_id"],
        "parent_task_id": task_row["parent_task_id"],
        "caused_by_receipt_id": task_row["caused_by_receipt_id"],
        "dedupe_key": "NA",
        "attempt": task_row["attempt"],
        "from_principal": task_row["from_principal"],
        "for_principal": task_row["for_principal"],
        "source_system": "asyncgate",
        "recipient_ai": task_row["recipient_ai"],
        "trust_domain": "default",
        "phase": "complete",
        "status": request.status,
        "realtime": False,
        "task_type": task_row["task_type"],
        "task_summary": task_row["task_summary"],
        "task_body": task_row["task_body"],
        "inputs": inputs,
        "expected_outcome_kind": task_row["expected_outcome_kind"],
        "expected_artifact_mime": task_row["expected_artifact_mime"],
        "outcome_kind": request.outcome_kind,
        "outcome_text": request.outcome_text,
        "artifact_location": request.artifact_location or "NA",
        "artifact_pointer": request.artifact_pointer or "NA",
        "artifact_checksum": request.artifact_checksum or "NA",
        "artifact_size_bytes": request.artifact_size_bytes,
        "artifact_mime": request.artifact_mime or "NA",
        "escalation_class": "NA",
        "escalation_reason": "NA",
        "escalation_to": "NA",
        "retry_requested": False,
        "completed_at": completed_at.isoformat(),
        "metadata": {},
    }

    return await emit_receipt_with_retry(
        memorygate_url=MEMORYGATE_URL,
        tenant_id=tenant_id,
        receipt_data=receipt_data,
    )


async def _emit_escalate_receipt(
    tenant_id: str,
    task_row: dict,
    reason: str,
    escalation_class: str,
) -> str:
    """Emit an escalate receipt to MemoryGate with retry logic"""
    import ulid

    receipt_id = str(ulid.new())
    inputs = task_row["inputs"]
    if isinstance(inputs, str):
        inputs = json.loads(inputs)

    # Escalate to delegate (DeleGate handles escalations)
    escalation_to = "delegate"

    receipt_data = {
        "schema_version": "1.0",
        "receipt_id": receipt_id,
        "task_id": task_row["task_id"],
        "parent_task_id": task_row["parent_task_id"],
        "caused_by_receipt_id": task_row["caused_by_receipt_id"],
        "dedupe_key": "NA",
        "attempt": task_row["attempt"],
        "from_principal": task_row["from_principal"],
        "for_principal": task_row["for_principal"],
        "source_system": "asyncgate",
        "recipient_ai": escalation_to,  # Routing invariant
        "trust_domain": "default",
        "phase": "escalate",
        "status": "NA",
        "realtime": False,
        "task_type": task_row["task_type"],
        "task_summary": task_row["task_summary"],
        "task_body": task_row["task_body"],
        "inputs": inputs,
        "expected_outcome_kind": task_row["expected_outcome_kind"],
        "expected_artifact_mime": task_row["expected_artifact_mime"],
        "outcome_kind": "NA",
        "outcome_text": "NA",
        "artifact_location": "NA",
        "artifact_pointer": "NA",
        "artifact_checksum": "NA",
        "artifact_size_bytes": 0,
        "artifact_mime": "NA",
        "escalation_class": escalation_class,
        "escalation_reason": reason,
        "escalation_to": escalation_to,
        "retry_requested": False,
        "metadata": {},
    }

    return await emit_receipt_with_retry(
        memorygate_url=MEMORYGATE_URL,
        tenant_id=tenant_id,
        receipt_data=receipt_data,
    )


def _row_to_task(row) -> Task:
    """Convert database row to Task model"""
    data = dict(row)

    if isinstance(data.get("inputs"), str):
        data["inputs"] = json.loads(data["inputs"])

    return Task(**data)


async def lease_expiry_worker(interval_seconds: int = 30):
    """
    Background worker that expires stale leases.
    
    Runs periodically to clean up leases that have expired.
    """
    logger.info(f"Lease expiry worker started (interval: {interval_seconds}s)")
    
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            
            # Use database session from pool
            async with get_session() as session:
                now = datetime.utcnow()
                
                # Find expired leases
                query = text("""
                    SELECT * FROM tasks
                    WHERE status = 'leased'
                      AND lease_expires_at < :now
                """)
                
                result = await session.execute(query, {"now": now})
                expired_rows = result.mappings().all()
                
                if not expired_rows:
                    continue
                
                logger.info(f"Processing {len(expired_rows)} expired leases")
                
                for row in expired_rows:
                    tenant_id = row["tenant_id"]
                    task_id = row["task_id"]
                    can_retry = row["attempt"] + 1 < row["max_attempts"]
                    
                    if can_retry:
                        # Re-queue for retry
                        update_sql = text("""
                            UPDATE tasks SET
                                status = 'queued',
                                lease_id = NULL,
                                worker_id = NULL,
                                lease_expires_at = NULL,
                                attempt = attempt + 1
                            WHERE task_id = :task_id AND tenant_id = :tenant_id
                        """)
                        await session.execute(update_sql, {
                            "task_id": task_id,
                            "tenant_id": tenant_id,
                        })
                        
                        logger.info(
                            f"Lease expired, task re-queued for retry",
                            extra={
                                "task_id": task_id,
                                "attempt": row["attempt"] + 1,
                                "max_attempts": row["max_attempts"],
                            }
                        )
                    else:
                        # Max retries exceeded, mark as expired
                        update_sql = text("""
                            UPDATE tasks SET
                                status = 'expired',
                                completed_at = NOW()
                            WHERE task_id = :task_id AND tenant_id = :tenant_id
                        """)
                        await session.execute(update_sql, {
                            "task_id": task_id,
                            "tenant_id": tenant_id,
                        })
                        
                        # Emit escalation receipt
                        try:
                            await _emit_escalate_receipt(
                                tenant_id=tenant_id,
                                task_row=row,
                                reason="Lease expired, max retries exceeded",
                                escalation_class="policy",
                            )
                            logger.info(
                                f"Lease expired, max retries exceeded, escalated",
                                extra={"task_id": task_id}
                            )
                        except ReceiptEmissionError as e:
                            logger.error(
                                f"Failed to emit escalation receipt for expired task",
                                extra={"task_id": task_id, "error": str(e)}
                            )
                
                await session.commit()
                
        except asyncio.CancelledError:
            logger.info("Lease expiry worker cancelled")
            break
        except Exception as e:
            logger.error(f"Error in lease expiry worker: {e}")


# =============================================================================
# Observability - Custom Metrics
# =============================================================================

# Register custom gauges (no-op if metrics disabled)
if observability_enabled():
    from legivellum.database import get_session
    
    async def get_queued_task_count():
        """Get current count of queued tasks"""
        try:
            async with get_session() as session:
                result = await session.execute(
                    text("SELECT COUNT(*) FROM tasks WHERE status = 'queued'")
                )
                return result.scalar() or 0
        except Exception:
            return 0
    
    # Register gauges that will be updated on /metrics requests
    track_gauge(
        "asyncgate_queue_depth",
        "Number of tasks currently queued",
        lambda: asyncio.run(get_queued_task_count())
    )
    
    track_gauge(
        "asyncgate_retry_queue_depth", 
        "Number of failed receipts queued for retry",
        get_retry_queue_size
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8002)),
        reload=os.environ.get("RELOAD", "false").lower() == "true",
    )
