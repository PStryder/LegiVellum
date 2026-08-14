"""Integration test for Postgres-backed Problemata repository."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from legivellum.problemata_control import (
    AsyncProblemataControlService,
    PostgresProblemataRepository,
    ProblemataBlueprint,
)


@pytest.fixture(autouse=True)
def cleanup_database():
    """Override global DB cleanup fixture for this module."""
    yield


@pytest.mark.asyncio
async def test_postgres_repository_persists_problemata_record():
    database_url = os.getenv(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/legivellum_test",
    )
    repository = PostgresProblemataRepository(database_url=database_url, auto_migrate=True)

    try:
        await repository.startup()
    except Exception as exc:  # pragma: no cover - environment-dependent
        await repository.shutdown()
        pytest.skip(f"Postgres unavailable for repository test: {exc}")

    service = AsyncProblemataControlService(repository=repository)
    blueprint = ProblemataBlueprint(
        problemata_id="prob-pg-test",
        tenant_id="tenant-pg",
        owner_principal="agent.pg",
        include_cognigate=False,
        include_delegategate=False,
        include_interview=False,
    )

    try:
        created = await service.create_from_blueprint(blueprint)
        fetched = await service.get("prob-pg-test")
        listed = await service.list()

        assert created.problemata_id == "prob-pg-test"
        assert fetched is not None
        assert fetched.problemata_id == "prob-pg-test"
        assert any(item.problemata_id == "prob-pg-test" for item in listed)
    finally:
        if repository._session_factory is not None:
            async with repository._session_factory() as session:
                await session.execute(
                    text("DELETE FROM problemata_registry WHERE problemata_id = :problemata_id"),
                    {"problemata_id": "prob-pg-test"},
                )
                await session.commit()
        await repository.shutdown()
