"""
DeleGate MCP Server

MCP (Model Context Protocol) interface for DeleGate.
Provides tools for plan creation and delegation coordination.
"""
import asyncio
import json
import os
from datetime import datetime
from typing import Any, Optional

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from sqlalchemy import text

from legivellum.database import init_database, get_session

from models import (
    Plan,
    PlanRequest,
    PlanStep,
    StepType,
    generate_plan_id,
)
from planner import create_plan

# Initialize MCP server
mcp = Server("delegate")

# Configuration
DEFAULT_TENANT = os.environ.get("LEGIVELLUM_TENANT_ID", "pstryder")
MEMORYGATE_URL = os.environ.get("MEMORYGATE_URL", "http://memorygate:8001")
ASYNCGATE_URL = os.environ.get("ASYNCGATE_URL", "http://asyncgate:8002")


# =============================================================================
# MCP Tools
# =============================================================================

@mcp.tool()
async def create_delegation_plan(
    intent: str,
    principal_ai: str,
    context: dict = None,
    constraints: list = None,
    caused_by_receipt_id: str = None,
    parent_task_id: str = None,
) -> dict[str, Any]:
    """
    Create a delegation plan from an intent.

    Transforms natural language intent into a structured plan with:
    - Execution steps (queue via AsyncGate or direct calls)
    - Dependencies between steps
    - Estimated runtime
    - Escalation points

    Args:
        intent: What should be accomplished (natural language)
        principal_ai: Agent making the request
        context: Additional context for planning
        constraints: Constraints to respect during planning
        caused_by_receipt_id: Receipt that caused this plan request
        parent_task_id: Parent task for delegation chains

    Returns:
        Created plan with steps and receipt ID
    """
    tenant_id = DEFAULT_TENANT

    # Build request
    request = PlanRequest(
        intent=intent,
        principal_ai=principal_ai,
        context=context or {},
        constraints=constraints or [],
        caused_by_receipt_id=caused_by_receipt_id,
        parent_task_id=parent_task_id,
    )

    # Generate the plan
    plan = create_plan(request)
    created_at = datetime.utcnow()
    plan.created_at = created_at

    # Store plan in database
    async with get_session() as session:
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

    # Emit plan_created receipt
    receipt_id = await _emit_plan_receipt(
        tenant_id=tenant_id,
        plan=plan,
        request=request,
        created_at=created_at,
    )

    return {
        "plan_id": plan.plan_id,
        "principal_ai": plan.principal_ai,
        "intent": plan.intent,
        "confidence": plan.confidence,
        "steps": [s.model_dump() for s in plan.steps],
        "estimated_total_runtime_seconds": plan.estimated_total_runtime_seconds,
        "notes": plan.notes,
        "receipt_id": receipt_id,
        "created_at": created_at.isoformat(),
    }


@mcp.tool()
async def get_plan(plan_id: str) -> dict[str, Any]:
    """
    Get a plan by ID.

    Args:
        plan_id: The plan ID to retrieve

    Returns:
        Plan details or error if not found
    """
    tenant_id = DEFAULT_TENANT

    async with get_session() as session:
        query = text("""
            SELECT * FROM plans
            WHERE tenant_id = :tenant_id AND plan_id = :plan_id
        """)

        result = await session.execute(query, {
            "tenant_id": tenant_id,
            "plan_id": plan_id,
        })
        row = result.mappings().first()

    if not row:
        return {"error": "not_found", "message": "Plan not found"}

    return _row_to_plan_dict(row)


