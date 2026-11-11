import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from httpx import AsyncClient

URL = "/api/v1/skills"


async def create_skill(client: AsyncClient, **overrides: object) -> dict[str, Any]:
    defaults: dict[str, object] = {
        "name": "Angular",
        "category": "frontend",
        "level": 5,
        "years": 6,
    }
    payload = defaults | overrides
    response = await client.post(URL, json=payload)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def test_create_skill_returns_201_with_camel_case_fields(client: AsyncClient) -> None:
    # WHEN
    response = await client.post(
        URL,
        json={
            "name": "  Python ",
            "category": "backend",
            "level": 3,
            "years": 2.5,
            "lastUsedYear": 2025,
        },
    )

    # THEN
    assert response.status_code == 201
    data = response.json()
    assert data == {
        "id": data["id"],
        "name": "Python",
        "category": "backend",
        "level": 3,
        "years": 2.5,
        "lastUsedYear": 2025,
    }


async def test_create_skill_with_level_out_of_range_returns_422(client: AsyncClient) -> None:
    # WHEN
    response = await client.post(
        URL, json={"name": "React", "category": "frontend", "level": 6, "years": 1}
    )

    # THEN
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "level"


async def test_create_skill_with_duplicate_name_ignores_case_and_returns_409(
    client: AsyncClient,
) -> None:
    # GIVEN
    await create_skill(client, name="Angular")

    # WHEN
    response = await client.post(
        URL, json={"name": "angular", "category": "frontend", "level": 4, "years": 1}
    )

    # THEN
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


async def test_list_skills_sorted_by_level_then_name(client: AsyncClient) -> None:
    # GIVEN
    await create_skill(client, name="SQL", category="database", level=3)
    await create_skill(client, name="Angular", level=5)
    await create_skill(client, name="Python", category="backend", level=3)

    # WHEN
    response = await client.get(URL)

    # THEN
    assert response.status_code == 200
    assert [skill["name"] for skill in response.json()] == ["Angular", "Python", "SQL"]


async def test_patch_changes_only_sent_fields(client: AsyncClient) -> None:
    # GIVEN
    skill = await create_skill(client, level=5, years=6)

    # WHEN
    response = await client.patch(f"{URL}/{skill['id']}", json={"level": 4})

    # THEN
    assert response.status_code == 200
    assert response.json()["level"] == 4
    assert response.json()["years"] == 6


async def test_patch_with_null_clears_last_used_year(client: AsyncClient) -> None:
    # GIVEN
    skill = await create_skill(client, lastUsedYear=2021)

    # WHEN
    response = await client.patch(f"{URL}/{skill['id']}", json={"lastUsedYear": None})

    # THEN
    assert response.status_code == 200
    assert response.json()["lastUsedYear"] is None


async def test_patch_rename_to_existing_name_returns_409(client: AsyncClient) -> None:
    # GIVEN
    await create_skill(client, name="Angular")
    python = await create_skill(client, name="Python", category="backend")

    # WHEN
    response = await client.patch(f"{URL}/{python['id']}", json={"name": "ANGULAR"})

    # THEN
    assert response.status_code == 409


async def test_delete_skill_then_get_returns_404(client: AsyncClient) -> None:
    # GIVEN
    skill = await create_skill(client)

    # WHEN
    delete_response = await client.delete(f"{URL}/{skill['id']}")

    # THEN
    assert delete_response.status_code == 204
    assert (await client.get(f"{URL}/{skill['id']}")).status_code == 404


async def test_get_unknown_skill_returns_404(client: AsyncClient) -> None:
    # WHEN
    response = await client.get(f"{URL}/{uuid.uuid4()}")

    # THEN
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_get_skill_returns_the_skill(client: AsyncClient) -> None:
    # GIVEN
    skill = await create_skill(client, name="Python", category="backend", level=3)

    # WHEN
    response = await client.get(f"{URL}/{skill['id']}")

    # THEN
    assert response.status_code == 200
    assert response.json() == skill


async def test_create_skill_with_last_used_year_in_future_returns_422(client: AsyncClient) -> None:
    # GIVEN
    next_year = datetime.now(UTC).year + 1

    # WHEN
    response = await client.post(
        URL,
        json={
            "name": "React",
            "category": "frontend",
            "level": 3,
            "years": 1,
            "lastUsedYear": next_year,
        },
    )

    # THEN
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "lastUsedYear"


@pytest.mark.parametrize("field", ["name", "category", "level", "years"])
async def test_patch_with_null_in_required_field_returns_422(
    client: AsyncClient,
    field: str,
) -> None:
    # GIVEN
    skill = await create_skill(client)

    # WHEN
    response = await client.patch(f"{URL}/{skill['id']}", json={field: None})

    # THEN
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == field


async def test_create_skill_with_unknown_field_returns_422(client: AsyncClient) -> None:
    # WHEN
    response = await client.post(
        URL,
        json={
            "name": "React",
            "category": "frontend",
            "level": 3,
            "years": 1,
            "lastUsedyear": 2024,  # typo: lower-case "y"
        },
    )

    # THEN
    assert response.status_code == 422
    error = response.json()["error"]["details"][0]
    assert error["type"] == "extra_forbidden"
    assert error["field"] == "lastUsedyear"
