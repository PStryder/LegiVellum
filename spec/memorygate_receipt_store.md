# MemoryGate Receipt Store Implementation

**Created:** 2026-01-03  
**Updated:** 2026-01-04 (Refocused on implementation role)  
**Status:** Implementation Specification  
**Purpose:** Define MemoryGate's role as the receipt store for the Technomancy Trilogy

**See `receipt_protocol.md` for universal receipt specification.**

---

## MemoryGate's Role

MemoryGate is the **single-writer receipt store** and **bootstrap provider** for the cognitive cluster.

**Core Responsibilities:**
1. Accept receipt POST requests from trilogy components
2. Validate receipts against schema
3. Store receipts in database (dual ID system)
4. Automatically pair completion receipts with roots
5. Return receipts in bootstrap (configuration + inbox)
6. Provide external audit API for compliance

**MemoryGate is a passive ledger, not a coordinator:**
- ✓ Accepts writes, validates, stores
- ✓ Answers explicit queries  
- ✗ Does NOT push notifications
- ✗ Does NOT coordinate work
- ✗ Does NOT interpret receipt meaning

---

## Database Schema

### Receipt Table

```sql
CREATE TABLE receipts (
    -- Dual identity (see receipt_protocol.md)
    uuid UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    receipt_id VARCHAR(200) UNIQUE NOT NULL,
    
    -- What happened?
    event_type VARCHAR(50) NOT NULL,
    summary TEXT NOT NULL,
    
    -- Who owns response?
    recipient_ai VARCHAR(50) NOT NULL,
    source_system VARCHAR(50) NOT NULL,
    
    -- Where is artifact?
    artifact_pointer VARCHAR(500),
    artifact_location VARCHAR(100),
    
    -- What's next?
    requires_action BOOLEAN DEFAULT FALSE,
    suggested_next_step TEXT,
    
    -- Chaining (provenance)
    caused_by_receipt_id VARCHAR(200) REFERENCES receipts(receipt_id),
    
    -- Pairing (completion tracking)
    paired_with_uuid UUID REFERENCES receipts(uuid),
    
    -- Status lifecycle
    status VARCHAR(20) DEFAULT 'active',
    
    -- Deduplication
    dedupe_key VARCHAR(200) UNIQUE NOT NULL,
    
    -- Extensibility
    metadata JSONB,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    delivered_at TIMESTAMP,
    read_at TIMESTAMP,
    archived_at TIMESTAMP,
    
    -- Indexes
    INDEX idx_unpaired (recipient_ai, status) WHERE status = 'active' AND paired_with_uuid IS NULL,
    INDEX idx_chain (caused_by_receipt_id),
    INDEX idx_pairing (paired_with_uuid),
    INDEX idx_event_type (event_type, created_at),
    INDEX idx_source_system (source_system, created_at),
    INDEX idx_recipient_active (recipient_ai, status, created_at) WHERE status = 'active'
);
```

### Indexes Rationale

**idx_unpaired:** Bootstrap queries for actionable receipts
**idx_chain:** Walking receipt chains for audit
**idx_pairing:** Finding paired receipts
**idx_event_type:** Analytics and monitoring
**idx_source_system:** System-level debugging
**idx_recipient_active:** Per-AI inbox queries

---

## Internal API (Service-to-Service)

### POST /internal/receipt

Accept receipt submission from trilogy components.

**Authentication:** Service token (X-Service-Token header)

**Request:**
```http
POST /internal/receipt
Headers:
    X-Service-Token: <shared_secret>
Content-Type: application/json

Body:
{
    "receipt_id": "R.20260104_095023_450.kee.origin_abc",
    "event_type": "task_received",
    "recipient_ai": "kee",
    "source_system": "external_system",
    "summary": "Analyze codebase and suggest improvements",
    "artifact_pointer": null,
    "artifact_location": null,
    "requires_action": true,
    "suggested_next_step": "Create plan for code analysis",
    "caused_by_receipt_id": null,
    "dedupe_key": "external_system:task_abc:v1",
    "metadata": {
        "source_user": "pstryder",
        "priority": "high"
    }
}
```

