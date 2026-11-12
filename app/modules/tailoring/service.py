from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.experience import service as experience_service
from app.modules.skills.models import Skill
from app.modules.tailoring.schemas import TailoringRequest
from app.modules.tailoring.scoring import TailoringOptions, TailoringResult, tailor


async def preview(session: AsyncSession, request: TailoringRequest) -> TailoringResult:
    """Tailor the whole profile to one offer without saving anything."""
    skills = (await session.scalars(select(Skill).order_by(Skill.name))).all()
    # Newest positions first; bullets and their skills come with them (lazy="selectin")
    experiences = await experience_service.list_experiences(session)

    return tailor(
        [requirement.to_domain() for requirement in request.requirements],
        skills,
        experiences,
        TailoringOptions(
            skill_limit=request.skill_limit,
            bullets_per_experience=request.bullets_per_experience,
            current_year=datetime.now(UTC).year,
        ),
    )
