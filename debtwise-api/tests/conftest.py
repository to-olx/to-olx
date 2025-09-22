"""
Global test fixtures and configuration.
"""

import asyncio
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings, Settings
from app.core.database import get_db
from app.main import app
from app.models.base import Base
from app.models.user import User  # Import all models to ensure they're registered


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
def test_settings() -> Settings:
    """Override settings for testing."""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        redis_url="redis://localhost:6379/15",  # Use a different Redis DB for tests
        secret_key="test-secret-key",
        jwt_secret_key="test-jwt-secret",
        environment="test",
        debug=False,
        rate_limit_enabled=False,  # Disable rate limiting in tests
    )


@pytest.fixture
def override_settings(test_settings: Settings):
    """Override the cached settings."""
    app.dependency_overrides[get_settings] = lambda: test_settings
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    # Create async engine with in-memory SQLite
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session factory
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    # Create and yield session
    async with async_session_maker() as session:
        yield session
        await session.rollback()
    
    # Clean up
    await engine.dispose()


@pytest.fixture
def override_db(test_db: AsyncSession):
    """Override the database dependency."""
    async def _get_test_db():
        yield test_db
    
    app.dependency_overrides[get_db] = _get_test_db
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(override_settings, override_db) -> TestClient:
    """Create a test client."""
    with TestClient(app) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def async_client(override_settings, override_db) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def test_user(test_db: AsyncSession) -> User:
    """Create a test user."""
    from app.core.security import get_password_hash
    
    user = User(
        email="test@example.com",
        username="testuser",
        full_name="Test User",
        hashed_password=get_password_hash("testpassword123"),
        is_active=True,
        is_verified=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_superuser(test_db: AsyncSession) -> User:
    """Create a test superuser."""
    from app.core.security import get_password_hash
    
    user = User(
        email="admin@example.com",
        username="admin",
        full_name="Admin User",
        hashed_password=get_password_hash("adminpassword123"),
        is_active=True,
        is_verified=True,
        is_superuser=True,
    )
    test_db.add(user)
    await test_db.commit()
    await test_db.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Create authentication headers for a test user."""
    from app.core.security import create_access_token
    
    access_token = create_access_token(subject=test_user.id)
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def superuser_auth_headers(test_superuser: User) -> dict:
    """Create authentication headers for a test superuser."""
    from app.core.security import create_access_token
    
    access_token = create_access_token(subject=test_superuser.id)
    return {"Authorization": f"Bearer {access_token}"}