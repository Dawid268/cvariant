# 0001 – FastAPI with async SQLAlchemy and request-scoped sessions

- **Status:** Accepted
- **Date:** 2026-11-11

## Context

CVariant is an HTTP API that will call slow external services (fetching job offers, an LLM API)
and a PostgreSQL database. We need a framework that handles many concurrent I/O-bound requests,
validates input strictly and documents the API for the React frontend.

## Decision

- **FastAPI** with Pydantic v2 for routing, validation and OpenAPI documentation.
- **SQLAlchemy 2 in async mode** (asyncpg driver) with **Alembic** migrations.
- One database session per request, provided by a FastAPI dependency (`get_session`). The
  dependency commits when the request succeeds and rolls back on any error.
- Feature code lives in `app/modules/<feature>/` (api, models, schemas, service).
- JSON uses camelCase (`CamelModel`); Python code stays snake_case.

## Alternatives considered

- **A middleware that opens a global session for every request.** Less code in endpoints, but the
  session becomes hidden global state, which makes it harder to test and to reason about which
  code touches the database.
- **Django + Django REST Framework.** Mature, but synchronous by default and heavier than needed
  for an API-only service.
- **Synchronous SQLAlchemy.** Simpler, but blocks a worker thread while waiting for the database
  and external APIs.

## Consequences

- Endpoints declare the session explicitly (`session: SessionDep`), so tests can swap it out.
- Tests run each case in a rolled-back transaction instead of truncating tables.
- Every database call must be awaited; mixing sync and async code needs care.
