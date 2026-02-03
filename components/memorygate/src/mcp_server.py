"""
MemoryGate MCP Server

MCP (Model Context Protocol) interface for MemoryGate.
Provides tools for receipt storage, inbox queries, and bootstrap.
"""
import asyncio
import json
import os
from datetime import datetime
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
from sqlalchemy import text

from legivellum.models import (
    Receipt,
    ReceiptCreate,
    Phase,
)
from legivellum.validation import validate_receipt_create, ValidationError
from legivellum.database import init_database, get_session


# Initialize MCP server
mcp = Server("memorygate")

# Default tenant for MCP (can be overridden via environment)
DEFAULT_TENANT = os.environ.get("LEGIVELLUM_TENANT_ID", "pstryder")


# =============================================================================
# MCP Tools
# =============================================================================

@mcp.tool()
async def memory_bootstrap(agent_name: str, session_id: str = None) -> dict[str, Any]:
    """
    Bootstrap a session with MemoryGate.

    Returns configuration, active inbox receipts, and recent context.
    Call this at the start of each session to resume work.

    Args:
        agent_name: Name of the agent bootstrapping
        session_id: Optional session identifier

    Returns:
        Bootstrap data including inbox and recent receipts
    """
    tenant_id = DEFAULT_TENANT

    async with get_session() as session:
        # Get inbox (active accepted receipts)
        inbox_query = text("""
            SELECT * FROM receipts
            WHERE tenant_id = :tenant_id
              AND recipient_ai = :recipient_ai
              AND phase = 'accepted'
              AND archived_at IS NULL
            ORDER BY stored_at DESC
            LIMIT 50
        """)

        inbox_result = await session.execute(inbox_query, {
            "tenant_id": tenant_id,
            "recipient_ai": agent_name,
        })
        inbox_rows = inbox_result.mappings().all()

        # Get recent context
        recent_query = text("""
            SELECT * FROM receipts
            WHERE tenant_id = :tenant_id
              AND recipient_ai = :recipient_ai
            ORDER BY stored_at DESC
            LIMIT 10
        """)

        recent_result = await session.execute(recent_query, {
            "tenant_id": tenant_id,
            "recipient_ai": agent_name,
        })
        recent_rows = recent_result.mappings().all()

    return {
        "tenant_id": tenant_id,
        "agent_name": agent_name,
        "session_id": session_id,
        "config": {
            "receipt_schema_version": "1.0",
            "memorygate_url": os.environ.get("MEMORYGATE_URL"),
            "asyncgate_url": os.environ.get("ASYNCGATE_URL"),
            "delegate_url": os.environ.get("DELEGATE_URL"),
            "capabilities": ["receipts", "semantic_memory", "audit"],
        },
        "inbox": {
            "count": len(inbox_rows),
            "receipts": [_row_to_dict(row) for row in inbox_rows],
        },
        "recent_context": {
            "last_10_receipts": [_row_to_dict(row) for row in recent_rows],
        },
    }


