import uuid
from datetime import date

import pytest

from app.modules.experience.models import Experience, ExperienceBullet
from app.modules.skills.enums import SkillCategory
from app.modules.skills.models import Skill
from app.modules.tailoring.scoring import (
    Importance,
    Requirement,
    RequirementMatch,
    TailoringOptions,
    compute_coverage,
    match_requirements,
    normalize_skill_name,
    rank_skills,
    tailor,
    tailor_experiences,
)

CURRENT_YEAR = 2026
MUST = Importance.MUST
NICE = Importance.NICE


def make_skill(
    name: str, level: int = 4, years: float = 3, last_used_year: int | None = None
) -> Skill:
    # Transient ORM objects: the scoring functions never touch the database
    return Skill(
        id=uuid.uuid4(),
        name=name,
        category=SkillCategory.OTHER,
        level=level,
        years=years,
        last_used_year=last_used_year,
    )


def make_experience(*bullets: tuple[str, list[Skill]]) -> Experience:
    return Experience(
        id=uuid.uuid4(),
        company="Acme",
        title="Developer",
        start_date=date(2020, 1, 1),
        bullets=[
            ExperienceBullet(id=uuid.uuid4(), text=text, sort_order=index, skills=skills)
            for index, (text, skills) in enumerate(bullets)
        ],
    )


def names(items: list[Skill]) -> list[str]:
    return [item.name for item in items]


# --- normalize_skill_name / match_requirements --------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Node.js", "nodejs"),
        ("node js", "nodejs"),
        ("CI/CD", "cicd"),
        ("ASP.NET Core", "aspnetcore"),
        ("type_script", "typescript"),
        ("C++", "c++"),
        ("C#", "c#"),
    ],
)
def test_normalize_skill_name(raw: str, expected: str) -> None:
    assert normalize_skill_name(raw) == expected


def test_match_requirements_pairs_differently_spelled_names() -> None:
    # GIVEN
    node, angular = make_skill("Node.js"), make_skill("Angular")

    # WHEN
    matches = match_requirements(
        [Requirement("NodeJS", MUST), Requirement("Kubernetes", NICE)], [node, angular]
    )

    # THEN - order follows the offer; a missing skill is a gap, not an error
    assert matches == [
        RequirementMatch(Requirement("NodeJS", MUST), node),
        RequirementMatch(Requirement("Kubernetes", NICE), None),
    ]


def test_match_requirements_merges_duplicates_keeping_higher_importance() -> None:
    # GIVEN
    angular = make_skill("Angular")
    requirements = [
        Requirement("angular", NICE),
        Requirement("Docker", NICE),
        Requirement("ANGULAR", MUST),
        Requirement("Angular", NICE),
    ]

    # WHEN
    matches = match_requirements(requirements, [angular])

    # THEN - one entry per skill, in the position of its first mention
    assert [(m.requirement, m.skill) for m in matches] == [
        (Requirement("ANGULAR", MUST), angular),
        (Requirement("Docker", NICE), None),
    ]


def test_match_requirements_skips_names_without_letters() -> None:
    assert match_requirements([Requirement(" . / ", MUST)], [make_skill("Angular")]) == []


# --- rank_skills --------------------------------------------------------------------------


def test_rank_skills_puts_must_before_nice_before_fillers() -> None:
    # GIVEN - the strongest skill is not requested, the weakest one is a must
    python = make_skill("Python", level=5)
    rxjs = make_skill("RxJS", level=2)
    docker = make_skill("Docker", level=3)
    skills = [python, rxjs, docker]
    matches = match_requirements([Requirement("Docker", NICE), Requirement("RxJS", MUST)], skills)

    # WHEN
    ranked = rank_skills(matches, skills, limit=10, current_year=CURRENT_YEAR)

    # THEN
    assert [(r.skill.name, r.importance) for r in ranked] == [
        ("RxJS", MUST),
        ("Docker", NICE),
        ("Python", None),
    ]


def test_rank_skills_orders_by_level_then_recency_then_years_then_name() -> None:
    # GIVEN
    skills = [
        make_skill("Vue", level=4, years=2, last_used_year=2024),
        make_skill("React", level=4, years=1),  # still in use beats used in 2024
        make_skill("Svelte", level=4, years=1, last_used_year=2024),  # fewer years than Vue
        make_skill("angular", level=5),
        make_skill("Ember", level=4, years=2, last_used_year=2024),  # ties with Vue on name
    ]

    # WHEN
    ranked = rank_skills([], skills, limit=10, current_year=CURRENT_YEAR)

    # THEN
    assert names([r.skill for r in ranked]) == ["angular", "React", "Ember", "Vue", "Svelte"]


