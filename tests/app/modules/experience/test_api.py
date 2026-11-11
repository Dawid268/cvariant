import uuid
from datetime import UTC, datetime
from typing import Any

from httpx import AsyncClient

URL = "/api/v1/experiences"
SKILLS_URL = "/api/v1/skills"


async def create_skill(client: AsyncClient, name: str = "Angular") -> str:
    payload = {"name": name, "category": "frontend", "level": 5, "years": 6}
    response = await client.post(SKILLS_URL, json=payload)
    assert response.status_code == 201, response.text
    skill_id: str = response.json()["id"]
    return skill_id


async def create_experience(client: AsyncClient, **overrides: object) -> dict[str, Any]:
    defaults: dict[str, object] = {
        "company": "Bank",
        "title": "Senior Angular Developer",
        "startDate": "2022-01-01",
    }
    response = await client.post(URL, json=defaults | overrides)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def create_bullet(
    client: AsyncClient,
    experience_id: str,
    **overrides: object,
) -> dict[str, Any]:
    defaults: dict[str, object] = {"text": "Migrated state management to Signal Store"}
    response = await client.post(f"{URL}/{experience_id}/bullets", json=defaults | overrides)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


# ---------- experiences ----------


async def test_create_experience_returns_201_with_empty_bullets(client: AsyncClient) -> None:
    # WHEN
    response = await client.post(
        URL,
        json={
            "company": " Bank ",
            "title": "Senior Angular Developer",
            "location": "Remote",
            "startDate": "2022-01-01",
        },
    )

    # THEN
    assert response.status_code == 201
    data = response.json()
    assert data == {
        "id": data["id"],
        "company": "Bank",
        "title": "Senior Angular Developer",
        "location": "Remote",
        "startDate": "2022-01-01",
        "endDate": None,
        "bullets": [],
    }


async def test_create_experience_with_end_before_start_returns_422(client: AsyncClient) -> None:
    # WHEN
    response = await client.post(
        URL,
        json={
            "company": "Bank",
            "title": "Dev",
            "startDate": "2022-01-01",
            "endDate": "2021-01-01",
        },
    )

    # THEN
    assert response.status_code == 422


async def test_create_experience_starting_in_future_returns_422(client: AsyncClient) -> None:
    # GIVEN
    next_year = datetime.now(UTC).year + 1

    # WHEN
    response = await client.post(
        URL,
        json={"company": "Bank", "title": "Dev", "startDate": f"{next_year}-01-01"},
    )

    # THEN
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "startDate"


async def test_patch_experience_changes_only_sent_fields(client: AsyncClient) -> None:
    # GIVEN
    experience = await create_experience(client, location="Warsaw")

    # WHEN
    response = await client.patch(f"{URL}/{experience['id']}", json={"location": "Remote"})

    # THEN
    assert response.status_code == 200
    assert response.json() == experience | {"location": "Remote"}


async def test_patch_experience_with_end_before_stored_start_returns_422(
    client: AsyncClient,
) -> None:
    # GIVEN
    experience = await create_experience(client, startDate="2022-01-01")

    # WHEN - only endDate is sent; the rule must use the stored startDate
    response = await client.patch(f"{URL}/{experience['id']}", json={"endDate": "2021-06-30"})

    # THEN
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "business_rule_violation"


async def test_patch_experience_with_null_end_date_marks_it_current(client: AsyncClient) -> None:
    # GIVEN
    experience = await create_experience(client, endDate="2023-12-31")

    # WHEN
    response = await client.patch(f"{URL}/{experience['id']}", json={"endDate": None})

    # THEN
    assert response.status_code == 200
    assert response.json()["endDate"] is None


async def test_list_experiences_current_first_then_newest(client: AsyncClient) -> None:
    # GIVEN
    await create_experience(client, company="Oldest", startDate="2016-01-01", endDate="2018-12-31")
    await create_experience(client, company="Current", startDate="2023-01-01")
    await create_experience(
        client, company="Previous", startDate="2019-01-01", endDate="2022-12-31"
    )

    # WHEN
    response = await client.get(URL)

    # THEN
    assert response.status_code == 200
    assert [e["company"] for e in response.json()] == ["Current", "Previous", "Oldest"]


