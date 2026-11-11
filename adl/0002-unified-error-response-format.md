# 0002 – Unified error response format

- **Status:** Accepted
- **Date:** 2026-11-11

## Context

The API returned errors in two shapes: our domain errors used
`{"error": {"code", "message"}}`, while FastAPI's request validation used
`{"detail": [...]}`. Framework errors (unknown route, wrong method) and unexpected
crashes had their own formats too. A client - the planned React frontend first - would
have to handle every shape separately.

## Decision

Every error response has exactly one shape:

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

- `code` is machine-readable and stable; clients branch on it, never on `message`.
- `details` is always present (empty when there is nothing field-specific).
- `field` is the name as the client sent it (camelCase), with list positions such as
  `skillIds.0`; it is `null` for rules spanning several fields and for malformed JSON.
- The submitted value is never echoed back, as it may contain personal data.
- Unexpected errors return `500 internal_error` with no internals; the full traceback goes
  to the server log. The app no longer passes `debug=True` to FastAPI, because Starlette's
  debug mode replaces the JSON response with an HTML traceback page.
- OpenAPI documents `ErrorResponse` for each status code an endpoint can return, replacing
  FastAPI's default `HTTPValidationError`, so generated clients get one error type.

| Source | Status | `code` |
| --- | --- | --- |
| Request validation | 422 | `validation_error` |
| Broken business rule | 422 | `business_rule_violation` |
| Missing resource | 404 | `not_found` |
| Duplicate data | 409 | `conflict` |
| Framework HTTP errors | 404, 405, ... | from the status phrase, e.g. `method_not_allowed` |
| Unhandled exception | 500 | `internal_error` |

## Alternatives considered

- **RFC 9457 Problem Details** (`application/problem+json`). A standard, but its flat
  `type`/`title`/`detail` fields fit field-level validation errors less naturally and
  are less familiar to frontend developers than a nested `error` object.
- **Keep FastAPI's default validation format.** No code, but clients still need two parsers.

## Consequences

- One error type in the frontend and in any generated API client.
- Adding a new domain error is a subclass with `status_code` and `code`; no new handler.
- Validation messages come from Pydantic, so they are in English and may change with
  Pydantic upgrades; clients must rely on `code` and `type`, not on message text.
