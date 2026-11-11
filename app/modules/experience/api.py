import uuid

from fastapi import APIRouter, status

from app.core.db import SessionDep
from app.modules.experience import service
from app.modules.experience.schemas import (
    BulletCreate,
    BulletRead,
    BulletUpdate,
    ExperienceCreate,
    ExperienceRead,
    ExperienceUpdate,
)

router = APIRouter(prefix="/experiences", tags=["experience"])


@router.get("")
async def list_experiences(session: SessionDep) -> list[ExperienceRead]:
    experiences = await service.list_experiences(session)
    return [ExperienceRead.model_validate(experience) for experience in experiences]


@router.get("/{experience_id}")
async def get_experience(experience_id: uuid.UUID, session: SessionDep) -> ExperienceRead:
    experience = await service.get_experience(session, experience_id)
    return ExperienceRead.model_validate(experience)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_experience(payload: ExperienceCreate, session: SessionDep) -> ExperienceRead:
    experience = await service.create_experience(session, payload)
    return ExperienceRead.model_validate(experience)


@router.patch("/{experience_id}")
async def update_experience(
    experience_id: uuid.UUID,
    payload: ExperienceUpdate,
    session: SessionDep,
) -> ExperienceRead:
    experience = await service.update_experience(session, experience_id, payload)
    return ExperienceRead.model_validate(experience)


@router.delete("/{experience_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_experience(experience_id: uuid.UUID, session: SessionDep) -> None:
    await service.delete_experience(session, experience_id)


@router.post("/{experience_id}/bullets", status_code=status.HTTP_201_CREATED)
async def create_bullet(
    experience_id: uuid.UUID,
    payload: BulletCreate,
    session: SessionDep,
) -> BulletRead:
    bullet = await service.create_bullet(session, experience_id, payload)
    return BulletRead.model_validate(bullet)


@router.patch("/{experience_id}/bullets/{bullet_id}")
async def update_bullet(
    experience_id: uuid.UUID,
    bullet_id: uuid.UUID,
    payload: BulletUpdate,
    session: SessionDep,
) -> BulletRead:
    bullet = await service.update_bullet(session, experience_id, bullet_id, payload)
    return BulletRead.model_validate(bullet)


@router.delete("/{experience_id}/bullets/{bullet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_bullet(
    experience_id: uuid.UUID,
    bullet_id: uuid.UUID,
    session: SessionDep,
) -> None:
    await service.delete_bullet(session, experience_id, bullet_id)
