import uuid
from datetime import date

from sqlalchemy import CheckConstraint, Column, ForeignKey, String, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.core.models import TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.skills.models import Skill

bullet_skills = Table(
    "bullet_skills",
    Base.metadata,
    Column(
        "bullet_id",
        ForeignKey("experience_bullets.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "skill_id",
        ForeignKey("skills.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    ),
)


class Experience(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experiences"
    __table_args__ = (
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="dates_in_order"),
    )

    company: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(128))
    location: Mapped[str | None] = mapped_column(String(128))
    start_date: Mapped[date]
    end_date: Mapped[date | None]  # None = current position

    bullets: Mapped[list["ExperienceBullet"]] = relationship(
        back_populates="experience",
        cascade="all, delete-orphan",
        # created_at and id make the order deterministic when sort_order values are equal
        order_by=lambda: [
            ExperienceBullet.sort_order,
            ExperienceBullet.created_at,
            ExperienceBullet.id,
        ],
        lazy="selectin",
    )


class ExperienceBullet(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "experience_bullets"

    experience_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("experiences.id", ondelete="CASCADE"),
        index=True,
    )
    text: Mapped[str] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(default=0)

    experience: Mapped[Experience] = relationship(back_populates="bullets")
    skills: Mapped[list[Skill]] = relationship(
        secondary=bullet_skills,
        order_by=Skill.name,
        lazy="selectin",
    )
