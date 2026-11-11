import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ConflictError
from app.modules.skills import service
from app.modules.skills.enums import SkillCategory
from app.modules.skills.schemas import SkillCreate


async def test_integrity_error_other_than_duplicate_name_is_not_masked(
    db_session: AsyncSession,
) -> None:
    # GIVEN - bypass Pydantic validation to hit the database CHECK constraint directly
    invalid = SkillCreate.model_construct(
        name="Angular",
        category=SkillCategory.FRONTEND,
        level=7,
        years=1,
        last_used_year=None,
    )

    # WHEN / THEN - the original database error surfaces, not a misleading 409
    with pytest.raises(IntegrityError) as exc_info:
        await service.create_skill(db_session, invalid)
    assert not isinstance(exc_info.value, ConflictError)
    assert "ck_skills_level_range" in str(exc_info.value.orig)
