from typing import Any

import pytest
from httpx import AsyncClient

URL = "/api/v1/tailoring/preview"


async def create_skill(client: AsyncClient, name: str, **overrides: object) -> dict[str, Any]:
    payload: dict[str, object] = {"name": name, "category": "frontend", "level": 4, "years": 3}
    response = await client.post("/api/v1/skills", json=payload | overrides)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def create_experience(
    client: AsyncClient, company: str, start_date: str, bullets: list[tuple[str, list[str]]]
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/experiences",
        json={"company": company, "title": "Developer", "startDate": start_date},
    )
    assert response.status_code == 201, response.text
    experience: dict[str, Any] = response.json()
    for text, skill_ids in bullets:
        bullet = await client.post(
            f"/api/v1/experiences/{experience['id']}/bullets",
            json={"text": text, "skillIds": skill_ids},
        )
        assert bullet.status_code == 201, bullet.text
    return experience


async def test_preview_tailors_profile_to_offer(client: AsyncClient) -> None:
    # GIVEN
    angular = await create_skill(client, "Angular", level=5)
    rxjs = await create_skill(client, "RxJS", level=3)
    python = await create_skill(client, "Python", category="backend")
    await create_skill(client, "jQuery", level=5, lastUsedYear=2015)  # stale, not asked for
    bank = await create_experience(
        client,
        "Bank",
        "2022-01-01",
        [
            ("Wrote internal docs", []),
            ("Built trading UI in Angular and RxJS", [angular["id"], rxjs["id"]]),
            ("Python reporting service", [python["id"]]),
        ],
    )
    shop = await create_experience(client, "Shop", "2019-01-01", [("Fixed bugs", [])])

    # WHEN
    response = await client.post(
        URL,
        json={
            "requirements": [
                {"name": "RxJS", "importance": "must"},
                {"name": "angular", "importance": "must"},
                {"name": "Kubernetes", "importance": "must"},
                {"name": "Docker", "importance": "nice"},
            ],
            "bulletsPerExperience": 2,
        },
    )

    # THEN
    assert response.status_code == 200, response.text
    data = response.json()
    assert [(s["name"], s["importance"]) for s in data["skills"]] == [
        ("Angular", "must"),
        ("RxJS", "must"),
        ("Python", None),
    ]
    assert data["skills"][0] == {
        "id": angular["id"],
        "name": "Angular",
        "category": "frontend",
        "level": 5,
        "importance": "must",
    }
    assert [e["id"] for e in data["experiences"]] == [bank["id"], shop["id"]]
    bank_bullets = data["experiences"][0]["bullets"]
    assert [(b["text"], b["score"]) for b in bank_bullets] == [
        ("Built trading UI in Angular and RxJS", 6),
        ("Wrote internal docs", 0),
    ]
    assert [s["name"] for s in bank_bullets[0]["skills"]] == ["Angular", "RxJS"]
    assert data["coverage"] == {
        "score": 0.6,  # (3 + 3) / (3 + 3 + 3 + 1)
        "matched": [
            {"name": "RxJS", "importance": "must"},
            {"name": "angular", "importance": "must"},
        ],
        "missing": [
            {"name": "Kubernetes", "importance": "must"},
            {"name": "Docker", "importance": "nice"},
        ],
    }


async def test_preview_with_empty_profile_reports_everything_missing(client: AsyncClient) -> None:
    # WHEN
    response = await client.post(URL, json={"requirements": [{"name": "Go", "importance": "nice"}]})

    # THEN
    assert response.status_code == 200
    assert response.json() == {
        "skills": [],
        "experiences": [],
        "coverage": {
            "score": 0.0,
            "matched": [],
            "missing": [{"name": "Go", "importance": "nice"}],
        },
    }


async def test_preview_applies_skill_limit(client: AsyncClient) -> None:
    # GIVEN
    for name in ["A", "B", "C"]:
        await create_skill(client, name)

    # WHEN
    response = await client.post(URL, json={"requirements": [], "skillLimit": 2})

    # THEN
    assert response.status_code == 200
    assert [s["name"] for s in response.json()["skills"]] == ["A", "B"]


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"requirements": [{"name": "Go", "importance": "maybe"}]}, "requirements.0.importance"),
        ({"requirements": [{"name": "  ", "importance": "must"}]}, "requirements.0.name"),
        ({"requirements": [{"name": "Go"}]}, "requirements.0.importance"),
        ({"requirements": [], "skillLimit": 0}, "skillLimit"),
        ({"requirements": [], "bulletsPerExperience": 11}, "bulletsPerExperience"),
        ({"requirements": [{"name": "Go", "importance": "must"}] * 51}, "requirements"),
        ({"requirements": [], "offerUrl": "https://example.com"}, "offerUrl"),
        ({}, "requirements"),
    ],
)
async def test_preview_rejects_invalid_request(
    client: AsyncClient, payload: dict[str, object], field: str
) -> None:
    # WHEN
    response = await client.post(URL, json=payload)

    # THEN
    assert response.status_code == 422
    assert [d["field"] for d in response.json()["error"]["details"]] == [field]


async def test_preview_does_not_save_anything(client: AsyncClient) -> None:
    # GIVEN
    skill = await create_skill(client, "Angular")

    # WHEN
    await client.post(URL, json={"requirements": [{"name": "Angular", "importance": "must"}]})

    # THEN
    assert (await client.get("/api/v1/skills")).json() == [skill]
