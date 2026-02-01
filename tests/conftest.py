"""
Pytest Configuration and Shared Fixtures for LegiVellum Tests

Provides test database setup, fixtures, and utilities for integration testing.
"""
import pytest
import pytest_asyncio
import os
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text


# =============================================================================
# Test Database Configuration
# =============================================================================

# Use separate test database
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/legivellum_test"
)

# Test API keys
TEST_TENANT_ID = "test_tenant"
TEST_API_KEY = f"test-key-{TEST_TENANT_ID}"

def _strip_sql_comments(schema_sql: str) -> str:
    """Remove full-line SQL comments for naive statement splitting."""
    lines = []
    for line in schema_sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        lines.append(line)
    return "\n".join(lines)


# =============================================================================
# Async Event Loop
# =============================================================================

@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


# =============================================================================
# Database Fixtures
# =============================================================================

@pytest_asyncio.fixture(scope="session")
async def test_engine():
    """Create test database engine"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
    )

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        await engine.dispose()
        pytest.skip(f"Test database unavailable: {exc}")
    
    yield engine
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="session")
async def test_db_setup(test_engine):
    """Setup test database schema"""
    # Read schema files
    schema_files = [
        "schema/receipts.sql",
        "schema/tasks.sql",
        "schema/plans.sql",
        "schema/workers.sql",
    ]
    
    async with test_engine.begin() as conn:
        for table in ("receipts", "tasks", "plans", "workers"):
            await conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE"))
        for schema_file in schema_files:
            if os.path.exists(schema_file):
                with open(schema_file) as f:
                    schema_sql = _strip_sql_comments(f.read())
                    # Execute schema (skip comments and empty lines)
                    for statement in schema_sql.split(";"):
                        statement = statement.strip()
                        if statement:
                            await conn.execute(text(statement))
    
    yield
    
    # Cleanup after all tests
    async with test_engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS receipts CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS tasks CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS plans CASCADE"))
        await conn.execute(text("DROP TABLE IF EXISTS workers CASCADE"))


@pytest_asyncio.fixture
async def test_session(test_engine, test_db_setup) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session"""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()  # Rollback after each test


@pytest_asyncio.fixture(autouse=True)
async def cleanup_database(test_session):
    """Clean database between tests"""
    yield
    
    # Clean all tables after each test
    await test_session.execute(text("DELETE FROM receipts"))
    await test_session.execute(text("DELETE FROM tasks"))
    await test_session.execute(text("DELETE FROM plans"))
    await test_session.execute(text("DELETE FROM workers"))
    await test_session.commit()


# =============================================================================
# Auth Fixtures
# =============================================================================

@pytest.fixture
def auth_headers():
    """Generate auth headers for test requests"""
    return {
        "X-API-Key": TEST_API_KEY,
    }


@pytest.fixture
def tenant_id():
    """Test tenant ID"""
    return TEST_TENANT_ID


# =============================================================================
# Sample Data Fixtures
# =============================================================================

@pytest.fixture
def sample_receipt_data(tenant_id):
    """Create sample receipt data"""
    from datetime import datetime, timezone
    
    return {
        "tenant_id": tenant_id,
        "schema_version": "1.0",
        "receipt_id": "01JGTEST123456789ABCDEFGHIJ",
        "task_id": "T-01JGTEST123456789ABCDEFGHIJ",
        "parent_task_id": "NA",
        "caused_by_receipt_id": "NA",
        "dedupe_key": "NA",
        "attempt": 0,
        "from_principal": "test@example.com",
        "for_principal": "test@example.com",
        "source_system": "test",
        "recipient_ai": "test_worker",
        "trust_domain": "test",
        "phase": "accepted",
        "status": "NA",
        "realtime": False,
        "task_type": "test.task",
        "task_summary": "Test task",
        "task_body": "Testing receipt storage",
        "inputs": {"test": "data"},
        "expected_outcome_kind": "response_text",
        "expected_artifact_mime": "NA",
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
        "created_at": datetime.now(timezone.utc),
        "metadata": {},
    }


# =============================================================================
# HTTP Client Fixtures
# =============================================================================

@pytest_asyncio.fixture
async def memorygate_client(auth_headers):
    """HTTP client for MemoryGate"""
    from httpx import AsyncClient
    # Note: In actual implementation, this would use TestClient
    # from fastapi.testclient import TestClient
    # from components.memorygate.src.main import app
    # client = TestClient(app)
    return None  # Placeholder


@pytest_asyncio.fixture
async def asyncgate_client(auth_headers):
    """HTTP client for AsyncGate"""
    from httpx import AsyncClient
    return None  # Placeholder


@pytest_asyncio.fixture
async def delegate_client(auth_headers):
    """HTTP client for DeleGate"""
    from httpx import AsyncClient
    return None  # Placeholder


# =============================================================================
# Helper Functions
# =============================================================================

async def create_test_receipt(session: AsyncSession, receipt_data: dict) -> str:
    """Helper to create receipt directly in database"""
    import json
    
    columns = ", ".join(receipt_data.keys())
    placeholders = ", ".join(f":{key}" for key in receipt_data.keys())
    
    # Convert dict fields to JSON
    data = receipt_data.copy()
    if isinstance(data.get("inputs"), dict):
        data["inputs"] = json.dumps(data["inputs"])
    if isinstance(data.get("metadata"), dict):
        data["metadata"] = json.dumps(data["metadata"])
    
    query = text(f"""
        INSERT INTO receipts ({columns})
        VALUES ({placeholders})
        RETURNING receipt_id
    """)
    
    result = await session.execute(query, data)
    await session.commit()
    
    return result.scalar()


async def create_test_task(session: AsyncSession, task_data: dict) -> str:
    """Helper to create task directly in database"""
    import json
    
    defaults = {
        "tenant_id": TEST_TENANT_ID,
        "status": "queued",
        "priority": 0,
        "attempt": 0,
        "max_attempts": 3,
    }
    
    data = {**defaults, **task_data}
    
    # Convert dict fields to JSON
    if isinstance(data.get("inputs"), dict):
        data["inputs"] = json.dumps(data["inputs"])
    
    columns = ", ".join(data.keys())
    placeholders = ", ".join(f":{key}" for key in data.keys())
    
    query = text(f"""
        INSERT INTO tasks ({columns})
        VALUES ({placeholders})
        RETURNING task_id
    """)
    
    result = await session.execute(query, data)
    await session.commit()
    
    return result.scalar()


# =============================================================================
# Pytest Configuration
# =============================================================================

def pytest_configure(config):
    """Configure pytest"""
    config.addinivalue_line(
        "markers",
        "unit: Unit tests (no database required)"
    )
    config.addinivalue_line(
        "markers",
        "integration: Integration tests (require database)"
    )
    config.addinivalue_line(
        "markers",
        "e2e: End-to-end tests (require all services)"
    )


# =============================================================================
# Test Utilities
# =============================================================================

class TestHelpers:
    """Helper methods for tests"""
    
    @staticmethod
    def generate_ulid():
        """Generate test ULID"""
        import ulid
        return str(ulid.new())
    
    @staticmethod
    def generate_task_id():
        """Generate test task ID"""
        import ulid
        return f"T-{str(ulid.new())}"
    
    @staticmethod
    def generate_plan_id():
        """Generate test plan ID"""
        import ulid
        return f"P-{str(ulid.new())}"


@pytest.fixture
def helpers():
    """Provide test helper methods"""
    return TestHelpers()