**Responses:**

```http
200 OK - Success
{
    "status": "stored",
    "uuid": "550e8400-e29b-41d4-a716-446655440000"
}

409 Conflict - Duplicate (idempotent success)
{
    "error": "duplicate_receipt",
    "existing_uuid": "550e8400-...",
    "message": "Receipt with this dedupe_key already exists"
}

400 Bad Request - Validation failed
{
    "error": "validation_failed",
    "field": "receipt_id",
    "message": "Invalid receipt_id format: must match R.{timestamp}.{component}.{ref}"
}

403 Forbidden - Invalid service token
{
    "error": "auth_failed",
    "message": "Invalid or missing service token"
}

503 Service Unavailable - Database down
{
    "error": "storage_unavailable",
    "message": "Receipt store temporarily unavailable"
}
```

**Implementation:**
```python
@app.post("/internal/receipt")
async def create_receipt(request: Request, receipt: ReceiptSubmission):
    # 1. Authenticate
    token = request.headers.get("X-Service-Token")
    expected_token = get_service_token(receipt.source_system)
    
    if not secrets.compare_digest(token or "", expected_token):
        raise HTTPException(403, "Invalid service token")
    
    # 2. Validate schema
    errors = validate_receipt_schema(receipt)
    if errors:
        raise HTTPException(400, {"error": "validation_failed", "fields": errors})
    
    # 3. Check for duplicate
    existing = db.query("SELECT uuid FROM receipts WHERE dedupe_key = ?", receipt.dedupe_key)
    if existing:
        return {"status": "duplicate", "uuid": existing.uuid}
    
    # 4. Store receipt
    try:
        uuid = db.insert("INSERT INTO receipts (...) VALUES (...)")
        
        # 5. Auto-pair if completion receipt
        if receipt.receipt_id.startswith("Complete."):
            await auto_pair_completion(receipt.receipt_id, uuid)
        
        return {"status": "stored", "uuid": uuid}
    
    except DatabaseError as e:
        logger.error(f"Failed to store receipt: {e}")
        raise HTTPException(503, "Receipt store temporarily unavailable")
```

---

## Automatic Pairing Logic

When completion receipt arrives, MemoryGate automatically pairs it with root.

**Pairing Algorithm:**
```python
async def auto_pair_completion(completion_receipt_id: str, completion_uuid: UUID):
    """
    Auto-pair completion receipt with its root.
    
    1. Extract root receipt_id from completion
    2. Find root in database
    3. Update both with cross-references
    4. Mark both as 'complete'
    """
    # Extract root: "Complete.R.20260104_095023_450.kee.task_x" → "R.20260104_095023_450.kee.task_x"
    root_receipt_id = completion_receipt_id.replace("Complete.", "", 1)
    
    # Find root receipt
    root = db.query("SELECT uuid FROM receipts WHERE receipt_id = ?", root_receipt_id)
    
    if not root:
        # Orphaned completion - log and store anyway
        logger.warning(f"Orphaned completion: {completion_receipt_id} has no matching root")
        return
    
    # Update both receipts
    db.execute("""
        UPDATE receipts
        SET paired_with_uuid = ?,
            status = 'complete'
        WHERE receipt_id = ?
    """, [completion_uuid, root_receipt_id])
    
    db.execute("""
        UPDATE receipts
        SET paired_with_uuid = ?,
            status = 'complete'
        WHERE uuid = ?
    """, [root.uuid, completion_uuid])
    
    logger.info(f"Paired receipts: {root_receipt_id} ↔ {completion_receipt_id}")
```

**Retroactive Pairing:**

If completion arrives before root (out-of-order delivery):
```python
async def on_root_receipt_insert(root_receipt_id: str, root_uuid: UUID):
    """
    Check for orphaned completion and pair if exists.
    """
    completion_receipt_id = f"Complete.{root_receipt_id}"
    
    completion = db.query("SELECT uuid FROM receipts WHERE receipt_id = ?", completion_receipt_id)
    
    if completion:
        # Found orphaned completion - pair now
        await pair_receipts(root_uuid, completion.uuid)
        logger.info(f"Retroactively paired: {root_receipt_id} ↔ {completion_receipt_id}")
```

