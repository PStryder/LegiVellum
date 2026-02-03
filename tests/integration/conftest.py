"""Integration test fixtures for LegiVellum problemata."""
import os
import sys
from pathlib import Path
from importlib.util import module_from_spec, spec_from_file_location

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/legivellum_test",
)

ALICE_KEY = "dev-key-alice"
BOB_KEY = "dev-key-bob"

def _strip_sql_comments(schema_sql: str) -> str:
    """Remove full-line SQL comments for naive statement splitting."""
    lines = []
    for line in schema_sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_module(module_name: str, file_path: Path, extra_path: Path | None = None):
    if extra_path:
        sys.path.insert(0, str(extra_path))
    spec = spec_from_file_location(module_name, str(file_path))
    module = module_from_spec(spec)
    sys.modules[module_name] = module
    if spec.loader is None:
        raise RuntimeError(f"Failed to load module: {file_path}")
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session", autouse=True)
def _set_integration_env():
    os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
    os.environ.setdefault("ENABLE_METRICS", "false")
    os.environ.setdefault("MEMORYGATE_URL", "http://memorygate.test")
    os.environ.setdefault("ASYNCGATE_URL", "http://asyncgate.test")
    os.environ.setdefault("LEGIVELLUM_TENANT_ID", "alice")

    root = _repo_root()
    shared_path = root / "shared"
    if str(shared_path) not in sys.path:
        sys.path.insert(0, str(shared_path))


@pytest_asyncio.fixture(scope="session")
async def integration_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, pool_pre_ping=True)
    schema_path = _repo_root() / "schema" / "init.sql"
    schema_sql = _strip_sql_comments(schema_path.read_text(encoding="utf-8"))
    try:
        async with engine.begin() as conn:
            for table in ("receipts", "tasks", "plans", "workers"):
                await conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
            for statement in schema_sql.split(";"):
                stmt = statement.strip()
                if not stmt:
                    continue
                await conn.execute(text(stmt))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"Integration database unavailable: {exc}")

    from legivellum.database import init_database, close_database
    init_database(TEST_DATABASE_URL)

    yield engine

    await close_database()
    await engine.dispose()


@pytest_asyncio.fixture
async def integration_session(integration_engine) -> AsyncSession:
    session_maker = async_sessionmaker(integration_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(autouse=True)
async def cleanup_database(integration_session: AsyncSession):
    for table in ("receipts", "tasks", "plans", "workers"):
        try:
            await integration_session.execute(text(f"DELETE FROM {table}"))
        except Exception:
            pass
    await integration_session.commit()

    yield
    for table in ("receipts", "tasks", "plans", "workers"):
        try:
            await integration_session.execute(text(f"DELETE FROM {table}"))
        except Exception:
            pass
    await integration_session.commit()


@pytest.fixture
def auth_headers():
    return {"X-API-Key": ALICE_KEY}


@pytest.fixture
def auth_headers_bob():
    return {"X-API-Key": BOB_KEY}


@pytest.fixture
def tenant_id():
    return "alice"


@pytest.fixture(scope="session")
def memorygate_mcp():
    root = _repo_root()
    module = _load_module(
        "memorygate_mcp",
        root / "components" / "memorygate" / "src" / "mcp_server.py",
        root / "components" / "memorygate" / "src",
    )
    return module


@pytest.fixture(scope="session")
def asyncgate_mcp(memorygate_mcp):
    root = _repo_root()
    asyncgate_src = root / "components" / "asyncgate" / "src"
    module = _load_module(
        "asyncgate_mcp",
        asyncgate_src / "mcp_server.py",
        asyncgate_src,
    )
    return module


@pytest.fixture(autouse=True)
def _patch_asyncgate_receipts(asyncgate_mcp, memorygate_mcp, monkeypatch):
    async def _submit(receipt_data: dict):
        result = await memorygate_mcp.memory_submit_receipt(receipt_data)
        if "error" in result and result["error"] != "duplicate_receipt_id":
            raise RuntimeError(result)
        return result["receipt_id"]

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
        caused_by_receipt_id: str | None,
        parent_task_id: str | None,
        created_at,
    ) -> str:
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
        return await _submit(receipt_data)

    async def _emit_complete_receipt(
        tenant_id: str,
        task_row: dict,
        status: str,
        outcome_kind: str,
        outcome_text: str,
        artifact_pointer: str | None,
        artifact_location: str | None,
        artifact_mime: str | None,
        artifact_checksum: str | None,
        artifact_size_bytes: int,
        completed_at,
    ) -> str:
        import ulid
        import json

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
        return await _submit(receipt_data)

    async def _emit_escalate_receipt(
        tenant_id: str,
        task_row: dict,
        reason: str,
        escalation_class: str,
    ) -> str:
        import ulid
        import json

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
        return await _submit(receipt_data)

    monkeypatch.setattr(asyncgate_mcp, "_emit_receipt", _emit_receipt)
    monkeypatch.setattr(asyncgate_mcp, "_emit_complete_receipt", _emit_complete_receipt)
    monkeypatch.setattr(asyncgate_mcp, "_emit_escalate_receipt", _emit_escalate_receipt)
