from collections.abc import AsyncIterator
from typing import NoReturn

from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError

from app.core.db import get_session
from app.settings import get_settings


async def test_liveness_returns_ok_and_version(client: AsyncClient) -> None:
    # WHEN
    response = await client.get("/health")

    # THEN
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": get_settings().VERSION}


async def test_readiness_is_ok_when_database_answers(client: AsyncClient) -> None:
    # WHEN
    response = await client.get("/health/ready")

    # THEN
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


class _UnavailableDatabaseSession:
    async def execute(self, *_args: object, **_kwargs: object) -> NoReturn:
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))


async def test_readiness_returns_503_when_database_is_down(
    client: AsyncClient, app: FastAPI
) -> None:
    # GIVEN
    async def broken_session() -> AsyncIterator[_UnavailableDatabaseSession]:
        yield _UnavailableDatabaseSession()

    app.dependency_overrides[get_session] = broken_session

    # WHEN
    response = await client.get("/health/ready")

    # THEN
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable", "database": "unavailable"}