---

## MCP Tools (AI-Facing Interface)

### Enhanced memory_bootstrap()

Existing tool extended to include receipt configuration and inbox.

```python
@mcp.tool()
def memory_bootstrap(ai_name: str, ai_platform: str) -> dict:
    """
    Initialize AI session with memory state, configuration, and inbox.
    
    Returns:
        - Observations, patterns, concepts (existing)
        - Receipt configuration (NEW)
        - Cluster topology (NEW)
        - Active inbox receipts (NEW)
    """
    # Update last_seen for AI instance
    update_ai_seen(ai_name, ai_platform)
    
    # Get receipt configuration
    receipt_config = {
        "schema_version": "1.0.0",
        "format_rules": {
            "root_pattern": "R.{timestamp}.{component}.{reference}",
            "completion_pattern": "Complete.{root_receipt_id}",
            "timestamp_format": "YYYYMMDD_HHmmss_SSS"
        },
        "event_types": ["task_received", "plan_created", "task_queued", 
                       "task_complete", "task_failed", "escalation"],
        "required_fields": ["receipt_id", "event_type", "recipient_ai", 
                          "source_system", "summary", "dedupe_key"]
    }
    
    # Get cluster topology
    cluster_topology = {
        "memorygate_url": os.getenv("MEMORYGATE_PUBLIC_URL"),
        "asyncgate_url": os.getenv("ASYNCGATE_URL"),
        "delegate_endpoints": get_delegate_registry(),
        "mcp_workers": get_worker_registry()
    }
    
    # Get active inbox (unpaired receipts requiring action)
    inbox_receipts = db.execute("""
        UPDATE receipts
        SET delivered_at = COALESCE(delivered_at, NOW())
        WHERE recipient_ai = :ai_name
          AND status = 'active'
          AND paired_with_uuid IS NULL
        RETURNING 
            receipt_id, event_type, summary, 
            source_system, requires_action, 
            artifact_pointer, created_at
        ORDER BY created_at DESC
        LIMIT 10
    """, {"ai_name": ai_name})
    
    unpaired_count = db.scalar("""
        SELECT COUNT(*) FROM receipts
        WHERE recipient_ai = :ai_name
          AND status = 'active'
          AND paired_with_uuid IS NULL
    """, {"ai_name": ai_name})
    
    return {
        # Existing fields
        "observations_count": get_observation_count(ai_name),
        "patterns_count": get_pattern_count(),
        "concepts_count": get_concept_count(),
        
        # Receipt system (NEW)
        "receipt_config": receipt_config,
        "connected_services": cluster_topology,
        
        # Active inbox (NEW)
        "inbox_receipts": inbox_receipts,
        "unpaired_count": unpaired_count,
        "inbox_more_waiting": max(0, unpaired_count - len(inbox_receipts))
    }
```

### New Inbox Management Tools

