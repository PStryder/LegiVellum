"""
Problemata control architecture scaffolding for LegiVellum.

This module provides:
- A blueprint compiler (GUI-friendly) that emits a problemata spec
- Validation orchestration via the canonical atomic validator
- In-memory and Postgres-backed repositories for create/list/get flows
- Topology diagnostics for edge-level feedback in the GUI
"""

from __future__ import annotations

import copy
import hashlib
import os
import re
import threading
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Optional, Protocol

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from .database import create_engine, get_database_url

from .problemata_validation import (
    ProblemataValidationResult,
    ValidationContext,
    validate_problemata_spec,
)


class ProblemataStatus(str, Enum):
    """Lifecycle state tracked by the control service."""

    VALIDATED = "validated"
    REJECTED = "rejected"


class ProblemataDiagnosticsStatus(str, Enum):
    """Diagnostic severity for topology edges."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


class ProblemataBlueprint(BaseModel):
    """GUI-oriented input model for generating a Problemata spec."""

    problemata_id: str = Field(..., min_length=3)
    version: str = Field(default="0.1.0", min_length=1)
    tenant_id: str = Field(..., min_length=1)
    owner_principal: str = Field(..., min_length=1)
    description: Optional[str] = None
    endpoint_base: str = Field(default="http://localhost")
    trust_domain: str = Field(default="default", min_length=1)
    include_asyncgate: bool = True
    include_cognigate: bool = False
    include_delegategate: bool = False
    include_interrogate: bool = True
    include_interview: bool = False
    include_memorygate: bool = True
    receipt_schema_version: str = Field(default="1.0")
    depot_default_sink: str = Field(default="filesystem")
    cgn_model: str = Field(default="anthropic/claude-3-opus")
    dlg_model: str = Field(default="gpt-4.1")
    interrogate_policy_profile_id: str = Field(default="default-policy")
    async_lease_ttl_seconds: int = Field(default=300, ge=1)
    async_max_attempts: int = Field(default=3, ge=1)
    async_retry_backoff_seconds: int = Field(default=15, ge=1)

    @field_validator("endpoint_base")
    @classmethod
    def validate_endpoint_base(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("endpoint_base must start with http:// or https://")
        return value.rstrip("/")


class ProblemataRecord(BaseModel):
    """Stored control-plane record for a spec submission."""

    problemata_id: str
    version: str
    status: ProblemataStatus
    source: str
    created_at: datetime
    spec_hash: Optional[str] = None
    validation: ProblemataValidationResult
    spec: dict[str, Any]


class ProblemataTopologyNode(BaseModel):
    """Derived topology node details for visualization."""

    primitive_id: str
    primitive_type: str
    inbound_edges: int
    outbound_edges: int


class ProblemataEdgeDiagnostic(BaseModel):
    """Edge-level topology diagnostic information."""

    index: int
    from_id: Optional[str] = None
    to_id: Optional[str] = None
    purpose: Optional[str] = None
    protocol: Optional[str] = None
    trust_domain: Optional[str] = None
    status: ProblemataDiagnosticsStatus
    messages: list[str] = Field(default_factory=list)


class ProblemataDiagnosticsResult(BaseModel):
    """Diagnostics envelope used by the control UI."""

    validation: ProblemataValidationResult
    nodes: list[ProblemataTopologyNode]
    edges: list[ProblemataEdgeDiagnostic]
    global_messages: list[str] = Field(default_factory=list)


class ProblemataRepository(Protocol):
    """Synchronous repository protocol for control service."""

    def upsert(self, record: ProblemataRecord) -> ProblemataRecord:
        ...

    def get(self, problemata_id: str) -> Optional[ProblemataRecord]:
        ...

    def list(self) -> list[ProblemataRecord]:
        ...


class InMemoryProblemataRepository:
    """Thread-safe in-memory repository for early control-plane development."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records_by_id: dict[str, ProblemataRecord] = {}
        self._order: list[str] = []

    def upsert(self, record: ProblemataRecord) -> ProblemataRecord:
        with self._lock:
            if record.problemata_id not in self._records_by_id:
                self._order.append(record.problemata_id)
            self._records_by_id[record.problemata_id] = record
            return record

    def get(self, problemata_id: str) -> Optional[ProblemataRecord]:
        with self._lock:
            record = self._records_by_id.get(problemata_id)
            return copy.deepcopy(record) if record else None

    def list(self) -> list[ProblemataRecord]:
        with self._lock:
            return [copy.deepcopy(self._records_by_id[item_id]) for item_id in self._order]


