"""
DeleGate - The Pure Planner

FastAPI service for intent-to-plan transformation and delegation coordination.
"""
import os
import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from legivellum.database import init_database, close_database, get_session_dependency
from legivellum.auth import get_current_tenant

from models import (
    Plan,
    PlanRequest,
    PlanResponse,
    PlanStep,
    StepType,
    WorkerInfo,
    WorkerRegisterRequest,
    WorkerListResponse,
    ExecutePlanRequest,
    ExecutePlanResponse,
    PlanStatusResponse,
)
from planner import create_plan

# Configuration
MEMORYGATE_URL = os.environ.get("MEMORYGATE_URL", "http://memorygate:8001")
ASYNCGATE_URL = os.environ.get("ASYNCGATE_URL", "http://asyncgate:8002")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    init_database()
    yield
    await close_database()


app = FastAPI(
    title="DeleGate",
    description="The Pure Planner - LegiVellum intent-to-plan transformation",
    version="0.1.0",
    lifespan=lifespan,
)

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
    return {"status": "healthy", "service": "delegate"}


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
# Plan Creation Endpoints
# =============================================================================

@app.post("/plans", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
async def create_delegation_plan(
    request: PlanRequest,
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """
    Create a delegation plan from an intent.

    Transforms natural language intent into a structured plan with:
    - Execution steps (queue via AsyncGate or direct calls)
    - Dependencies between steps
    - Estimated runtime
    - Escalation points
    """
    # Generate the plan
    plan = create_plan(request)
    created_at = datetime.utcnow()
    plan.created_at = created_at

    # Store plan in database
    insert_sql = text("""
        INSERT INTO plans (
            plan_id, tenant_id, principal_ai, intent, confidence,
            steps, estimated_total_runtime_seconds, notes,
            caused_by_receipt_id, parent_task_id,
            status, created_at
        ) VALUES (
            :plan_id, :tenant_id, :principal_ai, :intent, :confidence,
            :steps, :estimated_total_runtime_seconds, :notes,
            :caused_by_receipt_id, :parent_task_id,
            :status, :created_at
        )
    """)

    await session.execute(insert_sql, {
        "plan_id": plan.plan_id,
        "tenant_id": tenant_id,
        "principal_ai": plan.principal_ai,
        "intent": plan.intent,
        "confidence": plan.confidence,
        "steps": json.dumps([s.model_dump() for s in plan.steps]),
        "estimated_total_runtime_seconds": plan.estimated_total_runtime_seconds,
        "notes": plan.notes,
        "caused_by_receipt_id": request.caused_by_receipt_id or "NA",
        "parent_task_id": request.parent_task_id or "NA",
        "status": "created",
        "created_at": created_at,
    })
    await session.commit()

    # Emit plan_created receipt to MemoryGate
    receipt_id = await _emit_plan_receipt(
        tenant_id=tenant_id,
        plan=plan,
        request=request,
        created_at=created_at,
    )

    return PlanResponse(
        plan=plan,
        receipt_id=receipt_id,
        created_at=created_at,
    )


@app.get("/plans/{plan_id}")
async def get_plan(
    plan_id: str,
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """Get a plan by ID"""
    query = text("""
        SELECT * FROM plans
        WHERE tenant_id = :tenant_id AND plan_id = :plan_id
    """)

    result = await session.execute(query, {"tenant_id": tenant_id, "plan_id": plan_id})
    row = result.mappings().first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Plan not found"}
        )

    return _row_to_plan(row)


@app.get("/plans")
async def list_plans(
    principal_ai: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 20,
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """List plans with optional filtering"""
    conditions = ["tenant_id = :tenant_id"]
    params = {"tenant_id": tenant_id, "limit": limit}

    if principal_ai:
        conditions.append("principal_ai = :principal_ai")
        params["principal_ai"] = principal_ai

    if status:
        conditions.append("status = :status")
        params["status"] = status

    where_clause = " AND ".join(conditions)

    query = text(f"""
        SELECT * FROM plans
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT :limit
    """)

    result = await session.execute(query, params)
    rows = result.mappings().all()

    return {
        "plans": [_row_to_plan(row) for row in rows],
        "count": len(rows),
    }


# =============================================================================
# Plan Execution Endpoints
# =============================================================================

@app.post("/plans/{plan_id}/execute", response_model=ExecutePlanResponse)
async def execute_plan(
    plan_id: str,
    request: ExecutePlanRequest,
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """
    Execute a plan by queuing tasks to AsyncGate.

    Only queues steps of type 'queue_execution'.
    Direct calls and aggregation are handled by the principal.
    """
    # Get the plan
    query = text("""
        SELECT * FROM plans
        WHERE tenant_id = :tenant_id AND plan_id = :plan_id
    """)

    result = await session.execute(query, {"tenant_id": tenant_id, "plan_id": plan_id})
    row = result.mappings().first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Plan not found"}
        )

    plan = _row_to_plan(row)

    if request.dry_run:
        # Just validate, don't execute
        return ExecutePlanResponse(
            plan_id=plan_id,
            status="validated",
            steps_queued=len([s for s in plan.steps if s.step_type == StepType.QUEUE_EXECUTION]),
            receipt_ids=[],
        )

    # Queue execution steps to AsyncGate
    receipt_ids = []
    steps_queued = 0

    for step in plan.steps:
        if step.step_type == StepType.QUEUE_EXECUTION:
            try:
                receipt_id = await _queue_task(
                    tenant_id=tenant_id,
                    plan=plan,
                    step=step,
                )
                receipt_ids.append(receipt_id)
                steps_queued += 1
            except Exception as e:
                print(f"Warning: Failed to queue step {step.step_id}: {e}")

    # Update plan status
    update_sql = text("""
        UPDATE plans SET status = 'executing'
        WHERE plan_id = :plan_id AND tenant_id = :tenant_id
    """)
    await session.execute(update_sql, {"plan_id": plan_id, "tenant_id": tenant_id})
    await session.commit()

    return ExecutePlanResponse(
        plan_id=plan_id,
        status="started",
        steps_queued=steps_queued,
        receipt_ids=receipt_ids,
    )


@app.get("/plans/{plan_id}/status", response_model=PlanStatusResponse)
async def get_plan_status(
    plan_id: str,
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """Get the execution status of a plan"""
    # Get the plan
    query = text("""
        SELECT * FROM plans
        WHERE tenant_id = :tenant_id AND plan_id = :plan_id
    """)

    result = await session.execute(query, {"tenant_id": tenant_id, "plan_id": plan_id})
    row = result.mappings().first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Plan not found"}
        )

    plan = _row_to_plan(row)
    status = row["status"]

    # Count steps by type (simplified - would check MemoryGate for actual status)
    total_steps = len(plan.steps)
    execution_steps = len([s for s in plan.steps if s.step_type == StepType.QUEUE_EXECUTION])

    return PlanStatusResponse(
        plan_id=plan_id,
        status=status,
        total_steps=total_steps,
        completed_steps=0,  # Would query MemoryGate for actual counts
        failed_steps=0,
        pending_steps=execution_steps if status != "completed" else 0,
    )


# =============================================================================
# Worker Registry Endpoints
# =============================================================================

@app.post("/workers", status_code=status.HTTP_201_CREATED)
async def register_worker(
    request: WorkerRegisterRequest,
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """Register a worker with DeleGate"""
    insert_sql = text("""
        INSERT INTO workers (
            worker_id, tenant_id, worker_type, capabilities, task_types,
            description, endpoint, is_async, estimated_runtime_seconds,
            status, last_seen
        ) VALUES (
            :worker_id, :tenant_id, :worker_type, :capabilities, :task_types,
            :description, :endpoint, :is_async, :estimated_runtime_seconds,
            :status, :last_seen
        )
        ON CONFLICT (tenant_id, worker_id) DO UPDATE SET
            worker_type = EXCLUDED.worker_type,
            capabilities = EXCLUDED.capabilities,
            task_types = EXCLUDED.task_types,
            description = EXCLUDED.description,
            endpoint = EXCLUDED.endpoint,
            is_async = EXCLUDED.is_async,
            estimated_runtime_seconds = EXCLUDED.estimated_runtime_seconds,
            status = 'healthy',
            last_seen = NOW()
    """)

    await session.execute(insert_sql, {
        "worker_id": request.worker_id,
        "tenant_id": tenant_id,
        "worker_type": request.worker_type,
        "capabilities": json.dumps(request.capabilities),
        "task_types": json.dumps(request.task_types),
        "description": request.description,
        "endpoint": request.endpoint,
        "is_async": request.is_async,
        "estimated_runtime_seconds": request.estimated_runtime_seconds,
        "status": "healthy",
        "last_seen": datetime.utcnow(),
    })
    await session.commit()

    return {"status": "registered", "worker_id": request.worker_id}


@app.get("/workers", response_model=WorkerListResponse)
async def list_workers(
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """List registered workers"""
    query = text("""
        SELECT * FROM workers
        WHERE tenant_id = :tenant_id
        ORDER BY last_seen DESC
    """)

    result = await session.execute(query, {"tenant_id": tenant_id})
    rows = result.mappings().all()

    workers = []
    for row in rows:
        capabilities = row["capabilities"]
        if isinstance(capabilities, str):
            capabilities = json.loads(capabilities)

        task_types = row["task_types"]
        if isinstance(task_types, str):
            task_types = json.loads(task_types)

        workers.append(WorkerInfo(
            worker_id=row["worker_id"],
            worker_type=row["worker_type"],
            capabilities=capabilities,
            task_types=task_types,
            description=row["description"],
            endpoint=row["endpoint"],
            is_async=row["is_async"],
            estimated_runtime_seconds=row["estimated_runtime_seconds"],
            last_seen=row["last_seen"],
            status=row["status"],
        ))

    return WorkerListResponse(workers=workers, count=len(workers))


# =============================================================================
# Helper Functions
# =============================================================================

async def _emit_plan_receipt(
    tenant_id: str,
    plan: Plan,
    request: PlanRequest,
    created_at: datetime,
) -> str:
    """Emit a plan_created receipt to MemoryGate"""
    import ulid

    receipt_id = str(ulid.new())

    receipt_data = {
        "schema_version": "1.0",
        "receipt_id": receipt_id,
        "task_id": plan.plan_id,  # Use plan_id as task_id
        "parent_task_id": request.parent_task_id or "NA",
        "caused_by_receipt_id": request.caused_by_receipt_id or "NA",
        "dedupe_key": "NA",
        "attempt": 0,
        "from_principal": request.principal_ai,
        "for_principal": request.principal_ai,
        "source_system": "delegate",
        "recipient_ai": request.principal_ai,
        "trust_domain": "default",
        "phase": "accepted",
        "status": "NA",
        "realtime": False,
        "task_type": "plan.create",
        "task_summary": f"Plan created: {request.intent[:100]}",
        "task_body": json.dumps({
            "intent": request.intent,
            "steps": len(plan.steps),
            "confidence": plan.confidence,
        }),
        "inputs": request.context,
        "expected_outcome_kind": "artifact_pointer",
        "expected_artifact_mime": "application/json",
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
        "metadata": {"plan_id": plan.plan_id},
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MEMORYGATE_URL}/receipts",
                json=receipt_data,
                headers={"X-API-Key": f"dev-key-{tenant_id}"},
                timeout=10.0,
            )
            response.raise_for_status()
    except Exception as e:
        print(f"Warning: Failed to emit plan receipt to MemoryGate: {e}")

    return receipt_id


async def _queue_task(
    tenant_id: str,
    plan: Plan,
    step: PlanStep,
) -> str:
    """Queue a task to AsyncGate"""
    task_data = {
        "task_type": step.task_type or "generic",
        "task_summary": step.description,
        "task_body": json.dumps(step.params),
        "inputs": step.params,
        "recipient_ai": plan.principal_ai,
        "from_principal": plan.principal_ai,
        "for_principal": plan.principal_ai,
        "expected_outcome_kind": "artifact_pointer",
        "expected_artifact_mime": "application/json",
        "parent_task_id": plan.plan_id,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{ASYNCGATE_URL}/tasks",
            json=task_data,
            headers={"X-API-Key": f"dev-key-{tenant_id}"},
            timeout=10.0,
        )
        response.raise_for_status()
        result = response.json()
        return result.get("receipt_id", "")


def _row_to_plan(row) -> Plan:
    """Convert database row to Plan model"""
    steps_data = row["steps"]
    if isinstance(steps_data, str):
        steps_data = json.loads(steps_data)

    steps = [PlanStep(**s) for s in steps_data]

    return Plan(
        plan_id=row["plan_id"],
        principal_ai=row["principal_ai"],
        intent=row["intent"],
        confidence=row["confidence"],
        steps=steps,
        estimated_total_runtime_seconds=row["estimated_total_runtime_seconds"],
        notes=row["notes"],
        created_at=row["created_at"],
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8003)),
        reload=os.environ.get("RELOAD", "false").lower() == "true",
    )
