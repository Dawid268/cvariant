import uuid
from datetime import UTC, datetime
from typing import Annotated

from pydantic import AfterValidator, Field, StringConstraints, field_validator

from app.core.schemas import CamelInputModel, CamelModel
from app.modules.skills.enums import SkillCategory


def _not_in_future(year: int | None) -> int | None:
    if year is not None and year > datetime.now(UTC).year:
        raise ValueError("cannot be in the future")
    return year


SkillName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
Level = Annotated[int, Field(ge=1, le=5)]
Years = Annotated[float, Field(ge=0, le=50)]
LastUsedYear = Annotated[int | None, Field(ge=1970), AfterValidator(_not_in_future)]


class SkillCreate(CamelInputModel):
    name: SkillName
    category: SkillCategory
    level: Level
    years: Years
    last_used_year: LastUsedYear = None


class SkillUpdate(CamelInputModel):
    """PATCH body: every field is optional, only the fields that were sent are changed."""

    name: SkillName | None = None
    category: SkillCategory | None = None
    level: Level | None = None
    years: Years | None = None
    last_used_year: LastUsedYear = None

    @field_validator("name", "category", "level", "years")
    @classmethod
    def reject_explicit_null(cls, value: object) -> object:
        # Runs only for fields present in the request; omitted fields keep their default.
        # These columns are NOT NULL, so an explicit null must be a 422, not a database error.
        if value is None:
            raise ValueError("cannot be null")
        return value


class SkillRead(CamelModel):
    id: uuid.UUID
    name: str
    category: SkillCategory
    level: int
    years: float
    last_used_year: int | None