def test_rank_skills_fillers_skip_weak_and_stale_skills() -> None:
    # GIVEN
    skills = [
        make_skill("jQuery", level=5, last_used_year=CURRENT_YEAR - 6),  # stale
        make_skill("PHP", level=5, last_used_year=CURRENT_YEAR - 5),  # exactly at the limit
        make_skill("Go", level=2),  # too weak to fill
        make_skill("SQL", level=3),
    ]

    # WHEN
    ranked = rank_skills([], skills, limit=10, current_year=CURRENT_YEAR)

    # THEN
    assert names([r.skill for r in ranked]) == ["PHP", "SQL"]


def test_rank_skills_shows_requested_skills_even_if_weak_or_stale() -> None:
    # GIVEN - the offer asks for it, so the recruiter should see it
    jquery = make_skill("jQuery", level=2, last_used_year=2010)

    # WHEN
    ranked = rank_skills(
        match_requirements([Requirement("jQuery", NICE)], [jquery]),
        [jquery],
        limit=10,
        current_year=CURRENT_YEAR,
    )

    # THEN
    assert [(r.skill, r.importance) for r in ranked] == [(jquery, NICE)]


def test_rank_skills_respects_limit_dropping_the_least_relevant() -> None:
    # GIVEN
    skills = [make_skill("A", level=5), make_skill("B"), make_skill("C")]
    matches = match_requirements([Requirement("C", NICE), Requirement("B", MUST)], skills)

    # WHEN
    ranked = rank_skills(matches, skills, limit=2, current_year=CURRENT_YEAR)

    # THEN
    assert names([r.skill for r in ranked]) == ["B", "C"]


# --- tailor_experiences -------------------------------------------------------------------


def test_tailor_experiences_picks_bullets_with_highest_score() -> None:
    # GIVEN
    angular, rxjs, docker = make_skill("Angular"), make_skill("RxJS"), make_skill("Docker")
    experience = make_experience(
        ("Wrote docs", []),
        ("Dockerised the app", [docker]),  # nice = 1
        ("Built an Angular app with RxJS", [angular, rxjs]),  # must + must = 6
        ("Migrated to Angular 17", [angular]),  # must = 3
    )
    matches = match_requirements(
        [Requirement("Angular", MUST), Requirement("RxJS", MUST), Requirement("Docker", NICE)],
        [angular, rxjs, docker],
    )

    # WHEN
    [tailored] = tailor_experiences([experience], matches, bullets_per_experience=3)

    # THEN
    assert tailored.experience is experience
    assert [(b.bullet.text, b.score) for b in tailored.bullets] == [
        ("Built an Angular app with RxJS", 6),
        ("Migrated to Angular 17", 3),
        ("Dockerised the app", 1),
    ]


def test_tailor_experiences_keeps_user_order_on_ties_and_every_position() -> None:
    # GIVEN - nothing in these jobs matches the offer
    first = make_experience(("First", []), ("Second", []), ("Third", []))
    second = make_experience()

    # WHEN
    tailored = tailor_experiences(
        [first, second], match_requirements([Requirement("Go", MUST)], []), bullets_per_experience=2
    )

    # THEN - the job stays in the CV with the bullets the user put first
    assert [t.experience for t in tailored] == [first, second]
    assert [(b.bullet.text, b.score) for b in tailored[0].bullets] == [("First", 0), ("Second", 0)]
    assert tailored[1].bullets == []


# --- compute_coverage ---------------------------------------------------------------------


def test_compute_coverage_weights_must_higher_than_nice() -> None:
    # GIVEN - must (3) matched, must (3) and nice (1) missing
    angular = make_skill("Angular")
    matches = match_requirements(
        [Requirement("Angular", MUST), Requirement("Kubernetes", MUST), Requirement("Go", NICE)],
        [angular],
    )

    # WHEN
    coverage = compute_coverage(matches)

    # THEN
    assert coverage.matched == [Requirement("Angular", MUST)]
    assert coverage.missing == [Requirement("Kubernetes", MUST), Requirement("Go", NICE)]
    assert coverage.score == 0.43  # 3 / 7


def test_compute_coverage_without_requirements_is_full() -> None:
    assert compute_coverage([]).score == 1.0


# --- tailor -------------------------------------------------------------------------------


def test_tailor_combines_all_steps() -> None:
    # GIVEN
    angular, python = make_skill("Angular", level=5), make_skill("Python", level=3)
    experience = make_experience(("Python API", [python]), ("Angular UI", [angular]))

    # WHEN
    result = tailor(
        [Requirement("Angular", MUST), Requirement("AWS", NICE)],
        [python, angular],
        [experience],
        TailoringOptions(skill_limit=5, bullets_per_experience=1, current_year=CURRENT_YEAR),
    )

    # THEN
    assert [(r.skill, r.importance) for r in result.skills] == [(angular, MUST), (python, None)]
    assert [b.bullet.text for b in result.experiences[0].bullets] == ["Angular UI"]
    assert result.coverage.missing == [Requirement("AWS", NICE)]
    assert result.coverage.score == 0.75
