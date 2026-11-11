import uuid

from fastapi import APIRouter, status

from app.core.db import SessionDep
from app.modules.skills import service
from app.modules.skills.schemas import SkillCreate, SkillRead, SkillUpdate

router = APIRouter(prefix="/skills", tags=["skills"])


@router.get("")
async def list_skills(session: SessionDep) -> list[SkillRead]:
    skills = await service.list_skills(session)
    return [SkillRead.model_validate(skill) for skill in skills]


@router.get("/{skill_id}")
async def get_skill(skill_id: uuid.UUID, session: SessionDep) -> SkillRead:
    skill = await service.get_skill(session, skill_id)
    return SkillRead.model_validate(skill)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_skill(payload: SkillCreate, session: SessionDep) -> SkillRead:
    skill = await service.create_skill(session, payload)
    return SkillRead.model_validate(skill)


@router.patch("/{skill_id}")
async def update_skill(skill_id: uuid.UUID, payload: SkillUpdate, session: SessionDep) -> SkillRead:
    skill = await service.update_skill(session, skill_id, payload)
    return SkillRead.model_validate(skill)


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(skill_id: uuid.UUID, session: SessionDep) -> None:
    await service.delete_skill(session, skill_id)