class ProblemataControlService:
    """Application service for Problemata preview/validate/create operations."""

    def __init__(
        self,
        *,
        repository: Optional[ProblemataRepository] = None,
        validated_by: str = "legivellum.control-plane",
    ) -> None:
        self._repository = repository or InMemoryProblemataRepository()
        self._validated_by = validated_by

    def preview_from_blueprint(self, blueprint: ProblemataBlueprint) -> dict[str, Any]:
        """Compile a blueprint into a draft problemata spec."""
        return compile_problemata_blueprint(blueprint)

    def validate_spec(self, spec: dict[str, Any]) -> ProblemataValidationResult:
        """Run canonical atomic validation (multi-error mode for UX diagnostics)."""
        return validate_problemata_spec(
            spec,
            fail_fast=False,
            context=ValidationContext(validated_by=self._validated_by),
        )

    def register_spec(self, spec: dict[str, Any], *, source: str) -> ProblemataRecord:
        """Validate and register a spec submission."""
        validation = self.validate_spec(spec)
        record = _build_problemata_record(spec=spec, source=source, validation=validation)
        return self._repository.upsert(record)

    def update_spec(self, problemata_id: str, spec: dict[str, Any], *, source: str) -> ProblemataRecord:
        """Update an existing problemata spec by id (upsert semantics)."""
        normalized_spec = _normalize_spec_for_update(problemata_id=problemata_id, spec=spec)
        return self.register_spec(normalized_spec, source=source)

    def create_from_blueprint(self, blueprint: ProblemataBlueprint) -> ProblemataRecord:
        """Compile + validate + register a blueprint."""
        spec = self.preview_from_blueprint(blueprint)
        return self.register_spec(spec, source="blueprint")

    def get(self, problemata_id: str) -> Optional[ProblemataRecord]:
        return self._repository.get(problemata_id)

    def list(self) -> list[ProblemataRecord]:
        return self._repository.list()

    def diagnose_spec(self, spec: dict[str, Any]) -> ProblemataDiagnosticsResult:
        """Validate and produce topology diagnostics for UI edge inspection."""
        validation = self.validate_spec(spec)
        return _build_topology_diagnostics(spec=spec, validation=validation)


class AsyncProblemataRepository(Protocol):
    """Asynchronous repository protocol for control service."""

    async def upsert(self, record: ProblemataRecord) -> ProblemataRecord:
        ...

    async def get(self, problemata_id: str) -> Optional[ProblemataRecord]:
        ...

    async def list(self) -> list[ProblemataRecord]:
        ...


class AsyncProblemataControlService:
    """Async service for Problemata workflows backed by async repositories."""

    def __init__(
        self,
        *,
        repository: AsyncProblemataRepository,
        validated_by: str = "legivellum.control-plane",
    ) -> None:
        self._repository = repository
        self._validated_by = validated_by

    def preview_from_blueprint(self, blueprint: ProblemataBlueprint) -> dict[str, Any]:
        return compile_problemata_blueprint(blueprint)

    def validate_spec(self, spec: dict[str, Any]) -> ProblemataValidationResult:
        return validate_problemata_spec(
            spec,
            fail_fast=False,
            context=ValidationContext(validated_by=self._validated_by),
        )

    async def register_spec(self, spec: dict[str, Any], *, source: str) -> ProblemataRecord:
        validation = self.validate_spec(spec)
        record = _build_problemata_record(spec=spec, source=source, validation=validation)
        return await self._repository.upsert(record)

    async def update_spec(self, problemata_id: str, spec: dict[str, Any], *, source: str) -> ProblemataRecord:
        normalized_spec = _normalize_spec_for_update(problemata_id=problemata_id, spec=spec)
        return await self.register_spec(normalized_spec, source=source)

    async def create_from_blueprint(self, blueprint: ProblemataBlueprint) -> ProblemataRecord:
        spec = self.preview_from_blueprint(blueprint)
        return await self.register_spec(spec, source="blueprint")

    async def get(self, problemata_id: str) -> Optional[ProblemataRecord]:
        return await self._repository.get(problemata_id)

    async def list(self) -> list[ProblemataRecord]:
        return await self._repository.list()

    def diagnose_spec(self, spec: dict[str, Any]) -> ProblemataDiagnosticsResult:
        validation = self.validate_spec(spec)
        return _build_topology_diagnostics(spec=spec, validation=validation)


