"""
LegiVellum Database Utilities

Shared database connection and query utilities for PostgreSQL.
"""
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase


# Database URL from environment
def get_database_url() -> str:
    """Get database URL from environment"""
    return os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:postgres@localhost:5432/legivellum"
    )


class Base(DeclarativeBase):
    """SQLAlchemy declarative base"""
    pass


def create_engine(database_url: str = None):
    """Create async SQLAlchemy engine"""
    url = database_url or get_database_url()
    return create_async_engine(
        url,
        echo=os.environ.get("SQL_ECHO", "false").lower() == "true",
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    """Create async session factory"""
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


# Global engine and session factory (set on app startup)
_engine = None
_session_factory = None


def init_database(database_url: str = None):
    """Initialize global database connection"""
    global _engine, _session_factory
    _engine = create_engine(database_url)
    _session_factory = create_session_factory(_engine)
    return _engine


async def close_database():
    """Close global database connection"""
    global _engine
    if _engine:
        await _engine.dispose()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Get a database session from the pool"""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")

    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_session_dependency() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions"""
    async with get_session() as session:
        yield session
