import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import BusinessRuleError, NotFoundError
from app.modules.experience.models import Experience, ExperienceBullet
from app.modules.experience.schemas import (
    BulletCreate,
    BulletUpdate,
    ExperienceCreate,
    ExperienceUpdate,
)
from app.modules.skills.models import Skill

# ---------- experiences ----------


async def list_experiences(session: AsyncSession) -> Sequence[Experience]:
    query = select(Experience).order_by(
        Experience.end_date.desc().nulls_first(),
        Experience.start_date.desc(),
        Experience.id,  # deterministic order for identical dates
    )
    result = await session.scalars(query)
    return result.all()


async def get_experience(session: AsyncSession, experience_id: uuid.UUID) -> Experience:
    experience = await session.get(Experience, experience_id)
    if experience is None:
        raise NotFoundError(f"Experience {experience_id} not found")
    return experience


async def create_experience(session: AsyncSession, data: ExperienceCreate) -> Experience:
    experience = Experience(**data.model_dump(), bullets=[])
    session.add(experience)
    await session.flush()
    return experience


async def update_experience(
    session: AsyncSession,
    experience_id: uuid.UUID,
    data: ExperienceUpdate,
) -> Experience:
    experience = await get_experience(session, experience_id)
    changes = data.model_dump(exclude_unset=True)

    start = changes.get("start_date", experience.start_date)
    end = changes.get("end_date", experience.end_date)
    if end is not None and end < start:
        raise BusinessRuleError("endDate cannot be earlier than startDate")

    for field, value in changes.items():
        setattr(experience, field, value)
    await session.flush()
    return await _reload(session, experience_id)


async def delete_experience(session: AsyncSession, experience_id: uuid.UUID) -> None:
    # One DELETE: the database cascades to bullets and their skill tags (ON DELETE CASCADE),
    # so there is no need to load them first.
    query = delete(Experience).where(Experience.id == experience_id).returning(Experience.id)
    if await session.scalar(query) is None:
        raise NotFoundError(f"Experience {experience_id} not found")


# ---------- bullets ----------


async def create_bullet(
    session: AsyncSession,
    experience_id: uuid.UUID,
    data: BulletCreate,
) -> ExperienceBullet:
    experience = await get_experience(session, experience_id)
    sort_order = data.sort_order
    if sort_order is None:
        sort_order = max((b.sort_order for b in experience.bullets), default=-1) + 1
    bullet = ExperienceBullet(
        text=data.text,
        sort_order=sort_order,
        skills=await _load_skills(session, data.skill_ids),
    )
    experience.bullets.append(bullet)
    await session.flush()
    return bullet


async def update_bullet(
    session: AsyncSession,
    experience_id: uuid.UUID,
    bullet_id: uuid.UUID,
    data: BulletUpdate,
) -> ExperienceBullet:
    _, bullet = await _get_bullet(session, experience_id, bullet_id)
    changes = data.model_dump(exclude_unset=True)
    if "skill_ids" in changes:
        bullet.skills = await _load_skills(session, changes.pop("skill_ids"))
    for field, value in changes.items():
        setattr(bullet, field, value)
    await session.flush()
    await session.refresh(bullet, attribute_names=["updated_at"])
    return bullet


async def delete_bullet(
    session: AsyncSession,
    experience_id: uuid.UUID,
    bullet_id: uuid.UUID,
) -> None:
    experience, bullet = await _get_bullet(session, experience_id, bullet_id)
    experience.bullets.remove(bullet)  # delete-orphan deletes the row and keeps the list in sync
    await session.flush()


# ---------- helpers ----------


async def _reload(session: AsyncSession, experience_id: uuid.UUID) -> Experience:
    """Re-read the experience with its bullets and their skills, replacing stale state."""
    query = (
        select(Experience)
        .where(Experience.id == experience_id)
        .execution_options(populate_existing=True)
    )
    return (await session.scalars(query)).one()


async def _get_bullet(
    session: AsyncSession,
    experience_id: uuid.UUID,
    bullet_id: uuid.UUID,
) -> tuple[Experience, ExperienceBullet]:
    """Find the bullet inside its experience, so a bullet of another experience is a 404."""
    experience = await get_experience(session, experience_id)
    for bullet in experience.bullets:
        if bullet.id == bullet_id:
            return experience, bullet
    raise NotFoundError(f"Bullet {bullet_id} not found in experience {experience_id}")


async def _load_skills(session: AsyncSession, skill_ids: list[uuid.UUID]) -> list[Skill]:
    if not skill_ids:
        return []
    result = await session.scalars(select(Skill).where(Skill.id.in_(skill_ids)))
    skills = list(result.all())
    missing = set(skill_ids) - {skill.id for skill in skills}
    if missing:
        raise BusinessRuleError(f"Unknown skills: {', '.join(sorted(map(str, missing)))}")
    return skills
