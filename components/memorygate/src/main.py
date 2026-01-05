"""
MemoryGate - The Permanent Record

FastAPI service for the LegiVellum receipt ledger and semantic memory.
"""
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Query, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from legivellum.models import (
    Receipt,
    ReceiptCreate,
    ReceiptResponse,
    InboxResponse,
    BootstrapRequest,
    BootstrapResponse,
    BootstrapConfig,
    BootstrapInbox,
    BootstrapContext,
    TaskTimelineResponse,
    TaskChainResponse,
)
from legivellum.validation import validate_receipt_create, ValidationError
from legivellum.database import init_database, close_database, get_session_dependency
from legivellum.auth import get_current_tenant


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    init_database()
    yield
    # Shutdown
    await close_database()


app = FastAPI(
    title="MemoryGate",
    description="The Permanent Record - LegiVellum receipt ledger and semantic memory",
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


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "memorygate"}


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
# Receipt Endpoints
# =============================================================================

@app.post("/receipts", response_model=ReceiptResponse, status_code=status.HTTP_201_CREATED)
async def create_receipt(
    receipt_create: ReceiptCreate,
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """
    Store a new receipt.

    - tenant_id is extracted from authentication (not from request body)
    - receipt_id is auto-generated if not provided
    - stored_at is set server-side
    """
    try:
        # Validate and create receipt with server-assigned tenant_id
        receipt = validate_receipt_create(receipt_create, tenant_id)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_failed", "details": [e.to_dict()]}
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_failed", "details": [{"message": str(e)}]}
        )

    # Set server timestamp
    stored_at = datetime.utcnow()

    # Insert into database
    try:
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

        # Convert dict fields to JSON strings for PostgreSQL
        import json
        receipt_dict["inputs"] = json.dumps(receipt_dict["inputs"])
        receipt_dict["metadata"] = json.dumps(receipt_dict["metadata"])

        await session.execute(insert_sql, receipt_dict)
        await session.commit()

    except Exception as e:
        if "unique_receipt_per_tenant" in str(e) or "duplicate key" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error": "duplicate_receipt_id",
                    "receipt_id": receipt.receipt_id,
                    "message": "Receipt with this ID already exists"
                }
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "database_error", "message": str(e)}
        )

    return ReceiptResponse(
        receipt_id=receipt.receipt_id,
        stored_at=stored_at,
        tenant_id=tenant_id,
    )


@app.get("/inbox", response_model=InboxResponse)
async def get_inbox(
    recipient_ai: str = Query(..., description="Agent to get inbox for"),
    limit: int = Query(default=20, ge=1, le=100),
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """
    Get active obligations for an agent.

    Returns accepted receipts that haven't been archived.
    """
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
    receipts = [_row_to_receipt(row) for row in rows]

    return InboxResponse(
        tenant_id=tenant_id,
        recipient_ai=recipient_ai,
        count=len(receipts),
        receipts=receipts,
    )


@app.post("/bootstrap", response_model=BootstrapResponse)
async def bootstrap_session(
    request: BootstrapRequest,
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """
    Initialize a new session with configuration and inbox.

    Provides everything an agent needs to resume work:
    - Active obligations (inbox)
    - Recent context (last actions)
    - Configuration (endpoints, schema version)
    """
    agent_name = request.agent_name
    session_id = request.session_id

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
    inbox_receipts = [_row_to_receipt(row) for row in inbox_rows]

    # Get recent context (last 10 receipts for this agent)
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
    recent_receipts = [_row_to_receipt(row) for row in recent_rows]

    # Build configuration
    config = BootstrapConfig(
        receipt_schema_version="1.0",
        memorygate_url=os.environ.get("MEMORYGATE_URL"),
        asyncgate_url=os.environ.get("ASYNCGATE_URL"),
        delegate_url=os.environ.get("DELEGATE_URL"),
        capabilities=["receipts", "semantic_memory", "audit"],
    )

    return BootstrapResponse(
        tenant_id=tenant_id,
        agent_name=agent_name,
        session_id=session_id,
        config=config,
        inbox=BootstrapInbox(
            count=len(inbox_receipts),
            receipts=inbox_receipts,
        ),
        recent_context=BootstrapContext(
            last_10_receipts=recent_receipts,
        ),
    )


@app.get("/receipts/task/{task_id}", response_model=TaskTimelineResponse)
async def get_task_timeline(
    task_id: str,
    sort: str = Query(default="asc", regex="^(asc|desc)$"),
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """
    Get all receipts for a task (lifecycle timeline).
    """
    order = "ASC" if sort == "asc" else "DESC"

    query = text(f"""
        SELECT * FROM receipts
        WHERE tenant_id = :tenant_id
          AND task_id = :task_id
        ORDER BY stored_at {order}
    """)

    result = await session.execute(query, {
        "tenant_id": tenant_id,
        "task_id": task_id,
    })

    rows = result.mappings().all()
    receipts = [_row_to_receipt(row) for row in rows]

    return TaskTimelineResponse(
        tenant_id=tenant_id,
        task_id=task_id,
        receipts=receipts,
    )


@app.get("/receipts/chain/{receipt_id}", response_model=TaskChainResponse)
async def get_receipt_chain(
    receipt_id: str,
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """
    Get escalation/causation chain (recursive provenance).
    """
    # Use recursive CTE to traverse the chain
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
    receipts = [_row_to_receipt(row) for row in rows]

    return TaskChainResponse(
        root_receipt_id=receipt_id,
        chain=receipts,
    )


@app.post("/receipts/{receipt_id}/archive")
async def archive_receipt(
    receipt_id: str,
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """
    Archive a receipt (soft delete from inbox).
    """
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Receipt not found or already archived"}
        )

    return {"status": "archived", "receipt_id": receipt_id}


@app.get("/receipts/{receipt_id}")
async def get_receipt(
    receipt_id: str,
    tenant_id: str = Depends(get_current_tenant),
    session: AsyncSession = Depends(get_session_dependency),
):
    """
    Get a single receipt by ID.
    """
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Receipt not found"}
        )

    return _row_to_receipt(row)


# =============================================================================
# Helper Functions
# =============================================================================

def _row_to_receipt(row) -> Receipt:
    """Convert database row to Receipt model"""
    import json

    data = dict(row)

    # Handle JSON fields
    if isinstance(data.get("inputs"), str):
        data["inputs"] = json.loads(data["inputs"])
    if isinstance(data.get("metadata"), str):
        data["metadata"] = json.loads(data["metadata"])

    # Remove database-internal fields
    data.pop("uuid", None)

    return Receipt(**data)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8001)),
        reload=os.environ.get("RELOAD", "false").lower() == "true",
    )
