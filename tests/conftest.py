import os

# Point the app at the test database BEFORE anything imports the settings.
os.environ["POSTGRES_DB"] = os.environ.get("TEST_POSTGRES_DB", "cvariant_test")

from collections.abc import AsyncIterator

import pytest
from alembic import command
from alembic.config import Config
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.app import app_factory
from app.core.db import engine, get_session
from app.settings import get_settings


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    """Run all migrations once against the test database."""
    assert get_settings().POSTGRES_DB.endswith("_test"), "Refusing to run tests on a non-test DB"
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture(scope="session")
async def app() -> AsyncIterator[FastAPI]:
    application = app_factory()
    async with LifespanManager(application):
        yield application


@pytest.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """A session inside a transaction that is rolled back after each test.

    Code under test may call commit() - it only releases a SAVEPOINT, so nothing
    leaks between tests and no table cleanup is needed.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        session = AsyncSession(
            bind=connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )
        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest.fixture
async def client(app: FastAPI, db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    async def override_get_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()