@mcp.tool()
async def memory_store_receipt(
    task_id: str,
    phase: str,
    task_type: str,
    task_summary: str,
    from_principal: str,
    for_principal: str,
    recipient_ai: str,
    source_system: str = "mcp",
    task_body: str = "",
    inputs: dict = None,
    status: str = "NA",
    outcome_kind: str = "NA",
    outcome_text: str = "NA",
    artifact_pointer: str = "NA",
    artifact_location: str = "NA",
    artifact_mime: str = "NA",
    escalation_class: str = "NA",
    escalation_reason: str = "NA",
    escalation_to: str = "NA",
    caused_by_receipt_id: str = "NA",
    parent_task_id: str = "NA",
    completed_at: str = None,
    metadata: dict = None,
    receipt_id: str | None = None,
    dedupe_key: str = "NA",
    attempt: int = 0,
    expected_outcome_kind: str = "NA",
    expected_artifact_mime: str = "NA",
    artifact_checksum: str = "NA",
    artifact_size_bytes: int = 0,
    retry_requested: bool = False,
    created_at: str | None = None,
    started_at: str | None = None,
) -> dict[str, Any]:
    """
    Store a receipt in MemoryGate.

    Receipts are immutable records of obligation lifecycle events:
    - accepted: Creates an obligation
    - complete: Resolves an obligation
    - escalate: Transfers responsibility

    Args:
        task_id: Task correlation ID
        phase: Receipt phase (accepted, complete, escalate)
        task_type: Category of task (e.g., "code.generate")
        task_summary: Brief description
        from_principal: Who requested the work
        for_principal: Who the work is for
        recipient_ai: Agent that owns this receipt
        source_system: System emitting the receipt
        task_body: Full task specification
        inputs: Task input parameters
        status: Completion status (NA, success, failure, canceled)
        outcome_kind: Type of outcome (NA, none, response_text, artifact_pointer, mixed)
        outcome_text: Text outcome or summary
        artifact_pointer: Pointer to artifact
        artifact_location: Where artifact is stored
        artifact_mime: Artifact MIME type
        escalation_class: Why escalation (NA, owner, capability, trust, policy, scope, other)
        escalation_reason: Detailed escalation reason
        escalation_to: Escalation target
        caused_by_receipt_id: Receipt that caused this one
        parent_task_id: Parent task for delegation trees
        completed_at: Completion timestamp (ISO 8601)
        metadata: Additional metadata

    Returns:
        Stored receipt details including receipt_id and stored_at
    """
    tenant_id = DEFAULT_TENANT

    # Build receipt create object
    receipt_data = ReceiptCreate(
        receipt_id=receipt_id,
        task_id=task_id,
        phase=Phase(phase),
        task_type=task_type,
        task_summary=task_summary,
        task_body=task_body,
        from_principal=from_principal,
        for_principal=for_principal,
        source_system=source_system,
        recipient_ai=recipient_ai,
        inputs=inputs or {},
        status=status,
        outcome_kind=outcome_kind,
        outcome_text=outcome_text,
        artifact_pointer=artifact_pointer,
        artifact_location=artifact_location,
        artifact_mime=artifact_mime,
        escalation_class=escalation_class,
        escalation_reason=escalation_reason,
        escalation_to=escalation_to,
        caused_by_receipt_id=caused_by_receipt_id,
        parent_task_id=parent_task_id,
        dedupe_key=dedupe_key,
        attempt=attempt,
        expected_outcome_kind=expected_outcome_kind,
        expected_artifact_mime=expected_artifact_mime,
        artifact_checksum=artifact_checksum,
        artifact_size_bytes=artifact_size_bytes,
        retry_requested=retry_requested,
        created_at=datetime.fromisoformat(created_at) if created_at else None,
        started_at=datetime.fromisoformat(started_at) if started_at else None,
        completed_at=datetime.fromisoformat(completed_at) if completed_at else None,
        metadata=metadata or {},
    )

    try:
        receipt = validate_receipt_create(receipt_data, tenant_id)
    except (ValidationError, ValueError) as e:
        return {"error": "validation_failed", "message": str(e)}

    stored_at = datetime.utcnow()

    async with get_session() as session:
        insert_sql = text("""
            INSERT INTO receipts (
                schema_version, tenant_id, receipt_id, task_id, parent_task_id,
                caused_by_receipt_id, dedupe_key, attempt, from_principal,
                for_principal, source_system, recipient_ai, trust_domain,
                phase, status, realtime, task_type, task_summary, task_body,
                inputs, expected_outcome_kind, expected_artifact_mime,
                outcome_kind, outcome_text, artifact_location, artifact_pointer,
                artifact_checksum, artifact_size_bytes, artifact_mime,
                escalation_class, escalation_reason, escalation_to, retry_requested,
                created_at, stored_at, started_at, completed_at, read_at, archived_at,
                metadata
            ) VALUES (
                :schema_version, :tenant_id, :receipt_id, :task_id, :parent_task_id,
                :caused_by_receipt_id, :dedupe_key, :attempt, :from_principal,
                :for_principal, :source_system, :recipient_ai, :trust_domain,
                :phase, :status, :realtime, :task_type, :task_summary, :task_body,
                :inputs, :expected_outcome_kind, :expected_artifact_mime,
                :outcome_kind, :outcome_text, :artifact_location, :artifact_pointer,
                :artifact_checksum, :artifact_size_bytes, :artifact_mime,
                :escalation_class, :escalation_reason, :escalation_to, :retry_requested,
                :created_at, :stored_at, :started_at, :completed_at, :read_at, :archived_at,
                :metadata
            )
        """)

        receipt_dict = receipt.model_dump()
        receipt_dict["stored_at"] = stored_at
        receipt_dict["inputs"] = json.dumps(receipt_dict["inputs"])
        receipt_dict["metadata"] = json.dumps(receipt_dict["metadata"])
        receipt_dict.pop("body", None)
        receipt_dict.pop("artifact_refs", None)

        try:
            await session.execute(insert_sql, receipt_dict)
            await session.commit()
        except Exception as exc:
            if "unique_receipt_per_tenant" in str(exc) or "duplicate key" in str(exc).lower():
                return {"error": "duplicate_receipt_id", "receipt_id": receipt.receipt_id}
            return {"error": "database_error", "message": str(exc)}

    return {
        "receipt_id": receipt.receipt_id,
        "stored_at": stored_at.isoformat(),
        "tenant_id": tenant_id,
    }


