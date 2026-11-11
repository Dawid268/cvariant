from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from app.core import db
from app.modules.skills.enums import SkillCategory
from app.modules.skills.models import Skill

# The API tests replace get_session with a test double, so its real commit and
# rollback logic is exercised here, inside the rolled-back test transaction.


@pytest.fixture
def sessions_on_test_transaction(
    db_connection: AsyncConnection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def factory() -> AsyncSession:
        return AsyncSession(
            bind=db_connection,
            join_transaction_mode="create_savepoint",
            expire_on_commit=False,
        )

    monkeypatch.setattr(db, "session_factory", factory)


def _skill() -> Skill:
    return Skill(name="Angular", category=SkillCategory.FRONTEND, level=5, years=6)


async def _count_skills(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(Skill)) or 0


@pytest.mark.usefixtures("sessions_on_test_transaction")
async def test_get_session_commits_when_the_request_succeeds(db_session: AsyncSession) -> None:
    # GIVEN
    sessions: AsyncGenerator[AsyncSession] = db.get_session()
    session = await anext(sessions)
    session.add(_skill())

    # WHEN - the request finishes normally
    with pytest.raises(StopAsyncIteration):
        await anext(sessions)

    # THEN
    assert await _count_skills(db_session) == 1


@pytest.mark.usefixtures("sessions_on_test_transaction")
async def test_get_session_rolls_back_when_the_request_fails(db_session: AsyncSession) -> None:
    # GIVEN
    sessions = db.get_session()
    session = await anext(sessions)
    session.add(_skill())
    await session.flush()

    # WHEN - the request raises
    with pytest.raises(RuntimeError, match="boom"):
        await sessions.athrow(RuntimeError("boom"))

    # THEN
    assert await _count_skills(db_session) == 0