async def test_delete_experience_removes_its_bullets(client: AsyncClient) -> None:
    # GIVEN
    experience = await create_experience(client)
    bullet = await create_bullet(client, experience["id"])

    # WHEN
    response = await client.delete(f"{URL}/{experience['id']}")

    # THEN
    assert response.status_code == 204
    assert (await client.get(f"{URL}/{experience['id']}")).status_code == 404
    patch = await client.patch(f"{URL}/{experience['id']}/bullets/{bullet['id']}", json={})
    assert patch.status_code == 404


async def test_get_unknown_experience_returns_404(client: AsyncClient) -> None:
    # WHEN
    response = await client.get(f"{URL}/{uuid.uuid4()}")

    # THEN
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


# ---------- bullets ----------


async def test_create_bullet_with_skills_returns_skill_names(client: AsyncClient) -> None:
    # GIVEN
    angular = await create_skill(client, "Angular")
    ngrx = await create_skill(client, "NgRx")
    experience = await create_experience(client)

    # WHEN
    response = await client.post(
        f"{URL}/{experience['id']}/bullets",
        json={"text": "Migrated state to Signal Store", "skillIds": [ngrx, angular]},
    )

    # THEN
    assert response.status_code == 201
    data = response.json()
    assert data["text"] == "Migrated state to Signal Store"
    assert data["sortOrder"] == 0
    assert [skill["name"] for skill in data["skills"]] == ["Angular", "NgRx"]


async def test_bullet_appears_in_experience(client: AsyncClient) -> None:
    # GIVEN
    experience = await create_experience(client)
    bullet = await create_bullet(client, experience["id"])

    # WHEN
    response = await client.get(f"{URL}/{experience['id']}")

    # THEN
    assert response.json()["bullets"] == [bullet]


async def test_create_bullet_with_unknown_skill_returns_422(client: AsyncClient) -> None:
    # GIVEN
    experience = await create_experience(client)
    unknown = str(uuid.uuid4())

    # WHEN
    response = await client.post(
        f"{URL}/{experience['id']}/bullets",
        json={"text": "Something", "skillIds": [unknown]},
    )

    # THEN
    assert response.status_code == 422
    assert unknown in response.json()["error"]["message"]


async def test_create_bullet_with_duplicate_skill_returns_422(client: AsyncClient) -> None:
    # GIVEN
    angular = await create_skill(client)
    experience = await create_experience(client)

    # WHEN
    response = await client.post(
        f"{URL}/{experience['id']}/bullets",
        json={"text": "Something", "skillIds": [angular, angular]},
    )

    # THEN
    assert response.status_code == 422
    assert response.json()["error"]["details"][0]["field"] == "skillIds"


async def test_patch_bullet_replaces_skills(client: AsyncClient) -> None:
    # GIVEN
    angular = await create_skill(client, "Angular")
    python = await create_skill(client, "Python")
    experience = await create_experience(client)
    bullet = await create_bullet(client, experience["id"], skillIds=[angular])

    # WHEN
    response = await client.patch(
        f"{URL}/{experience['id']}/bullets/{bullet['id']}",
        json={"skillIds": [python]},
    )

    # THEN
    assert response.status_code == 200
    assert [skill["name"] for skill in response.json()["skills"]] == ["Python"]
    assert response.json()["text"] == bullet["text"]


async def test_bullet_of_another_experience_returns_404(client: AsyncClient) -> None:
    # GIVEN
    first = await create_experience(client, company="First")
    second = await create_experience(client, company="Second")
    bullet = await create_bullet(client, first["id"])

    # WHEN
    response = await client.patch(
        f"{URL}/{second['id']}/bullets/{bullet['id']}",
        json={"text": "Changed through the wrong experience"},
    )

    # THEN
    assert response.status_code == 404


async def test_delete_bullet_removes_it_from_experience(client: AsyncClient) -> None:
    # GIVEN
    experience = await create_experience(client)
    bullet = await create_bullet(client, experience["id"])

    # WHEN
    response = await client.delete(f"{URL}/{experience['id']}/bullets/{bullet['id']}")

    # THEN
    assert response.status_code == 204
    assert (await client.get(f"{URL}/{experience['id']}")).json()["bullets"] == []


