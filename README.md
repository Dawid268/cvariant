# CVariant

**One profile, many CVs.** CVariant generates a CV tailored to a specific job offer from a single,
complete candidate profile.

A developer who knows Angular, React, Python and SQL cannot fit everything on one page. For an
"Angular Developer" offer the CV should lead with Angular, RxJS and NgRx; for a "Fullstack Python"
offer, with FastAPI and SQL. CVariant does that selection for you:

1. **Profile** – enter your skills once (level 1–5, years of experience, last used) together with
   your work experience.
2. **Job offer** – paste a link to the offer (or its text). CVariant extracts the required and
   nice-to-have skills.
3. **Generate** – skills and experience bullets are selected and ordered for that offer, within the
   space a CV template allows. AI refines the summary and wording.
4. **Edit** – fine-tune the result in a block editor.
5. **Download** – get an ATS-friendly PDF. Every variant is saved with the offer it was made for.

> CVariant never adds skills or experience that are not in your profile. AI may only select,
> reorder and rephrase what is already there, and every AI change needs your approval.

## Status

Early development. The roadmap lives in [GitHub Issues](../../issues).

## Tech stack

| Area | Choice |
| --- | --- |
| Backend | Python 3.13, FastAPI, Pydantic v2 |
| Database | PostgreSQL 17, SQLAlchemy 2 (async), Alembic |
| Frontend | React + TypeScript (planned) |
| Tooling | uv, ruff, mypy (strict), pytest, pre-commit, GitHub Actions |
| Infrastructure | Docker; AWS (planned) |

## Getting started

Requirements: [uv](https://docs.astral.sh/uv/), Docker with Docker Compose.

```bash
cp .env.example .env
uv sync
uv run pre-commit install

docker compose up -d db          # PostgreSQL on localhost:5442
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

API docs: <http://localhost:8000/docs> · health check: <http://localhost:8000/health/ready>

To run the whole stack in containers instead: `docker compose up --build`.

## Development

```bash
uv run ruff check . && uv run ruff format .   # lint and format
uv run mypy app tests migrations              # type check
uv run pytest                                 # tests (need `docker compose up -d db`)
uv run alembic revision --autogenerate -m "describe change"
```

Tests run against a dedicated `cvariant_test` database. Each test runs inside a transaction that is
rolled back afterwards, so tests never see each other's data.

## Error responses

Every error has the same shape, so a client needs a single handler:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed",
    "details": [
      {"location": "body", "field": "level", "message": "Input should be less than or equal to 5", "type": "less_than_equal"}
    ]
  }
}
```

Branch on `code` (`validation_error`, `business_rule_violation`, `not_found`, `conflict`,
`internal_error`, ...), never on `message`. See [ADR 0002](adl/0002-unified-error-response-format.md).

## Project structure

```
app/
├── app.py            # app factory: routing, middleware, error handlers, lifespan
├── main.py           # ASGI entry point
├── settings.py       # configuration from environment variables
├── core/             # database session, base models and schemas, errors
└── modules/<name>/   # one package per feature: api, models, schemas, service
migrations/           # Alembic migrations
tests/                # mirrors app/
adl/                  # architecture decision records
```

## Architecture decisions

Significant decisions are recorded in [`adl/`](adl/README.md).

## License

[MIT](LICENSE)
