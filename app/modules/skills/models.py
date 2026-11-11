from sqlalchemy import CheckConstraint, Enum, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.core.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.skills.enums import SkillCategory


class Skill(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "skills"
    __table_args__ = (
        CheckConstraint("level BETWEEN 1 AND 5", name="level_range"),
        CheckConstraint("years >= 0", name="years_non_negative"),
    )

    name: Mapped[str] = mapped_column(String(64))
    category: Mapped[SkillCategory] = mapped_column(
        Enum(
            SkillCategory,
            native_enum=False,
            length=32,
            values_callable=lambda enum: [member.value for member in enum],
        ),
    )
    level: Mapped[int]
    years: Mapped[float]
    last_used_year: Mapped[int | None]  # None = still in use


# "Angular" and "angular" are the same skill
Index("uq_skills_name_lower", func.lower(Skill.name), unique=True)
