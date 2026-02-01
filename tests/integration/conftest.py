"""Integration test fixtures for LegiVellum problemata."""
import os
import sys
from pathlib import Path
from importlib.util import module_from_spec, spec_from_file_location

import pytest
import pytest_asyncio
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/legivellum_test",
)

ALICE_KEY = "dev-key-alice"
BOB_KEY = "dev-key-bob"


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


@pytest_asyncio.fixture(scope="session")
async def integration_engine():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, pool_pre_ping=True)
    schema_path = _repo_root() / "schema" / "init.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")
    try:
        async with engine.begin() as conn:
            for statement in schema_sql.split(";"):
                stmt = statement.strip()
                if not stmt or stmt.startswith("--"):
                    continue
                await conn.execute(text(stmt))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"Integration database unavailable: {exc}")

    yield engine

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
def memorygate_app():
    root = _repo_root()
    module = _load_module(
        "memorygate_main",
        root / "components" / "memorygate" / "src" / "main.py",
        root / "components" / "memorygate" / "src",
    )
    return module.app


@pytest.fixture(scope="session")
def asyncgate_app(memorygate_app):
    root = _repo_root()
    asyncgate_src = root / "components" / "asyncgate" / "src"
    module = _load_module(
        "asyncgate_main",
        asyncgate_src / "main.py",
        asyncgate_src,
    )

    import receipt_emitter

    async def _noop_worker(*args, **kwargs):
        return None

    async def _emit_receipt_with_retry(memorygate_url, tenant_id, receipt_data, max_retries=3, timeout=10.0):
        receipt_id = receipt_data["receipt_id"]
        transport = httpx.ASGITransport(app=memorygate_app)
        async with httpx.AsyncClient(transport=transport, base_url=memorygate_url) as client:
            response = await client.post(
                "/receipts",
                json=receipt_data,
                headers={"X-API-Key": f"dev-key-{tenant_id}"},
                timeout=timeout,
            )
        if response.status_code == 409:
            return receipt_id
        response.raise_for_status()
        return receipt_id

    module.lease_expiry_worker = _noop_worker
    receipt_emitter.retry_worker = _noop_worker
    receipt_emitter.stop_retry_worker = lambda: None
    receipt_emitter.emit_receipt_with_retry = _emit_receipt_with_retry

    return module.app


@pytest_asyncio.fixture(scope="session")
async def memorygate_client(memorygate_app, integration_engine):
    transport = httpx.ASGITransport(app=memorygate_app, lifespan="on")
    async with httpx.AsyncClient(transport=transport, base_url="http://memorygate.test") as client:
        yield client


@pytest_asyncio.fixture(scope="session")
async def asyncgate_client(asyncgate_app, integration_engine):
    transport = httpx.ASGITransport(app=asyncgate_app, lifespan="on")
    async with httpx.AsyncClient(transport=transport, base_url="http://asyncgate.test") as client:
        yield client
