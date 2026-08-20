"""Pytest configuration and shared fixtures for LegiVellum tests.

LegiVellum runs no database. It is the protocol package and the Problemata
control plane; storage belongs to the gates, each of which owns its own.

This file used to build a database containing `receipts`, `tasks`, `plans` and
`workers` -- ReceiptGate's, AsyncGate's and DeleGate's tables -- from DDL in
`schema/`, left over from when LegiVellum was one service. No test ever
requested those fixtures, and one of the files they loaded had not existed for
some time.
"""
import pytest
import pytest_asyncio
import asyncio
from typing import Generator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


# =============================================================================
# Test Database Configuration
# =============================================================================


# Test API keys
TEST_TENANT_ID = "test_tenant"
TEST_API_KEY = f"test-key-{TEST_TENANT_ID}"


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


# =============================================================================
# Canonical receipt fixtures (Phase 0)
# =============================================================================
# Sourced from examples/ rather than hand-built, so a schema change that
# invalidates the shipped examples fails here instead of passing against a
# fixture that was quietly updated to match.

import json as _json
from pathlib import Path as _Path

_EXAMPLES = _Path(__file__).resolve().parents[1] / "examples" / "receipts"


def _load_example(name: str) -> dict:
    return _json.loads((_EXAMPLES / name).read_text(encoding="utf-8"))


@pytest.fixture
def canonical_good_receipt() -> dict:
    """A canonical `accepted` receipt that must validate."""
    return _load_example("accepted.json")


@pytest.fixture(params=sorted(p.name for p in _EXAMPLES.glob("*.json")))
def canonical_valid_example(request) -> dict:
    """Every shipped valid example, one per test."""
    return _load_example(request.param)


@pytest.fixture(params=sorted(p.name for p in (_EXAMPLES / "invalid").glob("*.json")))
def canonical_invalid_example(request) -> dict:
    """Every shipped negative example, one per test.

    These existed but were asserted nowhere: the example validator globbed
    `examples/receipts/*.json` non-recursively, so nothing ever checked that
    the schema *rejects* anything. A change that loosened the schema passed CI.
    """
    return _load_example(f"invalid/{request.param}")
