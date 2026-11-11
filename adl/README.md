# Architecture Decision Log

Architecture Decision Records (ADRs) capture significant decisions: the context, what was decided,
and the consequences. They explain *why* the code looks the way it does.

Write an ADR when a decision is hard to reverse (schema, service boundaries, key dependencies) or
likely to be questioned later. Routine changes do not need one.

- Copy [template.md](template.md) to `NNNN-short-title.md`.
- Status: Proposed, Accepted, Superseded by NNNN.

## Records

- [0001 – FastAPI with async SQLAlchemy and request-scoped sessions](0001-fastapi-async-sqlalchemy.md) – Accepted
- [0002 – Unified error response format](0002-unified-error-response-format.md) – Accepted
