import uuid
from collections.abc import Sequence
from typing import NoReturn

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError, NotFoundError
from app.modules.skills.models import Skill
from app.modules.skills.schemas import SkillCreate, SkillUpdate

UNIQUE_NAME_INDEX = "uq_skills_name_lower"


async def list_skills(session: AsyncSession) -> Sequence[Skill]:
    query = select(Skill).order_by(Skill.level.desc(), Skill.name)
    result = await session.scalars(query)
    return result.all()


async def get_skill(session: AsyncSession, skill_id: uuid.UUID) -> Skill:
    skill = await session.get(Skill, skill_id)
    if skill is None:
        raise NotFoundError(f"Skill {skill_id} not found")
    return skill


async def create_skill(session: AsyncSession, data: SkillCreate) -> Skill:
    skill = Skill(**data.model_dump())
    try:
        async with session.begin_nested():
            session.add(skill)
    except IntegrityError as exc:
        _raise_for_integrity_error(exc, data.name)
    return skill


async def update_skill(session: AsyncSession, skill_id: uuid.UUID, data: SkillUpdate) -> Skill:
    skill = await get_skill(session, skill_id)
    changes = data.model_dump(exclude_unset=True)
    new_name = changes.get("name", skill.name)
    try:
        async with session.begin_nested():
            for field, value in changes.items():
                setattr(skill, field, value)
    except IntegrityError as exc:
        await session.refresh(skill)
        _raise_for_integrity_error(exc, new_name)
    await session.refresh(skill)
    return skill


async def delete_skill(session: AsyncSession, skill_id: uuid.UUID) -> None:
    skill = await get_skill(session, skill_id)
    await session.delete(skill)
    await session.flush()


def _raise_for_integrity_error(exc: IntegrityError, name: str) -> NoReturn:
    """Turn a duplicate-name violation into ConflictError; re-raise anything else unchanged."""
    if UNIQUE_NAME_INDEX in str(exc.orig):
        raise ConflictError(f"Skill '{name}' already exists") from exc
    raise exc
