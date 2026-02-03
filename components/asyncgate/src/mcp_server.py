"""
AsyncGate MCP Server

MCP (Model Context Protocol) interface for AsyncGate.
Provides tools for task queue management and worker coordination.
"""
import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from sqlalchemy import text

from legivellum.database import init_database, get_session

from models import (
    TaskStatus,
    generate_task_id,
    generate_lease_id,
)

# Initialize MCP server
mcp = Server("asyncgate")

# Configuration
DEFAULT_TENANT = os.environ.get("LEGIVELLUM_TENANT_ID", "pstryder")
LEASE_DURATION_SECONDS = int(os.environ.get("LEASE_DURATION_SECONDS", 900))
MEMORYGATE_URL = os.environ.get("MEMORYGATE_URL", "http://memorygate:8001")


# =============================================================================
# MCP Tools
# =============================================================================

@mcp.tool()
async def queue_task(
    task_type: str,
    task_summary: str,
    recipient_ai: str,
    from_principal: str,
    for_principal: str,
    task_body: str = "",
    inputs: dict = None,
    expected_outcome_kind: str = "NA",
    expected_artifact_mime: str = "NA",
    caused_by_receipt_id: str = None,
    parent_task_id: str = None,
    priority: int = 0,
) -> dict[str, Any]:
    """
    Queue a new task for async execution.

    Creates a task in the queue and emits an 'accepted' receipt to MemoryGate.
    Workers will poll for and execute this task.

    Args:
        task_type: Category of task (e.g., "code.generate", "data.analyze")
        task_summary: Brief description of the task
        recipient_ai: Agent that owns this task
        from_principal: Who requested the work
        for_principal: Who the work is for
        task_body: Full task specification
        inputs: Task input parameters as dict
        expected_outcome_kind: Expected outcome type (NA, none, response_text, artifact_pointer, mixed)
        expected_artifact_mime: Expected artifact MIME type
        caused_by_receipt_id: Receipt that caused this task
        parent_task_id: Parent task for delegation trees
        priority: Task priority (0=normal, 10=highest)

    Returns:
        Task ID, receipt ID, and creation status
    """
    tenant_id = DEFAULT_TENANT
    task_id = generate_task_id()
    created_at = datetime.utcnow()

    async with get_session() as session:
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
            "task_type": task_type,
            "task_summary": task_summary,
            "task_body": task_body,
            "inputs": json.dumps(inputs or {}),
            "recipient_ai": recipient_ai,
            "from_principal": from_principal,
            "for_principal": for_principal,
            "expected_outcome_kind": expected_outcome_kind,
            "expected_artifact_mime": expected_artifact_mime,
            "caused_by_receipt_id": caused_by_receipt_id or "NA",
            "parent_task_id": parent_task_id or "NA",
            "status": TaskStatus.QUEUED.value,
            "priority": max(0, min(10, priority)),
            "attempt": 0,
            "max_attempts": 3,
            "created_at": created_at,
        })
        await session.commit()

    # Emit accepted receipt to MemoryGate
    receipt_id = await _emit_receipt(
        tenant_id=tenant_id,
        task_id=task_id,
        phase="accepted",
        task_type=task_type,
        task_summary=task_summary,
        task_body=task_body,
        inputs=inputs or {},
        recipient_ai=recipient_ai,
        from_principal=from_principal,
        for_principal=for_principal,
        expected_outcome_kind=expected_outcome_kind,
        expected_artifact_mime=expected_artifact_mime,
        caused_by_receipt_id=caused_by_receipt_id,
        parent_task_id=parent_task_id,
        created_at=created_at,
    )

    return {
        "task_id": task_id,
        "receipt_id": receipt_id,
        "status": "queued",
        "created_at": created_at.isoformat(),
    }


