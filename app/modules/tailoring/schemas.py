import uuid
from datetime import date
from typing import Annotated, Self

from pydantic import Field, StringConstraints

from app.core.schemas import CamelInputModel, CamelModel
from app.modules.experience.schemas import BulletSkillRead
from app.modules.skills.enums import SkillCategory
from app.modules.tailoring.scoring import (
    Importance,
    Requirement,
    TailoredExperience,
    TailoringResult,
)

RequirementName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]

# ---------- request ----------


class RequirementIn(CamelInputModel):
    name: RequirementName
    importance: Importance

    def to_domain(self) -> Requirement:
        return Requirement(self.name, self.importance)


class TailoringRequest(CamelInputModel):
    """Requirements of one job offer, typed by hand for now and produced by AI later."""

    requirements: list[RequirementIn] = Field(max_length=50)
    skill_limit: int = Field(default=12, ge=1, le=30)
    bullets_per_experience: int = Field(default=4, ge=1, le=10)


# ---------- response ----------


class RequirementRead(CamelModel):
    name: str
    importance: Importance

    @classmethod
    def from_domain(cls, requirement: Requirement) -> Self:
        return cls(name=requirement.name, importance=requirement.importance)


class TailoredSkillRead(CamelModel):
    id: uuid.UUID
    name: str
    category: SkillCategory
    level: int
    importance: Importance | None = Field(
        description="Importance in the offer; null = a strong skill the offer did not ask for"
    )


class TailoredBulletRead(CamelModel):
    id: uuid.UUID
    text: str
    score: int = Field(description="Sum of the weights of offer requirements this bullet shows")
    skills: list[BulletSkillRead]


class TailoredExperienceRead(CamelModel):
    id: uuid.UUID
    company: str
    title: str
    location: str | None
    start_date: date
    end_date: date | None
    bullets: list[TailoredBulletRead]

    @classmethod
    def from_domain(cls, tailored: TailoredExperience) -> Self:
        experience = tailored.experience
        return cls(
            id=experience.id,
            company=experience.company,
            title=experience.title,
            location=experience.location,
            start_date=experience.start_date,
            end_date=experience.end_date,
            bullets=[
                TailoredBulletRead(
                    id=ranked.bullet.id,
                    text=ranked.bullet.text,
                    score=ranked.score,
                    skills=[BulletSkillRead.model_validate(s) for s in ranked.bullet.skills],
                )
                for ranked in tailored.bullets
            ],
        )


class CoverageRead(CamelModel):
    score: float = Field(ge=0, le=1, description="Weighted share of requirements in the profile")
    matched: list[RequirementRead]
    missing: list[RequirementRead]


class TailoringPreview(CamelModel):
    skills: list[TailoredSkillRead]
    experiences: list[TailoredExperienceRead]
    coverage: CoverageRead

    @classmethod
    def from_domain(cls, result: TailoringResult) -> Self:
        return cls(
            skills=[
                TailoredSkillRead(
                    id=ranked.skill.id,
                    name=ranked.skill.name,
                    category=ranked.skill.category,
                    level=ranked.skill.level,
                    importance=ranked.importance,
                )
                for ranked in result.skills
            ],
            experiences=[TailoredExperienceRead.from_domain(e) for e in result.experiences],
            coverage=CoverageRead(
                score=result.coverage.score,
                matched=[RequirementRead.from_domain(r) for r in result.coverage.matched],
                missing=[RequirementRead.from_domain(r) for r in result.coverage.missing],
            ),
        )
