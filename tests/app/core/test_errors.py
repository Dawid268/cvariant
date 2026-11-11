import json
import logging
from collections.abc import AsyncIterator
from typing import NoReturn

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.app import app_factory
from app.core.errors import http_error_handler

SKILLS_URL = "/api/v1/skills"
EXPERIENCES_URL = "/api/v1/experiences"
VALID_SKILL = {"name": "Angular", "category": "frontend", "level": 5, "years": 6}


async def test_validation_error_has_the_unified_shape(client: AsyncClient) -> None:
    # WHEN
    response = await client.post(SKILLS_URL, json=VALID_SKILL | {"level": 6})

    # THEN
    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "Request validation failed",
            "details": [
                {
                    "location": "body",
                    "field": "level",
                    "message": "Input should be less than or equal to 5",
                    "type": "less_than_equal",
                },
            ],
        },
    }


async def test_validation_error_lists_every_invalid_field(client: AsyncClient) -> None:
    # WHEN
    response = await client.post(SKILLS_URL, json={"category": "frontend", "years": -1})

    # THEN
    details = response.json()["error"]["details"]
    assert {(d["field"], d["type"]) for d in details} == {
        ("name", "missing"),
        ("level", "missing"),
        ("years", "greater_than_equal"),
    }


async def test_validation_error_does_not_echo_the_input(client: AsyncClient) -> None:
    # WHEN
    response = await client.post(SKILLS_URL, json=VALID_SKILL | {"level": "secret-value"})

    # THEN
    assert "secret-value" not in response.text


async def test_custom_validator_message_has_no_pydantic_prefix(client: AsyncClient) -> None:
    # WHEN
    response = await client.post(SKILLS_URL, json=VALID_SKILL | {"lastUsedYear": 2999})

    # THEN
    assert response.json()["error"]["details"][0]["message"] == "cannot be in the future"


async def test_cross_field_rule_has_no_field(client: AsyncClient) -> None:
    # WHEN
    response = await client.post(
        EXPERIENCES_URL,
        json={
            "company": "Bank",
            "title": "Dev",
            "startDate": "2022-01-01",
            "endDate": "2021-01-01",
        },
    )

    # THEN
    assert response.json()["error"]["details"] == [
        {
            "location": "body",
            "field": None,
            "message": "endDate cannot be earlier than startDate",
            "type": "value_error",
        },
    ]


async def test_nested_field_path_points_at_the_list_item(client: AsyncClient) -> None:
    # WHEN
    experience = (
        await client.post(
            EXPERIENCES_URL,
            json={"company": "Bank", "title": "Dev", "startDate": "2022-01-01"},
        )
    ).json()
    response = await client.post(
        f"{EXPERIENCES_URL}/{experience['id']}/bullets",
        json={"text": "Something", "skillIds": ["not-a-uuid"]},
    )

    # THEN
    detail = response.json()["error"]["details"][0]
    assert (detail["location"], detail["field"], detail["type"]) == (
        "body",
        "skillIds.0",
        "uuid_parsing",
    )


async def test_malformed_json_is_a_validation_error_without_field(client: AsyncClient) -> None:
    # WHEN
    response = await client.post(
        SKILLS_URL,
        content='{"name": "Angular",',
        headers={"Content-Type": "application/json"},
    )

    # THEN
    assert response.status_code == 422
    detail = response.json()["error"]["details"][0]
    assert (detail["location"], detail["field"], detail["type"]) == ("body", None, "json_invalid")


async def test_invalid_path_parameter_reports_path_location(client: AsyncClient) -> None:
    # WHEN
    response = await client.get(f"{SKILLS_URL}/not-a-uuid")

    # THEN
    assert response.status_code == 422
    detail = response.json()["error"]["details"][0]
    assert (detail["location"], detail["field"]) == ("path", "skill_id")


async def test_domain_error_has_the_unified_shape(client: AsyncClient) -> None:
    # GIVEN
    await client.post(SKILLS_URL, json=VALID_SKILL)

    # WHEN
    response = await client.post(SKILLS_URL, json=VALID_SKILL)

    # THEN
    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "conflict",
            "message": "Skill 'Angular' already exists",
            "details": [],
        },
    }


async def test_unknown_route_has_the_unified_shape(client: AsyncClient) -> None:
    # WHEN
    response = await client.get("/api/v1/does-not-exist")

    # THEN
    assert response.status_code == 404
    assert response.json() == {
        "error": {"code": "not_found", "message": "Not Found", "details": []},
    }


async def test_wrong_method_keeps_the_allow_header(client: AsyncClient) -> None:
    # WHEN
    response = await client.put(SKILLS_URL)

    # THEN
    assert response.status_code == 405
    assert response.json()["error"]["code"] == "method_not_allowed"
    assert "allow" in response.headers  # the framework's Allow header is passed through


@pytest.fixture
async def crashing_client() -> AsyncIterator[AsyncClient]:
    app: FastAPI = app_factory()

    async def crash() -> NoReturn:
        raise RuntimeError("database password is hunter2")

    app.add_api_route("/crash", crash, response_model=None)
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def test_unhandled_error_is_logged_but_not_revealed(
    crashing_client: AsyncClient,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # WHEN
    with caplog.at_level(logging.ERROR, logger="app.core.errors"):
        response = await crashing_client.get("/crash")

    # THEN
    assert response.status_code == 500
    assert response.json() == {
        "error": {"code": "internal_error", "message": "Internal server error", "details": []},
    }
    assert "hunter2" not in response.text
    assert "hunter2" in caplog.text


async def test_openapi_documents_the_unified_error_schema(client: AsyncClient) -> None:
    # WHEN
    schema = (await client.get("/openapi.json")).json()

    # THEN
    create_skill = schema["paths"][SKILLS_URL]["post"]["responses"]
    assert create_skill["409"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse",
    }
    assert create_skill["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ErrorResponse",
    }
    assert "HTTPValidationError" not in schema["components"]["schemas"]


async def test_non_standard_http_status_does_not_break_the_handler() -> None:
    # GIVEN
    request = Request({"type": "http", "method": "GET", "path": "/", "headers": []})

    # WHEN
    response = await http_error_handler(request, StarletteHTTPException(status_code=499))

    # THEN
    assert response.status_code == 499
    assert json.loads(bytes(response.body)) == {
        "error": {"code": "http_error", "message": "HTTP Error", "details": []},
    }