@mcp.tool()
async def get_task(task_id: str) -> dict[str, Any]:
    """
    Get task details by ID.

    Args:
        task_id: The task ID to retrieve

    Returns:
        Task details or error if not found
    """
    tenant_id = DEFAULT_TENANT

    async with get_session() as session:
        query = text("""
            SELECT * FROM tasks
            WHERE tenant_id = :tenant_id AND task_id = :task_id
        """)

        result = await session.execute(query, {
            "tenant_id": tenant_id,
            "task_id": task_id,
        })
        row = result.mappings().first()

    if not row:
        return {"error": "not_found", "message": "Task not found"}

    return _row_to_dict(row)


@mcp.tool()
async def list_tasks(
    status: str = None,
    recipient_ai: str = None,
    task_type: str = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    List tasks with optional filters.

    Args:
        status: Filter by status (queued, leased, completed, failed, expired)
        recipient_ai: Filter by recipient agent
        task_type: Filter by task type
        limit: Maximum results (1-100)

    Returns:
        List of matching tasks
    """
    tenant_id = DEFAULT_TENANT
    limit = max(1, min(100, limit))

    conditions = ["tenant_id = :tenant_id"]
    params = {"tenant_id": tenant_id, "limit": limit}

    if status:
        conditions.append("status = :status")
        params["status"] = status

    if recipient_ai:
        conditions.append("recipient_ai = :recipient_ai")
        params["recipient_ai"] = recipient_ai

    if task_type:
        conditions.append("task_type = :task_type")
        params["task_type"] = task_type

    where_clause = " AND ".join(conditions)

    async with get_session() as session:
        query = text(f"""
            SELECT * FROM tasks
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit
        """)

        result = await session.execute(query, params)
        rows = result.mappings().all()

    return {
        "count": len(rows),
        "tasks": [_row_to_dict(row) for row in rows],
    }


@mcp.tool()
async def lease_task(
    worker_id: str,
    capabilities: list = None,
    preferred_kinds: list = None,
) -> dict[str, Any]:
    """
    Worker polls for and leases an available task.

    Returns a task offer if work is available, or empty if no work.
    Worker should emit an accepted receipt after receiving the offer.

    Args:
        worker_id: Unique worker identifier (format: {type}.{instance})
        capabilities: List of worker capabilities for matching
        preferred_kinds: Preferred task types to match

    Returns:
        Task offer with lease details, or empty if no work
    """
    tenant_id = DEFAULT_TENANT
    row = None

    async with get_session() as session:
        # Try preferred kinds first
        if preferred_kinds:
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
                "preferred_kinds": preferred_kinds,
            })
            row = result.mappings().first()

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
            return {"status": "no_work", "message": "No tasks available"}

        # Create lease
        lease_id = generate_lease_id()
        lease_expires_at = datetime.utcnow() + timedelta(seconds=LEASE_DURATION_SECONDS)

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
            "worker_id": worker_id,
            "lease_expires_at": lease_expires_at,
            "task_id": row["task_id"],
            "tenant_id": tenant_id,
        })
        await session.commit()

    # Parse inputs
    inputs = row["inputs"]
    if isinstance(inputs, str):
        inputs = json.loads(inputs)

    return {
        "status": "leased",
        "lease_id": lease_id,
        "lease_expires_at": lease_expires_at.isoformat(),
        "task": {
            "task_id": row["task_id"],
            "task_type": row["task_type"],
            "task_summary": row["task_summary"],
            "task_body": row["task_body"],
            "inputs": inputs,
            "expected_outcome_kind": row["expected_outcome_kind"],
            "expected_artifact_mime": row["expected_artifact_mime"],
        },
    }


@mcp.tool()
async def complete_task(
    lease_id: str,
    worker_id: str,
    status: str,
    outcome_kind: str = "none",
    outcome_text: str = "",
    artifact_pointer: str = None,
    artifact_location: str = None,
    artifact_mime: str = None,
    artifact_checksum: str = None,
    artifact_size_bytes: int = 0,
) -> dict[str, Any]:
    """
    Worker marks a leased task as complete.

    Emits a 'complete' receipt to MemoryGate with the result.

    Args:
        lease_id: The lease ID from lease_task
        worker_id: Worker that executed the task
        status: Completion status (success, failure, canceled)
        outcome_kind: Type of outcome (none, response_text, artifact_pointer, mixed)
        outcome_text: Text outcome or summary
        artifact_pointer: Pointer to artifact if applicable
        artifact_location: Where artifact is stored
        artifact_mime: Artifact MIME type
        artifact_checksum: Artifact integrity checksum
        artifact_size_bytes: Artifact size in bytes

    Returns:
        Completion status and receipt ID
    """
    tenant_id = DEFAULT_TENANT

    async with get_session() as session:
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
            "worker_id": worker_id,
        })
        row = result.mappings().first()

        if not row:
            return {"error": "not_found", "message": "Lease not found or already completed"}

        completed_at = datetime.utcnow()

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

    # Emit complete receipt
    receipt_id = await _emit_complete_receipt(
        tenant_id=tenant_id,
        task_row=row,
        status=status,
        outcome_kind=outcome_kind,
        outcome_text=outcome_text,
        artifact_pointer=artifact_pointer,
        artifact_location=artifact_location,
        artifact_mime=artifact_mime,
        artifact_checksum=artifact_checksum,
        artifact_size_bytes=artifact_size_bytes,
        completed_at=completed_at,
    )

    return {
        "task_id": row["task_id"],
        "lease_id": lease_id,
        "status": status,
        "receipt_id": receipt_id,
        "completed_at": completed_at.isoformat(),
    }


@mcp.tool()
async def fail_task(
    lease_id: str,
    worker_id: str,
    error_message: str,
    retryable: bool = True,
) -> dict[str, Any]:
    """
    Worker marks a leased task as failed.

    May schedule retry if retryable and attempts remaining.

    Args:
        lease_id: The lease ID from lease_task
        worker_id: Worker that attempted the task
        error_message: Description of what failed
        retryable: Whether the task can be retried

    Returns:
        Failure status and whether retry was scheduled
    """
    tenant_id = DEFAULT_TENANT

    async with get_session() as session:
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
            "worker_id": worker_id,
        })
        row = result.mappings().first()

        if not row:
            return {"error": "not_found", "message": "Lease not found"}

        current_attempt = row["attempt"]
        max_attempts = row["max_attempts"]
        can_retry = retryable and (current_attempt + 1) < max_attempts

        if can_retry:
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

            # Emit escalation receipt
            await _emit_escalate_receipt(
                tenant_id=tenant_id,
                task_row=row,
                reason=f"Max retries exceeded: {error_message}",
                escalation_class="policy",
            )

        await session.commit()

    return {
        "task_id": row["task_id"],
        "lease_id": lease_id,
        "status": "retry_scheduled" if can_retry else "failed",
        "retry_scheduled": can_retry,
        "next_attempt": current_attempt + 1 if can_retry else None,
    }


@mcp.tool()
async def heartbeat(lease_id: str, worker_id: str) -> dict[str, Any]:
    """
    Worker sends heartbeat to extend lease.

    Call periodically during long-running tasks to prevent lease expiry.

    Args:
        lease_id: The lease ID to extend
        worker_id: Worker holding the lease

    Returns:
        New lease expiry time
    """
    tenant_id = DEFAULT_TENANT

    async with get_session() as session:
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
            "worker_id": worker_id,
        })
        row = result.mappings().first()

        if not row:
            return {"error": "not_found", "message": "Lease not found or expired"}

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

    return {
        "lease_id": lease_id,
        "lease_expires_at": new_expires_at.isoformat(),
        "status": "extended",
    }


@mcp.tool()
async def expire_leases() -> dict[str, Any]:
    """
    Expire stale leases and emit escalation receipts when retries are exhausted.
    """
    tenant_id = DEFAULT_TENANT
    now = datetime.utcnow()

    async with get_session() as session:
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

                await _emit_escalate_receipt(
                    tenant_id=tenant_id,
                    task_row=row,
                    reason="Lease expired, max retries exceeded",
                    escalation_class="policy",
                )

        await session.commit()

    return {"expired": len(expired_rows)}


# =============================================================================
# Helper Functions
# =============================================================================

def _row_to_dict(row) -> dict[str, Any]:
    """Convert database row to dict"""
    data = dict(row)

    if isinstance(data.get("inputs"), str):
        data["inputs"] = json.loads(data["inputs"])

    for key in ["created_at", "started_at", "completed_at", "lease_expires_at"]:
        if data.get(key) and hasattr(data[key], "isoformat"):
            data[key] = data[key].isoformat()

    data.pop("id", None)
    return data


async def _emit_receipt(
    tenant_id: str,
    task_id: str,
    phase: str,
    task_type: str,
    task_summary: str,
    task_body: str,
    inputs: dict,
    recipient_ai: str,
    from_principal: str,
    for_principal: str,
    expected_outcome_kind: str,
    expected_artifact_mime: str,
    caused_by_receipt_id: Optional[str],
    parent_task_id: Optional[str],
    created_at: datetime,
) -> str:
    """Emit an accepted receipt to MemoryGate"""
    import ulid

    receipt_id = str(ulid.new())

    receipt_data = {
        "schema_version": "1.0",
        "receipt_id": receipt_id,
        "task_id": task_id,
        "parent_task_id": parent_task_id or "NA",
        "caused_by_receipt_id": caused_by_receipt_id or "NA",
        "dedupe_key": "NA",
        "attempt": 0,
        "from_principal": from_principal,
        "for_principal": for_principal,
        "source_system": "asyncgate",
        "recipient_ai": recipient_ai,
        "trust_domain": "default",
        "phase": phase,
        "status": "NA",
        "realtime": False,
        "task_type": task_type,
        "task_summary": task_summary,
        "task_body": task_body,
        "inputs": inputs,
        "expected_outcome_kind": expected_outcome_kind,
        "expected_artifact_mime": expected_artifact_mime,
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
        print(f"Warning: Failed to emit receipt to MemoryGate: {e}")

    return receipt_id


async def _emit_complete_receipt(
    tenant_id: str,
    task_row: dict,
    status: str,
    outcome_kind: str,
    outcome_text: str,
    artifact_pointer: Optional[str],
    artifact_location: Optional[str],
    artifact_mime: Optional[str],
    artifact_checksum: Optional[str],
    artifact_size_bytes: int,
    completed_at: datetime,
) -> str:
    """Emit a complete receipt to MemoryGate"""
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
        "status": status,
        "realtime": False,
        "task_type": task_row["task_type"],
        "task_summary": task_row["task_summary"],
        "task_body": task_row["task_body"],
        "inputs": inputs,
        "expected_outcome_kind": task_row["expected_outcome_kind"],
        "expected_artifact_mime": task_row["expected_artifact_mime"],
        "outcome_kind": outcome_kind,
        "outcome_text": outcome_text,
        "artifact_location": artifact_location or "NA",
        "artifact_pointer": artifact_pointer or "NA",
        "artifact_checksum": artifact_checksum or "NA",
        "artifact_size_bytes": artifact_size_bytes,
        "artifact_mime": artifact_mime or "NA",
        "escalation_class": "NA",
        "escalation_reason": "NA",
        "escalation_to": "NA",
        "retry_requested": False,
        "completed_at": completed_at.isoformat(),
        "metadata": {},
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
        print(f"Warning: Failed to emit complete receipt: {e}")

    return receipt_id


async def _emit_escalate_receipt(
    tenant_id: str,
    task_row: dict,
    reason: str,
    escalation_class: str,
) -> str:
    """Emit an escalate receipt to MemoryGate"""
    import ulid

    receipt_id = str(ulid.new())
    inputs = task_row["inputs"]
    if isinstance(inputs, str):
        inputs = json.loads(inputs)

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
        "recipient_ai": escalation_to,
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
        print(f"Warning: Failed to emit escalate receipt: {e}")

    return receipt_id


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