@mcp.tool()
async def memory_submit_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    """
    Store a full receipt payload.

    Accepts a ReceiptCreate-shaped payload and returns the stored receipt ID.
    """
    tenant_id = DEFAULT_TENANT

    try:
        receipt_create = ReceiptCreate(**receipt)
        receipt_obj = validate_receipt_create(receipt_create, tenant_id)
    except (ValidationError, ValueError) as exc:
        return {"error": "validation_failed", "message": str(exc)}
    except Exception as exc:  # Pydantic validation errors
        return {"error": "validation_failed", "message": str(exc)}

    stored_at = datetime.utcnow()

    async with get_session() as session:
        insert_sql = text("""
            INSERT INTO receipts (
                schema_version, tenant_id, receipt_id, task_id, parent_task_id,
                caused_by_receipt_id, dedupe_key, attempt, from_principal,
                for_principal, source_system, recipient_ai, trust_domain,
                phase, status, realtime, task_type, task_summary, task_body,
                inputs, expected_outcome_kind, expected_artifact_mime,
                outcome_kind, outcome_text, artifact_location, artifact_pointer,
                artifact_checksum, artifact_size_bytes, artifact_mime,
                escalation_class, escalation_reason, escalation_to, retry_requested,
                created_at, stored_at, started_at, completed_at, read_at, archived_at,
                metadata
            ) VALUES (
                :schema_version, :tenant_id, :receipt_id, :task_id, :parent_task_id,
                :caused_by_receipt_id, :dedupe_key, :attempt, :from_principal,
                :for_principal, :source_system, :recipient_ai, :trust_domain,
                :phase, :status, :realtime, :task_type, :task_summary, :task_body,
                :inputs, :expected_outcome_kind, :expected_artifact_mime,
                :outcome_kind, :outcome_text, :artifact_location, :artifact_pointer,
                :artifact_checksum, :artifact_size_bytes, :artifact_mime,
                :escalation_class, :escalation_reason, :escalation_to, :retry_requested,
                :created_at, :stored_at, :started_at, :completed_at, :read_at, :archived_at,
                :metadata
            )
        """)

        receipt_dict = receipt_obj.model_dump()
        receipt_dict["stored_at"] = stored_at
        receipt_dict["inputs"] = json.dumps(receipt_dict["inputs"])
        receipt_dict["metadata"] = json.dumps(receipt_dict["metadata"])
        receipt_dict.pop("body", None)
        receipt_dict.pop("artifact_refs", None)

        try:
            await session.execute(insert_sql, receipt_dict)
            await session.commit()
        except Exception as exc:
            if "unique_receipt_per_tenant" in str(exc) or "duplicate key" in str(exc).lower():
                return {"error": "duplicate_receipt_id", "receipt_id": receipt_obj.receipt_id}
            return {"error": "database_error", "message": str(exc)}

    return {
        "receipt_id": receipt_obj.receipt_id,
        "stored_at": stored_at.isoformat(),
        "tenant_id": tenant_id,
    }


