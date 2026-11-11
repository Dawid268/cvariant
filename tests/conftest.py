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
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

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
async def db_connection() -> AsyncIterator[AsyncConnection]:
    """A connection with an open transaction that is rolled back after each test.

    Everything a test writes - through the API or directly - happens inside this
    transaction, so nothing leaks between tests and no table cleanup is needed.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()


def _session_on(connection: AsyncConnection) -> AsyncSession:
    # commit() inside the code under test only releases a SAVEPOINT of the outer transaction
    return AsyncSession(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )


@pytest.fixture
async def db_session(db_connection: AsyncConnection) -> AsyncIterator[AsyncSession]:
    """A session for preparing or checking data directly in the database."""
    session = _session_on(db_connection)
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture
async def client(app: FastAPI, db_connection: AsyncConnection) -> AsyncIterator[AsyncClient]:
    """HTTP client where every request gets its own session, exactly like in production.

    Sharing one session between requests would let a later request see stale objects
    from the identity map of an earlier one (e.g. after a database-level cascade).
    """

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with _session_on(db_connection) as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()
