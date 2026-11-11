import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Self

from pydantic import AfterValidator, Field, StringConstraints, field_validator, model_validator

from app.core.schemas import CamelInputModel, CamelModel, reject_null
from app.modules.skills.enums import SkillCategory


def _not_in_future(value: date) -> date:
    if value > datetime.now(UTC).date():
        raise ValueError("cannot be in the future")
    return value


def _unique(ids: list[uuid.UUID]) -> list[uuid.UUID]:
    if len(ids) != len(set(ids)):
        raise ValueError("must not contain duplicates")
    return ids


ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
BulletText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
SortOrder = Annotated[int, Field(ge=0)]
StartDate = Annotated[date, AfterValidator(_not_in_future)]
SkillIds = Annotated[list[uuid.UUID], Field(max_length=20), AfterValidator(_unique)]


# ---------- bullets ----------


class BulletCreate(CamelInputModel):
    text: BulletText
    sort_order: SortOrder | None = None  # omitted = append after the last bullet
    skill_ids: SkillIds = Field(default_factory=list)


class BulletUpdate(CamelInputModel):
    text: BulletText | None = None
    sort_order: SortOrder | None = None
    skill_ids: SkillIds | None = None

    _no_nulls = field_validator("text", "sort_order", "skill_ids")(reject_null)


class BulletSkillRead(CamelModel):
    id: uuid.UUID
    name: str
    category: SkillCategory


class BulletRead(CamelModel):
    id: uuid.UUID
    text: str
    sort_order: int
    skills: list[BulletSkillRead]


# ---------- experiences ----------


class ExperienceCreate(CamelInputModel):
    """endDate may be in the future on purpose, e.g. a contract with a fixed end date."""

    company: ShortText
    title: ShortText
    location: ShortText | None = None
    start_date: StartDate
    end_date: date | None = None

    @model_validator(mode="after")
    def end_not_before_start(self) -> Self:
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("endDate cannot be earlier than startDate")
        return self


class ExperienceUpdate(CamelInputModel):
    """Date order is checked in the service: a PATCH may carry only one of the two dates."""

    company: ShortText | None = None
    title: ShortText | None = None
    location: ShortText | None = None
    start_date: StartDate | None = None
    end_date: date | None = None

    _no_nulls = field_validator("company", "title", "start_date")(reject_null)


class ExperienceRead(CamelModel):
    id: uuid.UUID
    company: str
    title: str
    location: str | None
    start_date: date
    end_date: date | None
    bullets: list[BulletRead]