```python
@mcp.tool()
def get_inbox_receipts(
    unread_only: bool = True,
    limit: int = 20,
    source_system: str = None,
    event_type: str = None
) -> list[dict]:
    """
    Query inbox receipts with filters.
    
    Args:
        unread_only: Only show unread receipts (default true)
        limit: Max receipts to return (default 20, max 100)
        source_system: Filter by source (e.g., "asyncgate")
        event_type: Filter by event type (e.g., "task_complete")
    
    Returns:
        List of receipt dictionaries
    """
    query = """
        SELECT receipt_id, event_type, summary, source_system,
               artifact_pointer, artifact_location, requires_action,
               caused_by_receipt_id, created_at, metadata
        FROM receipts
        WHERE recipient_ai = :ai_name
          AND status = 'active'
    """
    
    params = {"ai_name": get_current_ai()}
    
    if unread_only:
        query += " AND read_at IS NULL"
    
    if source_system:
        query += " AND source_system = :source_system"
        params["source_system"] = source_system
    
    if event_type:
        query += " AND event_type = :event_type"
        params["event_type"] = event_type
    
    query += " ORDER BY created_at DESC LIMIT :limit"
    params["limit"] = min(limit, 100)
    
    return db.execute(query, params)

@mcp.tool()
def read_inbox_receipt(receipt_id: str) -> dict:
    """
    Mark receipt as read and return full details.
    
    Sets read_at timestamp and returns complete receipt including metadata.
    """
    db.execute("""
        UPDATE receipts
        SET read_at = COALESCE(read_at, NOW())
        WHERE receipt_id = :receipt_id
          AND recipient_ai = :ai_name
    """, {"receipt_id": receipt_id, "ai_name": get_current_ai()})
    
    receipt = db.query("""
        SELECT * FROM receipts
        WHERE receipt_id = :receipt_id
          AND recipient_ai = :ai_name
    """, {"receipt_id": receipt_id, "ai_name": get_current_ai()})
    
    if not receipt:
        raise NotFoundError(f"Receipt {receipt_id} not found or not owned by you")
    
    return receipt

@mcp.tool()
def archive_inbox_receipt(receipt_id: str) -> dict:
    """
    Archive a receipt (hides from active inbox, preserves for audit).
    
    Sets archived_at timestamp and changes status to 'archived'.
    """
    result = db.execute("""
        UPDATE receipts
        SET archived_at = NOW(),
            status = 'archived'
        WHERE receipt_id = :receipt_id
          AND recipient_ai = :ai_name
          AND status = 'active'
        RETURNING receipt_id
    """, {"receipt_id": receipt_id, "ai_name": get_current_ai()})
    
    if not result:
        raise NotFoundError(f"Receipt {receipt_id} not found, already archived, or not owned by you")
    
    return {"status": "archived", "receipt_id": receipt_id}
```

---

## External Audit API

Read-only queries for compliance and monitoring.

**Authentication:** External API key (different from service tokens)

### GET /external/receipt-chain

```http
GET /external/receipt-chain?root=R.20260104_095023_450.kee.origin_abc
Headers:
    Authorization: Bearer <external_api_key>

Response (200 OK):
{
    "root_receipt_id": "R.20260104_095023_450.kee.origin_abc",
    "status": "complete",
    "chain": [
        {
            "receipt_id": "R.20260104_095023_450.kee.origin_abc",
            "event_type": "task_received",
            "summary": "Analyze codebase",
            "created_at": "2026-01-04T09:50:23.450Z",
            "caused_by_receipt_id": null
        },
        {
            "receipt_id": "R.20260104_095024_120.delegate.plan_xyz",
            "event_type": "plan_created",
            "created_at": "2026-01-04T09:50:24.120Z",
            "caused_by_receipt_id": "R.20260104_095023_450.kee.origin_abc"
        },
        {
            "receipt_id": "Complete.R.20260104_095023_450.kee.origin_abc",
            "event_type": "task_complete",
            "created_at": "2026-01-04T10:05:20.100Z",
            "paired_with": "R.20260104_095023_450.kee.origin_abc"
        }
    ],
    "completion_timestamp": "2026-01-04T10:05:20.100Z",
    "total_duration_seconds": 897
}
```

**Implementation:**
```python
@app.get("/external/receipt-chain")
async def get_receipt_chain(root: str, auth: str = Header(...)):
    validate_external_api_key(auth)
    
    # Walk chain from root
    chain = []
    current_id = root
    
    while current_id:
        receipt = db.query("SELECT * FROM receipts WHERE receipt_id = ?", current_id)
        if not receipt:
            break
        
        chain.append(receipt)
        
        # Find children (receipts caused by this one)
        children = db.query("""
            SELECT receipt_id FROM receipts 
            WHERE caused_by_receipt_id = ?
            ORDER BY created_at ASC
        """, current_id)
        
        current_id = children[0].receipt_id if children else None
    
    # Find completion receipt
    completion = db.query("""
        SELECT * FROM receipts
        WHERE receipt_id = ?
    """, f"Complete.{root}")
    
    if completion:
        chain.append(completion)
    
    return {
        "root_receipt_id": root,
        "status": "complete" if completion else "in_progress",
        "chain": chain,
        "completion_timestamp": completion.created_at if completion else None
    }
```