@mcp.tool()
async def list_plans(
    principal_ai: str = None,
    status: str = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    List plans with optional filters.

    Args:
        principal_ai: Filter by requesting agent
        status: Filter by status (created, executing, completed, failed, canceled)
        limit: Maximum results (1-100)

    Returns:
        List of matching plans
    """
    tenant_id = DEFAULT_TENANT
    limit = max(1, min(100, limit))

    conditions = ["tenant_id = :tenant_id"]
    params = {"tenant_id": tenant_id, "limit": limit}

    if principal_ai:
        conditions.append("principal_ai = :principal_ai")
        params["principal_ai"] = principal_ai

    if status:
        conditions.append("status = :status")
        params["status"] = status

    where_clause = " AND ".join(conditions)

    async with get_session() as session:
        query = text(f"""
            SELECT * FROM plans
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit
        """)

        result = await session.execute(query, params)
        rows = result.mappings().all()

    return {
        "count": len(rows),
        "plans": [_row_to_plan_dict(row) for row in rows],
    }


@mcp.tool()
async def execute_plan(
    plan_id: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Execute a plan by queuing tasks to AsyncGate.

    Only queues steps of type 'queue_execution'.
    Direct calls and aggregation are handled by the principal.

    Args:
        plan_id: The plan ID to execute
        dry_run: If true, validate but don't execute

    Returns:
        Execution status and queued task receipt IDs
    """
    tenant_id = DEFAULT_TENANT

    async with get_session() as session:
        query = text("""
            SELECT * FROM plans
            WHERE tenant_id = :tenant_id AND plan_id = :plan_id
        """)

        result = await session.execute(query, {
            "tenant_id": tenant_id,
            "plan_id": plan_id,
        })
        row = result.mappings().first()

        if not row:
            return {"error": "not_found", "message": "Plan not found"}

        plan_dict = _row_to_plan_dict(row)
        steps = plan_dict["steps"]

        execution_steps = [s for s in steps if s.get("step_type") == "queue_execution"]

        if dry_run:
            return {
                "plan_id": plan_id,
                "status": "validated",
                "steps_to_queue": len(execution_steps),
                "receipt_ids": [],
            }

        # Queue execution steps
        receipt_ids = []
        for step in execution_steps:
            try:
                receipt_id = await _queue_task(
                    tenant_id=tenant_id,
                    plan_id=plan_id,
                    principal_ai=plan_dict["principal_ai"],
                    step=step,
                )
                receipt_ids.append(receipt_id)
            except Exception as e:
                print(f"Warning: Failed to queue step {step.get('step_id')}: {e}")

        # Update plan status
        update_sql = text("""
            UPDATE plans SET status = 'executing'
            WHERE plan_id = :plan_id AND tenant_id = :tenant_id
        """)
        await session.execute(update_sql, {
            "plan_id": plan_id,
            "tenant_id": tenant_id,
        })
        await session.commit()

    return {
        "plan_id": plan_id,
        "status": "started",
        "steps_queued": len(receipt_ids),
        "receipt_ids": receipt_ids,
    }


@mcp.tool()
async def register_worker(
    worker_id: str,
    worker_type: str,
    capabilities: list = None,
    task_types: list = None,
    description: str = None,
    endpoint: str = None,
    is_async: bool = True,
    estimated_runtime_seconds: int = 60,
) -> dict[str, Any]:
    """
    Register a worker with DeleGate.

    Workers are used for task routing during plan creation.

    Args:
        worker_id: Unique worker identifier
        worker_type: Type of worker (e.g., "code-generator")
        capabilities: List of capability tags
        task_types: List of supported task types
        description: Human-readable description
        endpoint: Worker endpoint URL (optional)
        is_async: Whether worker runs async (via AsyncGate)
        estimated_runtime_seconds: Typical runtime estimate

    Returns:
        Registration status
    """
    tenant_id = DEFAULT_TENANT

    async with get_session() as session:
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
            "worker_id": worker_id,
            "tenant_id": tenant_id,
            "worker_type": worker_type,
            "capabilities": json.dumps(capabilities or []),
            "task_types": json.dumps(task_types or []),
            "description": description,
            "endpoint": endpoint,
            "is_async": is_async,
            "estimated_runtime_seconds": estimated_runtime_seconds,
            "status": "healthy",
            "last_seen": datetime.utcnow(),
        })
        await session.commit()

    return {"status": "registered", "worker_id": worker_id}


@mcp.tool()
async def list_workers() -> dict[str, Any]:
    """
    List registered workers.

    Returns:
        List of registered workers with their capabilities
    """
    tenant_id = DEFAULT_TENANT

    async with get_session() as session:
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

        workers.append({
            "worker_id": row["worker_id"],
            "worker_type": row["worker_type"],
            "capabilities": capabilities,
            "task_types": task_types,
            "description": row["description"],
            "endpoint": row["endpoint"],
            "is_async": row["is_async"],
            "estimated_runtime_seconds": row["estimated_runtime_seconds"],
            "status": row["status"],
            "last_seen": row["last_seen"].isoformat() if row["last_seen"] else None,
        })

    return {"count": len(workers), "workers": workers}


@mcp.tool()
async def analyze_intent(intent: str) -> dict[str, Any]:
    """
    Analyze an intent without creating a plan.

    Useful for understanding how DeleGate would decompose an intent.

    Args:
        intent: The intent to analyze

    Returns:
        Analysis including detected task type, complexity, and suggested approach
    """
    from planner import detect_intent_type, estimate_complexity

    task_type = detect_intent_type(intent)
    complexity = estimate_complexity(intent, {})

    # Provide guidance based on analysis
    if complexity == "simple":
        approach = "Single task execution via AsyncGate"
        estimated_steps = 2
    elif complexity == "medium":
        approach = "Sequential execution with synthesis"
        estimated_steps = 4
    else:
        approach = "Parallel subtasks with aggregation"
        estimated_steps = 6

    return {
        "intent": intent,
        "detected_task_type": task_type,
        "complexity": complexity,
        "suggested_approach": approach,
        "estimated_steps": estimated_steps,
    }


# =============================================================================
# Helper Functions
# =============================================================================

def _row_to_plan_dict(row) -> dict[str, Any]:
    """Convert database row to plan dict"""
    steps_data = row["steps"]
    if isinstance(steps_data, str):
        steps_data = json.loads(steps_data)

    return {
        "plan_id": row["plan_id"],
        "principal_ai": row["principal_ai"],
        "intent": row["intent"],
        "confidence": row["confidence"],
        "steps": steps_data,
        "estimated_total_runtime_seconds": row["estimated_total_runtime_seconds"],
        "notes": row["notes"],
        "status": row["status"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


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
        "task_id": plan.plan_id,
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
        print(f"Warning: Failed to emit plan receipt: {e}")

    return receipt_id


async def _queue_task(
    tenant_id: str,
    plan_id: str,
    principal_ai: str,
    step: dict,
) -> str:
    """Queue a task to AsyncGate"""
    task_data = {
        "task_type": step.get("task_type") or "generic",
        "task_summary": step.get("description", ""),
        "task_body": json.dumps(step.get("params", {})),
        "inputs": step.get("params", {}),
        "recipient_ai": principal_ai,
        "from_principal": principal_ai,
        "for_principal": principal_ai,
        "expected_outcome_kind": "artifact_pointer",
        "expected_artifact_mime": "application/json",
        "parent_task_id": plan_id,
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


# =============================================================================
# Main Entry Point
# =============================================================================

async def main():
    """Run the MCP server"""
    init_database()

    async with stdio_server() as (read_stream, write_stream):
        await mcp.run(
            read_stream,
            write_stream,
            mcp.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
