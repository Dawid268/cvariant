"""Tailoring logic as pure functions: no database and no HTTP, only data in and decisions out.

The offer is described by a list of requirements (later produced by the AI offer parser);
the functions here decide which skills and experience bullets the tailored CV shows.
"""

import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from app.modules.experience.models import Experience, ExperienceBullet
from app.modules.skills.models import Skill


class Importance(StrEnum):
    MUST = "must"
    NICE = "nice"


IMPORTANCE_WEIGHT: dict[Importance, int] = {Importance.MUST: 3, Importance.NICE: 1}

# Skills the offer does not ask for fill the remaining slots only if they are strong and fresh
FILLER_MIN_LEVEL = 3
STALE_AFTER_YEARS = 5

_SEPARATORS = re.compile(r"[\s._/-]+")


def normalize_skill_name(name: str) -> str:
    """Return a comparison key, so "Node.js", "NodeJS" and "node js" all match."""
    return _SEPARATORS.sub("", name.casefold())


@dataclass(frozen=True, slots=True)
class Requirement:
    name: str
    importance: Importance


@dataclass(frozen=True, slots=True)
class RequirementMatch:
    requirement: Requirement
    skill: Skill | None  # None = the offer asks for something missing from the profile


def match_requirements(
    requirements: Sequence[Requirement],
    skills: Sequence[Skill],
) -> list[RequirementMatch]:
    """Pair each distinct requirement with the profile skill of the same name."""
    skills_by_key = {normalize_skill_name(skill.name): skill for skill in skills}

    # The same skill listed twice in an offer keeps its higher importance
    strongest: dict[str, Requirement] = {}
    for requirement in requirements:
        key = normalize_skill_name(requirement.name)
        if not key:
            continue
        current = strongest.get(key)
        if (
            current is None
            or IMPORTANCE_WEIGHT[requirement.importance] > IMPORTANCE_WEIGHT[current.importance]
        ):
            strongest[key] = requirement

    return [
        RequirementMatch(requirement, skills_by_key.get(key))
        for key, requirement in strongest.items()
    ]


# --- skills -------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RankedSkill:
    skill: Skill
    importance: Importance | None  # None = shown as a strong skill, not asked for by the offer


def _strength_key(skill: Skill, current_year: int) -> tuple[int, int, float, str]:
    """Sort key, strongest first: level, then recency, then years, then name for stability."""
    last_used = current_year if skill.last_used_year is None else skill.last_used_year
    return (-skill.level, -last_used, -skill.years, skill.name.casefold())


def _is_stale(skill: Skill, current_year: int) -> bool:
    return (
        skill.last_used_year is not None and current_year - skill.last_used_year > STALE_AFTER_YEARS
    )


def rank_skills(
    matches: Sequence[RequirementMatch],
    skills: Sequence[Skill],
    *,
    limit: int,
    current_year: int,
) -> list[RankedSkill]:
    """Requested skills first (must before nice), then strong, fresh skills up to the limit."""
    requested = sorted(
        (
            (match.skill, match.requirement.importance)
            for match in matches
            if match.skill is not None
        ),
        key=lambda pair: (-IMPORTANCE_WEIGHT[pair[1]], _strength_key(pair[0], current_year)),
    )

    requested_ids = {skill.id for skill, _ in requested}
    fillers = sorted(
        (
            skill
            for skill in skills
            if skill.id not in requested_ids
            and skill.level >= FILLER_MIN_LEVEL
            and not _is_stale(skill, current_year)
        ),
        key=lambda skill: _strength_key(skill, current_year),
    )

    ranked = [RankedSkill(skill, importance) for skill, importance in requested]
    ranked += [RankedSkill(skill, None) for skill in fillers]
    return ranked[:limit]


# --- experience ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RankedBullet:
    bullet: ExperienceBullet
    score: int  # sum of the weights of the offer requirements this bullet demonstrates


@dataclass(frozen=True, slots=True)
class TailoredExperience:
    experience: Experience
    bullets: list[RankedBullet]


def _skill_weights(matches: Sequence[RequirementMatch]) -> dict[uuid.UUID, int]:
    return {
        match.skill.id: IMPORTANCE_WEIGHT[match.requirement.importance]
        for match in matches
        if match.skill is not None
    }


def tailor_experiences(
    experiences: Sequence[Experience],
    matches: Sequence[RequirementMatch],
    *,
    bullets_per_experience: int,
) -> list[TailoredExperience]:
    """Keep every position (a CV must not hide jobs) but only its most relevant bullets.

    Ties keep the user's own bullet order, so with no relevant bullets the CV shows the
    first ones the user chose.
    """
    weights = _skill_weights(matches)
    tailored = []
    for experience in experiences:
        ranked = [
            RankedBullet(bullet, sum(weights.get(skill.id, 0) for skill in bullet.skills))
            for bullet in experience.bullets
        ]
        # sorted() is stable: equal scores stay in their original order
        best = sorted(ranked, key=lambda item: -item.score)[:bullets_per_experience]
        tailored.append(TailoredExperience(experience, best))
    return tailored


# --- coverage -----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Coverage:
    matched: list[Requirement]
    missing: list[Requirement]
    score: float  # weighted share of the requirements present in the profile, 0.0-1.0


def compute_coverage(matches: Sequence[RequirementMatch]) -> Coverage:
    matched = [match.requirement for match in matches if match.skill is not None]
    missing = [match.requirement for match in matches if match.skill is None]
    total = sum(IMPORTANCE_WEIGHT[req.importance] for req in [*matched, *missing])
    covered = sum(IMPORTANCE_WEIGHT[req.importance] for req in matched)
    # An offer with no requirements asks for nothing, so nothing is missing
    score = covered / total if total else 1.0
    return Coverage(matched, missing, round(score, 2))


# --- entry point --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TailoringOptions:
    skill_limit: int
    bullets_per_experience: int
    current_year: int  # passed in, not read from the clock, so results are reproducible


@dataclass(frozen=True, slots=True)
class TailoringResult:
    skills: list[RankedSkill]
    experiences: list[TailoredExperience]
    coverage: Coverage


def tailor(
    requirements: Sequence[Requirement],
    skills: Sequence[Skill],
    experiences: Sequence[Experience],
    options: TailoringOptions,
) -> TailoringResult:
    matches = match_requirements(requirements, skills)
    return TailoringResult(
        skills=rank_skills(
            matches, skills, limit=options.skill_limit, current_year=options.current_year
        ),
        experiences=tailor_experiences(
            experiences, matches, bullets_per_experience=options.bullets_per_experience
        ),
        coverage=compute_coverage(matches),
    )