### GET /external/work-in-flight

```http
GET /external/work-in-flight?recipient_ai=kee
Headers:
    Authorization: Bearer <external_api_key>

Response (200 OK):
{
    "recipient_ai": "kee",
    "unpaired_receipts": [
        {
            "receipt_id": "R.20260104_095023_450.kee.origin_abc",
            "event_type": "task_received",
            "summary": "Analyze codebase",
            "created_at": "2026-01-04T09:50:23.450Z",
            "age_seconds": 1234
        }
    ],
    "count": 1
}
```

---

## Service Token Management

### Token Generation

```python
import secrets

def generate_service_token(source_system: str) -> str:
    """Generate cryptographically secure service token."""
    token = secrets.token_urlsafe(64)
    
    db.execute("""
        INSERT INTO service_tokens (source_system, token_hash, created_at)
        VALUES (?, ?, NOW())
    """, [source_system, hash_token(token)])
    
    return token

# Store in both systems:
# AsyncGate: MEMORYGATE_SERVICE_TOKEN=<token>
# MemoryGate: ASYNCGATE_SERVICE_TOKEN_HASH=<hash>
```

### Token Validation

```python
def validate_service_token(source_system: str, token: str) -> bool:
    """Validate service token against stored hash."""
    stored_hash = db.scalar("""
        SELECT token_hash FROM service_tokens
        WHERE source_system = ? AND revoked_at IS NULL
    """, source_system)
    
    if not stored_hash:
        return False
    
    return secrets.compare_digest(hash_token(token), stored_hash)
```

### Token Rotation

```python
def rotate_service_token(source_system: str) -> str:
    """Generate new token and revoke old one."""
    # Revoke existing
    db.execute("""
        UPDATE service_tokens
        SET revoked_at = NOW()
        WHERE source_system = ? AND revoked_at IS NULL
    """, source_system)
    
    # Generate new
    return generate_service_token(source_system)
```

---

## Rate Limiting

Prevent receipt spam from compromised or buggy components.

```python
# Per source_system limits
RATE_LIMITS = {
    "asyncgate": 1000,  # receipts/hour
    "delegate": 500,
    "principal": 100,
    "default": 50
}

async def check_rate_limit(source_system: str):
    """Check if source_system has exceeded rate limit."""
    key = f"receipt_rate:{source_system}"
    count = redis.incr(key)
    
    if count == 1:
        redis.expire(key, 3600)  # 1 hour window
    
    limit = RATE_LIMITS.get(source_system, RATE_LIMITS["default"])
    
    if count > limit:
        raise HTTPException(429, f"Rate limit exceeded: {limit}/hour")
```

---

## Monitoring & Observability

### Key Metrics

Prometheus metrics exposed:

```python
# Receipt volume
receipt_submissions_total = Counter(
    "memorygate_receipt_submissions_total",
    "Total receipt submissions",
    ["source_system", "event_type", "status"]
)

# Pairing success
receipt_pairings_total = Counter(
    "memorygate_receipt_pairings_total",
    "Total receipt pairings",
    ["success"]
)

# Active receipts
active_receipts_gauge = Gauge(
    "memorygate_active_receipts",
    "Current number of active unpaired receipts",
    ["recipient_ai"]
)

# Storage latency
receipt_storage_duration = Histogram(
    "memorygate_receipt_storage_duration_seconds",
    "Receipt storage latency"
)
```

### Health Check

