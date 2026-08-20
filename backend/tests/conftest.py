"""
Pytest configuration and fixtures for JobPilot tests.
"""
import pytest
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import Base
from app.main import app


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_database():
    """Set up test database - tables already created by alembic."""
    yield
    # Cleanup after all tests


@pytest.fixture
async def db_session():
    """Provide a clean database session for each test."""
    # Use the existing database
    from app.core.database import get_db
    async for session in get_db():
        yield session
        break


# Override app dependencies for testing
@pytest.fixture(autouse=True)
def override_dependencies():
    """Override app dependencies for testing."""
    # Reset any overrides
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