@mcp.tool()
async def memory_get_inbox(
    recipient_ai: str,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Get active inbox receipts for an agent.

    Returns accepted receipts that haven't been archived.
    These represent open obligations requiring action.

    Args:
        recipient_ai: Agent to get inbox for
        limit: Maximum receipts to return (1-100)

    Returns:
        List of active inbox receipts
    """
    tenant_id = DEFAULT_TENANT
    limit = max(1, min(100, limit))

    async with get_session() as session:
        query = text("""
            SELECT * FROM receipts
            WHERE tenant_id = :tenant_id
              AND recipient_ai = :recipient_ai
              AND phase = 'accepted'
              AND archived_at IS NULL
            ORDER BY stored_at DESC
            LIMIT :limit
        """)

        result = await session.execute(query, {
            "tenant_id": tenant_id,
            "recipient_ai": recipient_ai,
            "limit": limit,
        })
        rows = result.mappings().all()

    return {
        "tenant_id": tenant_id,
        "recipient_ai": recipient_ai,
        "count": len(rows),
        "receipts": [_row_to_dict(row) for row in rows],
    }


@mcp.tool()
async def memory_get_receipt(receipt_id: str) -> dict[str, Any]:
    """
    Get a single receipt by ID.

    Args:
        receipt_id: The receipt ID to retrieve

    Returns:
        Receipt data or error if not found
    """
    tenant_id = DEFAULT_TENANT

    async with get_session() as session:
        query = text("""
            SELECT * FROM receipts
            WHERE tenant_id = :tenant_id
              AND receipt_id = :receipt_id
        """)

        result = await session.execute(query, {
            "tenant_id": tenant_id,
            "receipt_id": receipt_id,
        })
        row = result.mappings().first()

    if not row:
        return {"error": "not_found", "message": "Receipt not found"}

    return _row_to_dict(row)


@mcp.tool()
async def memory_get_task_timeline(task_id: str) -> dict[str, Any]:
    """
    Get all receipts for a task (lifecycle timeline).

    Shows the complete history of a task from accepted to complete/escalate.

    Args:
        task_id: Task ID to get timeline for

    Returns:
        List of receipts in chronological order
    """
    tenant_id = DEFAULT_TENANT

    async with get_session() as session:
        query = text("""
            SELECT * FROM receipts
            WHERE tenant_id = :tenant_id
              AND task_id = :task_id
            ORDER BY stored_at ASC
        """)

        result = await session.execute(query, {
            "tenant_id": tenant_id,
            "task_id": task_id,
        })
        rows = result.mappings().all()

    return {
        "tenant_id": tenant_id,
        "task_id": task_id,
        "receipts": [_row_to_dict(row) for row in rows],
    }


@mcp.tool()
async def memory_get_receipt_chain(receipt_id: str) -> dict[str, Any]:
    """
    Get the receipt causality chain starting at a receipt ID.
    """
    tenant_id = DEFAULT_TENANT

    async with get_session() as session:
        query = text("""
            WITH RECURSIVE chain AS (
                SELECT * FROM receipts
                WHERE tenant_id = :tenant_id AND receipt_id = :receipt_id

                UNION ALL

                SELECT r.* FROM receipts r
                JOIN chain c ON r.caused_by_receipt_id = c.receipt_id
                WHERE r.tenant_id = :tenant_id
            )
            SELECT * FROM chain ORDER BY stored_at
        """)

        result = await session.execute(query, {
            "tenant_id": tenant_id,
            "receipt_id": receipt_id,
        })
        rows = result.mappings().all()

    return {
        "root_receipt_id": receipt_id,
        "chain": [_row_to_dict(row) for row in rows],
    }


@mcp.tool()
async def memory_archive_receipt(receipt_id: str) -> dict[str, Any]:
    """
    Archive a receipt (remove from inbox).

    Archived receipts are still queryable but won't appear in inbox.
    Use this after processing an inbox receipt.

    Args:
        receipt_id: Receipt ID to archive

    Returns:
        Archive status
    """
    tenant_id = DEFAULT_TENANT

    async with get_session() as session:
        query = text("""
            UPDATE receipts
            SET archived_at = NOW()
            WHERE tenant_id = :tenant_id
              AND receipt_id = :receipt_id
              AND archived_at IS NULL
        """)

        result = await session.execute(query, {
            "tenant_id": tenant_id,
            "receipt_id": receipt_id,
        })
        await session.commit()

    if result.rowcount == 0:
        return {"error": "not_found", "message": "Receipt not found or already archived"}

    return {"status": "archived", "receipt_id": receipt_id}


@mcp.tool()
async def memory_search(
    query_text: str = None,
    recipient_ai: str = None,
    task_type: str = None,
    phase: str = None,
    limit: int = 20,
) -> dict[str, Any]:
    """
    Search receipts with filters.

    Args:
        query_text: Text to search in task_summary (optional)
        recipient_ai: Filter by recipient (optional)
        task_type: Filter by task type (optional)
        phase: Filter by phase (accepted, complete, escalate) (optional)
        limit: Maximum results (1-100)

    Returns:
        Matching receipts
    """
    tenant_id = DEFAULT_TENANT
    limit = max(1, min(100, limit))

    conditions = ["tenant_id = :tenant_id"]
    params = {"tenant_id": tenant_id, "limit": limit}

    if query_text:
        conditions.append("task_summary ILIKE :query_text")
        params["query_text"] = f"%{query_text}%"

    if recipient_ai:
        conditions.append("recipient_ai = :recipient_ai")
        params["recipient_ai"] = recipient_ai

    if task_type:
        conditions.append("task_type = :task_type")
        params["task_type"] = task_type

    if phase:
        conditions.append("phase = :phase")
        params["phase"] = phase

    where_clause = " AND ".join(conditions)

    async with get_session() as session:
        query = text(f"""
            SELECT * FROM receipts
            WHERE {where_clause}
            ORDER BY stored_at DESC
            LIMIT :limit
        """)

        result = await session.execute(query, params)
        rows = result.mappings().all()

    return {
        "count": len(rows),
        "receipts": [_row_to_dict(row) for row in rows],
    }


# =============================================================================
# Helper Functions
# =============================================================================

def _row_to_dict(row) -> dict[str, Any]:
    """Convert database row to dict"""
    data = dict(row)

    # Handle JSON fields
    if isinstance(data.get("inputs"), str):
        data["inputs"] = json.loads(data["inputs"])
    if isinstance(data.get("metadata"), str):
        data["metadata"] = json.loads(data["metadata"])

    # Convert datetimes to ISO format
    for key in ["created_at", "stored_at", "started_at", "completed_at", "read_at", "archived_at"]:
        if data.get(key) and hasattr(data[key], "isoformat"):
            data[key] = data[key].isoformat()

    # Remove database-internal fields
    data.pop("uuid", None)

    return data


# =============================================================================
# Main Entry Point
# =============================================================================

async def main():
    """Run the MCP server"""
    # Initialize database
    init_database()

    # Run MCP server
    async with stdio_server() as (read_stream, write_stream):
        await mcp.run(
            read_stream,
            write_stream,
            mcp.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