```python
@app.get("/health")
async def health_check():
    """Health check endpoint for load balancers."""
    try:
        # Test database connectivity
        db.query("SELECT 1")
        
        # Test receipt store
        receipt_count = db.scalar("SELECT COUNT(*) FROM receipts")
        
        return {
            "status": "healthy",
            "receipt_count": receipt_count,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(503, "Service unhealthy")
```

---

## Data Retention & Archiving

### Automatic Archiving

Daily cron job archives old complete receipts:

```python
def archive_old_receipts(retention_days: int = 90):
    """Archive receipts older than retention period."""
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    
    result = db.execute("""
        UPDATE receipts
        SET status = 'archived',
            archived_at = NOW()
        WHERE status = 'complete'
          AND created_at < :cutoff
        RETURNING uuid
    """, {"cutoff": cutoff})
    
    logger.info(f"Archived {len(result)} receipts older than {retention_days} days")
    return len(result)
```

### Cold Storage Export

Export archived receipts to object storage:

```python
def export_to_cold_storage(batch_size: int = 1000):
    """Export archived receipts to S3 for compliance."""
    archived = db.query("""
        SELECT * FROM receipts
        WHERE status = 'archived'
          AND exported_at IS NULL
        LIMIT :batch_size
    """, {"batch_size": batch_size})
    
    if not archived:
        return 0
    
    # Export to S3
    export_key = f"receipts/archive/{datetime.utcnow().date()}/{uuid4()}.jsonl"
    s3.put_object(
        Bucket="memorygate-compliance",
        Key=export_key,
        Body="\n".join(json.dumps(r) for r in archived)
    )
    
    # Mark as exported
    db.execute("""
        UPDATE receipts
        SET exported_at = NOW(),
            export_location = :location
        WHERE uuid IN :uuids
    """, {"location": export_key, "uuids": [r.uuid for r in archived]})
    
    return len(archived)
```

---

## Security Considerations

### Sensitive Data in Receipts

Receipts may contain sensitive information in metadata:
- User identifiers
- Task parameters
- Artifact locations

**Mitigation:**
```python
# Encrypt sensitive metadata before storage
def encrypt_metadata(metadata: dict) -> str:
    sensitive_keys = ["user_email", "api_key", "credentials"]
    
    for key in sensitive_keys:
        if key in metadata:
            metadata[key] = encrypt(metadata[key])
    
    return json.dumps(metadata)

# Decrypt when returning to authorized requestors
def decrypt_metadata(encrypted: str) -> dict:
    metadata = json.loads(encrypted)
    
    sensitive_keys = ["user_email", "api_key", "credentials"]
    
    for key in sensitive_keys:
        if key in metadata:
            metadata[key] = decrypt(metadata[key])
    
    return metadata
```

### Access Control

```python
def check_receipt_ownership(receipt_id: str, ai_name: str):
    """Verify AI owns this receipt before allowing access."""
    receipt = db.query("""
        SELECT recipient_ai FROM receipts
        WHERE receipt_id = ?
    """, receipt_id)
    
    if not receipt:
        raise NotFoundError("Receipt not found")
    
    if receipt.recipient_ai != ai_name:
        raise ForbiddenError("You do not own this receipt")
```

---

## Implementation Checklist

- [ ] Database schema deployed (receipts table + indexes)
- [ ] Internal API endpoint (/internal/receipt)
- [ ] Service token system (generation, validation, rotation)
- [ ] Automatic pairing logic
- [ ] Enhanced memory_bootstrap() tool
- [ ] New inbox management tools (get/read/archive)
- [ ] External audit API (/external/receipt-chain, /external/work-in-flight)
- [ ] Rate limiting (per source_system)
- [ ] Monitoring & metrics (Prometheus)
- [ ] Health check endpoint
- [ ] Archiving cron job
- [ ] Cold storage export
- [ ] Security (encryption, access control)
- [ ] Integration testing with AsyncGate
- [ ] Load testing (1000+ receipts/sec)
- [ ] Documentation for component integration

---

*Implementation spec documented: 2026-01-04*  
*Purpose: Define MemoryGate's role as receipt store*  
*See receipt_protocol.md for universal receipt specification*