"""Common test fixtures and configuration for pytest.

This module contains fixtures that can be used across all types of tests:
- Unit tests
- Integration tests
- End-to-end tests
"""
import asyncio
import os
from typing import AsyncGenerator, Generator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool  # Add this import

from airweave.models._base import Base

# Import all fixtures so they are automatically available for all tests
from tests.fixtures.common import (  # noqa
    app,
    mock_background_tasks,
    mock_db,
    mock_sync,
    mock_sync_dag,
    mock_sync_job,
    mock_user,
)


# Mock DB Session for Unit Tests
@pytest.fixture
async def mock_db_session():
    """Provide a mock DB session for unit tests."""
    from unittest.mock import AsyncMock

    mock_session = AsyncMock(spec=AsyncSession)
    yield mock_session


# Fixture to check if database is available and skip if not
@pytest.fixture(scope="session")
def skip_if_no_db():
    """Skip tests that require a database if connection is not available."""
    # Use a test database URL, trying the environment first, then fallback to localhost
    test_db_url = os.environ.get(
        "TEST_DATABASE_URL", "postgresql://airweave:airweave1234!@localhost:5432/airweave"
    )

    # Parse the URL to get the connection details
    parts = test_db_url.split("://")[1].split("@")
    creds = parts[0].split(":")
    host_parts = parts[1].split("/")
    host_port = host_parts[0].split(":")
    db_name = host_parts[1] if len(host_parts) > 1 else "postgres"

    user = creds[0]
    password = creds[1] if len(creds) > 1 else ""
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 5432

    try:
        # For simplicity, use a simple sync check rather than async in this fixture
        import psycopg2

        psycopg2.connect(dbname=db_name, user=user, password=password, host=host, port=port).close()

        # If we get here, connection was successful
        return True
    except Exception as e:
        pytest.skip(f"Database connection not available: {e}")


# Test Database Connection for Integration Tests
@pytest.fixture(scope="function")
async def db_engine(skip_if_no_db):
    """Create a test database engine for each test function."""
    test_db_url = os.environ.get(
        "TEST_DATABASE_URL", "postgresql+asyncpg://airweave:airweave1234!@localhost:5432/airweave"
    )

    engine = create_async_engine(test_db_url, echo=True, poolclass=StaticPool, connect_args={
        "server_settings": {"jit": "off"}
    })

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop all tables after each test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for integration tests.

    Each test gets a fresh session with complete cleanup.
    """
    async with AsyncSession(db_engine, expire_on_commit=False) as session:
        yield session
        # The context manager automatically handles cleanup