async def test_deleting_skill_removes_tag_but_keeps_bullet(client: AsyncClient) -> None:
    # GIVEN
    angular = await create_skill(client, "Angular")
    ngrx = await create_skill(client, "NgRx")
    experience = await create_experience(client)
    await create_bullet(client, experience["id"], skillIds=[angular, ngrx])

    # WHEN
    await client.delete(f"{SKILLS_URL}/{ngrx}")

    # THEN
    bullets = (await client.get(f"{URL}/{experience['id']}")).json()["bullets"]
    assert len(bullets) == 1
    assert [skill["name"] for skill in bullets[0]["skills"]] == ["Angular"]


async def test_patch_bullet_changes_text_and_order_but_keeps_skills(client: AsyncClient) -> None:
    # GIVEN
    angular = await create_skill(client)
    experience = await create_experience(client)
    bullet = await create_bullet(client, experience["id"], skillIds=[angular])

    # WHEN
    response = await client.patch(
        f"{URL}/{experience['id']}/bullets/{bullet['id']}",
        json={"text": "Led the migration to Signal Store", "sortOrder": 3},
    )

    # THEN
    assert response.status_code == 200
    assert response.json() == bullet | {"text": "Led the migration to Signal Store", "sortOrder": 3}


async def test_bullets_without_sort_order_are_appended_at_the_end(client: AsyncClient) -> None:
    # GIVEN
    experience = await create_experience(client)

    # WHEN
    for text in ["first", "second", "third"]:
        await create_bullet(client, experience["id"], text=text)

    # THEN
    bullets = (await client.get(f"{URL}/{experience['id']}")).json()["bullets"]
    assert [(b["text"], b["sortOrder"]) for b in bullets] == [
        ("first", 0),
        ("second", 1),
        ("third", 2),
    ]


async def test_bullets_are_ordered_by_explicit_sort_order(client: AsyncClient) -> None:
    # GIVEN
    experience = await create_experience(client)
    await create_bullet(client, experience["id"], text="least important", sortOrder=5)
    await create_bullet(client, experience["id"], text="most important", sortOrder=1)

    # WHEN
    bullets = (await client.get(f"{URL}/{experience['id']}")).json()["bullets"]

    # THEN
    assert [b["text"] for b in bullets] == ["most important", "least important"]


async def test_delete_unknown_experience_returns_404(client: AsyncClient) -> None:
    # WHEN
    response = await client.delete(f"{URL}/{uuid.uuid4()}")

    # THEN
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_tags_have_the_same_order_in_every_response(client: AsyncClient) -> None:
    # GIVEN - skills created in non-alphabetical order
    rxjs = await create_skill(client, "RxJS")
    ngrx = await create_skill(client, "NgRx")
    angular = await create_skill(client, "Angular")
    experience = await create_experience(client)

    # WHEN
    created = await create_bullet(client, experience["id"], skillIds=[rxjs, angular, ngrx])
    patched = await client.patch(
        f"{URL}/{experience['id']}/bullets/{created['id']}",
        json={"skillIds": [rxjs, angular]},
    )
    fetched = (await client.get(f"{URL}/{experience['id']}")).json()["bullets"][0]

    # THEN
    assert [s["name"] for s in created["skills"]] == ["Angular", "NgRx", "RxJS"]
    assert [s["name"] for s in patched.json()["skills"]] == ["Angular", "RxJS"]
    assert fetched["skills"] == patched.json()["skills"]


async def test_patch_bullet_that_is_not_first_in_the_list(client: AsyncClient) -> None:
    # GIVEN
    experience = await create_experience(client)
    await create_bullet(client, experience["id"], text="first")
    second = await create_bullet(client, experience["id"], text="second")

    # WHEN
    response = await client.patch(
        f"{URL}/{experience['id']}/bullets/{second['id']}",
        json={"text": "second, edited"},
    )

    # THEN
    assert response.status_code == 200
    bullets = (await client.get(f"{URL}/{experience['id']}")).json()["bullets"]
    assert [b["text"] for b in bullets] == ["first", "second, edited"]