class PostgresProblemataRepository:
    """Postgres-backed Problemata repository with SQL migration support."""

    def __init__(
        self,
        *,
        database_url: Optional[str] = None,
        auto_migrate: bool = True,
        migrations_dir: Optional[Path] = None,
        engine: Optional[AsyncEngine] = None,
    ) -> None:
        self._database_url = database_url or get_database_url()
        self._auto_migrate = auto_migrate
        self._migrations_dir = migrations_dir
        self._engine = engine
        self._session_factory: Optional[async_sessionmaker[AsyncSession]] = None
        self._owns_engine = engine is None

    async def startup(self) -> None:
        """Initialize engine/session factory and apply migrations if enabled."""
        if self._engine is None:
            self._engine = create_engine(self._database_url)
        if self._session_factory is None:
            self._session_factory = async_sessionmaker(
                self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
        if self._auto_migrate:
            await apply_problemata_migrations(self._engine, migrations_dir=self._migrations_dir)

    async def shutdown(self) -> None:
        """Dispose engine if this repository created it."""
        if self._engine is not None and self._owns_engine:
            await self._engine.dispose()
        self._engine = None
        self._session_factory = None

    async def _ensure_ready(self) -> None:
        if self._session_factory is None:
            await self.startup()

    async def upsert(self, record: ProblemataRecord) -> ProblemataRecord:
        await self._ensure_ready()
        assert self._session_factory is not None
        query = text(
            """
            INSERT INTO problemata_registry (
                problemata_id,
                version,
                status,
                source,
                created_at,
                updated_at,
                spec_hash,
                validation,
                spec
            ) VALUES (
                :problemata_id,
                :version,
                :status,
                :source,
                :created_at,
                :updated_at,
                :spec_hash,
                :validation,
                :spec
            )
            ON CONFLICT (problemata_id)
            DO UPDATE SET
                version = EXCLUDED.version,
                status = EXCLUDED.status,
                source = EXCLUDED.source,
                updated_at = EXCLUDED.updated_at,
                spec_hash = EXCLUDED.spec_hash,
                validation = EXCLUDED.validation,
                spec = EXCLUDED.spec
            RETURNING problemata_id, version, status, source, created_at, spec_hash, validation, spec
            """
        ).bindparams(
            # Without an explicit type the asyncpg dialect hands the raw dict to
            # its jsonb encoder, which expects an already-serialized string.
            bindparam("validation", type_=JSONB),
            bindparam("spec", type_=JSONB),
        )
        params = {
            "problemata_id": record.problemata_id,
            "version": record.version,
            "status": record.status.value,
            "source": record.source,
            "created_at": record.created_at,
            "updated_at": datetime.now(timezone.utc),
            "spec_hash": record.spec_hash,
            "validation": record.validation.model_dump(mode="json"),
            "spec": record.spec,
        }
        async with self._session_factory() as session:
            result = await session.execute(query, params)
            row = result.mappings().one()
            await session.commit()
        return _record_from_mapping(row)

    async def get(self, problemata_id: str) -> Optional[ProblemataRecord]:
        await self._ensure_ready()
        assert self._session_factory is not None
        query = text(
            """
            SELECT
                problemata_id,
                version,
                status,
                source,
                created_at,
                spec_hash,
                validation,
                spec
            FROM problemata_registry
            WHERE problemata_id = :problemata_id
            """
        )
        async with self._session_factory() as session:
            result = await session.execute(query, {"problemata_id": problemata_id})
            row = result.mappings().first()
        if row is None:
            return None
        return _record_from_mapping(row)

    async def list(self) -> list[ProblemataRecord]:
        await self._ensure_ready()
        assert self._session_factory is not None
        query = text(
            """
            SELECT
                problemata_id,
                version,
                status,
                source,
                created_at,
                spec_hash,
                validation,
                spec
            FROM problemata_registry
            ORDER BY created_at ASC, problemata_id ASC
            """
        )
        async with self._session_factory() as session:
            result = await session.execute(query)
            rows = result.mappings().all()
        return [_record_from_mapping(row) for row in rows]


MIGRATION_COMPONENT = "problemata_control"
MIGRATIONS_TABLE = "legivellum_schema_migrations"


def resolve_problemata_migrations_dir() -> Path:
    """Resolve default migration directory for Problemata control storage."""
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / "schema" / "migrations" / "problemata_control"


async def apply_problemata_migrations(
    engine: AsyncEngine,
    *,
    migrations_dir: Optional[Path] = None,
) -> None:
    """Apply SQL migrations for Problemata registry table."""
    resolved_dir = Path(migrations_dir) if migrations_dir else resolve_problemata_migrations_dir()
    if not resolved_dir.exists():
        raise FileNotFoundError(f"Problemata migrations directory not found: {resolved_dir}")

    migration_files = sorted(path for path in resolved_dir.glob("*.sql") if path.is_file())
    async with engine.begin() as connection:
        await connection.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} (
                    component TEXT NOT NULL,
                    version TEXT NOT NULL,
                    checksum TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (component, version)
                )
                """
            )
        )

    for migration_file in migration_files:
        match = re.match(r"^(\d+)_", migration_file.name)
        if match is None:
            raise ValueError(f"Invalid migration filename (missing numeric prefix): {migration_file.name}")

        version = match.group(1)
        sql_payload = migration_file.read_text(encoding="utf-8")
        checksum = hashlib.sha256(sql_payload.encode("utf-8")).hexdigest()

        async with engine.begin() as connection:
            existing_checksum_result = await connection.execute(
                text(
                    f"""
                    SELECT checksum
                    FROM {MIGRATIONS_TABLE}
                    WHERE component = :component AND version = :version
                    """
                ),
                {"component": MIGRATION_COMPONENT, "version": version},
            )
            existing_checksum = existing_checksum_result.scalar_one_or_none()
            if existing_checksum is not None:
                if existing_checksum != checksum:
                    raise RuntimeError(
                        "Applied migration checksum mismatch for "
                        f"{migration_file.name}: expected {existing_checksum}, got {checksum}"
                    )
                continue

            for statement in _split_sql_statements(sql_payload):
                await connection.execute(text(statement))

            await connection.execute(
                text(
                    f"""
                    INSERT INTO {MIGRATIONS_TABLE} (component, version, checksum)
                    VALUES (:component, :version, :checksum)
                    """
                ),
                {"component": MIGRATION_COMPONENT, "version": version, "checksum": checksum},
            )


def create_default_postgres_problemata_service(
    *,
    database_url: Optional[str] = None,
    auto_migrate: Optional[bool] = None,
) -> tuple[AsyncProblemataControlService, PostgresProblemataRepository]:
    """Create default async control service configured for Postgres persistence."""
    resolved_auto_migrate = auto_migrate
    if resolved_auto_migrate is None:
        resolved_auto_migrate = os.environ.get("PROBLEMATA_AUTO_MIGRATE", "true").lower() == "true"

    repository = PostgresProblemataRepository(
        database_url=database_url or os.environ.get("PROBLEMATA_DATABASE_URL") or get_database_url(),
        auto_migrate=resolved_auto_migrate,
    )
    service = AsyncProblemataControlService(repository=repository)
    return service, repository


def compile_problemata_blueprint(blueprint: ProblemataBlueprint) -> dict[str, Any]:
    """
    Compile a GUI blueprint into a problemata spec.

    The output is intentionally explicit and validator-friendly:
    - Required primitives are always present (MetaGate, ReceiptGate, DepotGate)
    - Required bootstrap / receipt / artifact routes are emitted
    - Optional primitives are toggled by blueprint flags
    """

    primitive_ids = {
        "metagate": "metagate-main",
        "receiptgate": "receiptgate-main",
        "depotgate": "depotgate-main",
        "asyncgate": "asyncgate-main",
        "cognigate": "cognigate-main",
        "delegategate": "delegategate-main",
        "interrogate": "interrogate-main",
        "interview": "interview-main",
        "memorygate": "memorygate-main",
    }

    def endpoint(name: str) -> str:
        return f"{blueprint.endpoint_base}/{name}/mcp"

    primitives: dict[str, dict[str, Any]] = {
        primitive_ids["metagate"]: {
            "type": "metagate",
            "endpoint": endpoint("metagate"),
            "config": {},
        },
        primitive_ids["receiptgate"]: {
            "type": "receiptgate",
            "endpoint": endpoint("receiptgate"),
            "config": {
                "receipt_schema_version": blueprint.receipt_schema_version,
                "auth_ref": "secrets/receiptgate_token",
            },
        },
        primitive_ids["depotgate"]: {
            "type": "depotgate",
            "endpoint": endpoint("depotgate"),
            "config": {
                "default_sink": blueprint.depot_default_sink,
                "auth_ref": "secrets/depotgate_token",
                "allowed_mime_types": ["text/plain", "application/json"],
                "max_artifact_size_mb": 25,
            },
        },
    }

    if blueprint.include_memorygate:
        primitives[primitive_ids["memorygate"]] = {
            "type": "memorygate",
            "endpoint": endpoint("memorygate"),
            "config": {"receiptgate_ref": primitive_ids["receiptgate"]},
        }

    if blueprint.include_asyncgate:
        primitives[primitive_ids["asyncgate"]] = {
            "type": "asyncgate",
            "endpoint": endpoint("asyncgate"),
            "config": {
                "lease_ttl_seconds": blueprint.async_lease_ttl_seconds,
                "max_attempts": blueprint.async_max_attempts,
                "retry_backoff_seconds": blueprint.async_retry_backoff_seconds,
                "receipt_mode": "receiptgate_integrated",
                "receiptgate_ref": primitive_ids["receiptgate"],
            },
        }

    if blueprint.include_cognigate:
        primitives[primitive_ids["cognigate"]] = {
            "type": "cognigate",
            "endpoint": endpoint("cognigate"),
            "config": {
                "ai": {
                    "endpoint": "https://openrouter.ai/api/v1",
                    "model": blueprint.cgn_model,
                    "api_key_ref": "secrets/cognigate_api_key",
                },
                "profile_ref": "profiles/default-cognition.yaml",
                "receiptgate_ref": primitive_ids["receiptgate"],
                "depotgate_ref": primitive_ids["depotgate"],
            },
        }

    if blueprint.include_delegategate:
        primitives[primitive_ids["delegategate"]] = {
            "type": "delegategate",
            "endpoint": endpoint("delegategate"),
            "config": {
                "planner": {
                    "model": blueprint.dlg_model,
                    "api_key_ref": "secrets/delegategate_api_key",
                },
                "plan_store_ref": primitive_ids["depotgate"],
                "receiptgate_ref": primitive_ids["receiptgate"],
                "depotgate_ref": primitive_ids["depotgate"],
            },
        }

    if blueprint.include_interrogate:
        primitives[primitive_ids["interrogate"]] = {
            "type": "interrogate",
            "endpoint": endpoint("interrogate"),
            "config": {
                "policy_profile_id": blueprint.interrogate_policy_profile_id,
                "metagate_ref": primitive_ids["metagate"],
                "receiptgate_ref": primitive_ids["receiptgate"],
                "memorygate_ref": primitive_ids["memorygate"] if blueprint.include_memorygate else None,
                "problemata_id": blueprint.problemata_id,
                "sync_timeout_ms": 15_000,
            },
        }

    if blueprint.include_interview:
        primitives[primitive_ids["interview"]] = {
            "type": "interview",
            "endpoint": endpoint("interview"),
            "config": {
                "allowed_sources": [
                    "projection_cache",
                    "ledger_mirror",
                    "component_poll",
                ],
                "rate_limits": {"requests_per_minute": 120},
            },
        }

    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()

    def add_edge(source: str, target: str, purpose: str) -> None:
        edge_key = (source, target, purpose)
        if edge_key in seen_edges:
            return
        seen_edges.add(edge_key)
        edges.append(
            {
                "from": source,
                "to": target,
                "purpose": purpose,
                "protocol": "mcp",
                "trust_domain": blueprint.trust_domain,
            }
        )

    metagate_id = primitive_ids["metagate"]
    receiptgate_id = primitive_ids["receiptgate"]
    depotgate_id = primitive_ids["depotgate"]

    for primitive_id in primitives:
        if primitive_id == metagate_id:
            continue
        add_edge(primitive_id, metagate_id, "bootstrap")

    receipt_emitters = [
        primitive_ids["asyncgate"],
        primitive_ids["cognigate"],
        primitive_ids["delegategate"],
        primitive_ids["interrogate"],
    ]
    for primitive_id in receipt_emitters:
        if primitive_id in primitives:
            add_edge(primitive_id, receiptgate_id, "receipt_emit")

    artifact_emitters = [
        primitive_ids["asyncgate"],
        primitive_ids["cognigate"],
        primitive_ids["delegategate"],
    ]
    for primitive_id in artifact_emitters:
        if primitive_id in primitives:
            add_edge(primitive_id, depotgate_id, "artifact_store")

    if primitive_ids["delegategate"] in primitives:
        add_edge(primitive_ids["delegategate"], depotgate_id, "plan_store")

    if primitive_ids["interrogate"] in primitives and primitive_ids["asyncgate"] in primitives:
        add_edge(primitive_ids["interrogate"], primitive_ids["asyncgate"], "lease")

    if primitive_ids["interview"] in primitives:
        add_edge(primitive_ids["interview"], receiptgate_id, "observe")
        if primitive_ids["memorygate"] in primitives:
            add_edge(primitive_ids["interview"], primitive_ids["memorygate"], "observe")

    return {
        "problemata": {
            "id": blueprint.problemata_id,
            "version": blueprint.version,
            "tenant_id": blueprint.tenant_id,
            "owner_principal": blueprint.owner_principal,
            "description": blueprint.description or f"Problemata {blueprint.problemata_id}",
            "labels": {
                "generated_by": "legivellum.problemata_control",
                "mode": "blueprint",
            },
            "defaults": {
                "receiptgate_ref": receiptgate_id,
                "depotgate_ref": depotgate_id,
                "trust_domain": blueprint.trust_domain,
            },
        },
        "primitives": primitives,
        "topology": edges,
        "policies": {
            "trust_domain": blueprint.trust_domain,
            "rate_limits": {"global_requests_per_minute": 300},
        },
    }


def _extract_problemata_id(spec: dict[str, Any]) -> str:
    problemata = spec.get("problemata")
    if isinstance(problemata, dict):
        value = problemata.get("id")
        if isinstance(value, str) and value.strip():
            return value
    return "unknown-problemata"


def _extract_problemata_version(spec: dict[str, Any]) -> str:
    problemata = spec.get("problemata")
    if isinstance(problemata, dict):
        value = problemata.get("version")
        if isinstance(value, str) and value.strip():
            return value
    return "0.0.0"


def _build_problemata_record(
    *,
    spec: dict[str, Any],
    source: str,
    validation: ProblemataValidationResult,
) -> ProblemataRecord:
    problemata_id = _extract_problemata_id(spec)
    version = _extract_problemata_version(spec)
    status = ProblemataStatus.VALIDATED if validation.status == "passed" else ProblemataStatus.REJECTED
    return ProblemataRecord(
        problemata_id=problemata_id,
        version=version,
        status=status,
        source=source,
        created_at=datetime.now(timezone.utc),
        spec_hash=validation.spec_hash,
        validation=validation,
        spec=copy.deepcopy(spec),
    )


def _normalize_spec_for_update(problemata_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    normalized = copy.deepcopy(spec)
    problemata = normalized.get("problemata")
    if not isinstance(problemata, dict):
        problemata = {}
        normalized["problemata"] = problemata
    existing_id = problemata.get("id")
    if isinstance(existing_id, str) and existing_id.strip() and existing_id != problemata_id:
        raise ValueError(
            f"Spec problemata.id ({existing_id}) does not match requested id ({problemata_id})"
        )
    problemata["id"] = problemata_id
    return normalized


def _record_from_mapping(row: Mapping[str, Any]) -> ProblemataRecord:
    validation = ProblemataValidationResult.model_validate(row["validation"])
    return ProblemataRecord(
        problemata_id=str(row["problemata_id"]),
        version=str(row["version"]),
        status=ProblemataStatus(str(row["status"])),
        source=str(row["source"]),
        created_at=row["created_at"],
        spec_hash=row.get("spec_hash"),
        validation=validation,
        spec=copy.deepcopy(dict(row["spec"])),
    )


def _split_sql_statements(sql_payload: str) -> list[str]:
    lines: list[str] = []
    for line in sql_payload.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)

    statements: list[str] = []
    current: list[str] = []
    in_single_quote = False
    previous_char = ""
    for char in cleaned:
        if char == "'" and previous_char != "\\":
            in_single_quote = not in_single_quote
        if char == ";" and not in_single_quote:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
        else:
            current.append(char)
        previous_char = char

    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def _build_topology_diagnostics(
    *,
    spec: dict[str, Any],
    validation: ProblemataValidationResult,
) -> ProblemataDiagnosticsResult:
    primitives = spec.get("primitives")
    topology = spec.get("topology")
    primitive_map = primitives if isinstance(primitives, dict) else {}
    edges = topology if isinstance(topology, list) else []

    inbound_counts: dict[str, int] = {primitive_id: 0 for primitive_id in primitive_map}
    outbound_counts: dict[str, int] = {primitive_id: 0 for primitive_id in primitive_map}
    diagnostics: list[ProblemataEdgeDiagnostic] = []

    for idx, edge in enumerate(edges):
        from_id = edge.get("from") if isinstance(edge, dict) else None
        to_id = edge.get("to") if isinstance(edge, dict) else None
        purpose = edge.get("purpose") if isinstance(edge, dict) else None
        protocol = edge.get("protocol") if isinstance(edge, dict) else None
        trust_domain = edge.get("trust_domain") if isinstance(edge, dict) else None

        if isinstance(from_id, str) and from_id in outbound_counts:
            outbound_counts[from_id] += 1
        if isinstance(to_id, str) and to_id in inbound_counts:
            inbound_counts[to_id] += 1

        diagnostics.append(
            ProblemataEdgeDiagnostic(
                index=idx,
                from_id=from_id if isinstance(from_id, str) else None,
                to_id=to_id if isinstance(to_id, str) else None,
                purpose=purpose if isinstance(purpose, str) else None,
                protocol=protocol if isinstance(protocol, str) else None,
                trust_domain=trust_domain if isinstance(trust_domain, str) else None,
                status=ProblemataDiagnosticsStatus.OK,
                messages=[],
            )
        )

    global_messages: list[str] = []
    path_index_pattern = re.compile(r"^topology\[(\d+)\]")
    path_source_pattern = re.compile(r"^topology\.([^.]+)$")

    for error in validation.errors:
        assigned = False
        index_match = path_index_pattern.match(error.path)
        if index_match:
            edge_index = int(index_match.group(1))
            if 0 <= edge_index < len(diagnostics):
                diagnostics[edge_index].messages.append(f"{error.code}: {error.message}")
                diagnostics[edge_index].status = ProblemataDiagnosticsStatus.ERROR
                assigned = True

        if assigned:
            continue

        source_match = path_source_pattern.match(error.path)
        if source_match:
            source_id = source_match.group(1)
            matched_any = False
            for edge in diagnostics:
                if edge.from_id == source_id:
                    edge.messages.append(f"{error.code}: {error.message}")
                    edge.status = ProblemataDiagnosticsStatus.ERROR
                    matched_any = True
            if matched_any:
                assigned = True

        if assigned:
            continue

        if error.path.startswith("topology"):
            global_messages.append(f"{error.code}: {error.message}")

    for edge in diagnostics:
        if edge.status == ProblemataDiagnosticsStatus.ERROR:
            continue
        if edge.protocol and edge.protocol.strip().lower() != "mcp":
            edge.status = ProblemataDiagnosticsStatus.WARNING
            edge.messages.append("Protocol is not MCP.")
        if edge.from_id == edge.to_id and edge.from_id is not None:
            edge.status = ProblemataDiagnosticsStatus.WARNING
            edge.messages.append("Self-loop edge detected.")

    nodes: list[ProblemataTopologyNode] = []
    for primitive_id, primitive in primitive_map.items():
        primitive_type = ""
        if isinstance(primitive, dict):
            primitive_type = str(primitive.get("type") or "")
        nodes.append(
            ProblemataTopologyNode(
                primitive_id=primitive_id,
                primitive_type=primitive_type,
                inbound_edges=inbound_counts.get(primitive_id, 0),
                outbound_edges=outbound_counts.get(primitive_id, 0),
            )
        )

    return ProblemataDiagnosticsResult(
        validation=validation,
        nodes=nodes,
        edges=diagnostics,
        global_messages=global_messages,
    )
