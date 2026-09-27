from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime, timedelta, timezone

from app.db.models import User, Lead


async def get_or_create_user(
        session: AsyncSession,
        tg_id: int,
        username: str | None,
        first_name: str | None,
        utm_source: str | None,
        utm_campaign: str | None,
) -> User:
    stmt = insert(User).values(
        tg_id=tg_id,
        username=username,
        first_name=first_name,
        utm_source=utm_source,
        utm_campaign=utm_campaign,
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=["tg_id"])

    await session.execute(stmt)

    result = await session.execute(
        select(User).where(User.tg_id == tg_id)
    )
    return result.scalar_one()


async def has_recent_lead(session: AsyncSession, user_id: int, hours: int = 24) -> bool:
    threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
    stmt = select(Lead).where(Lead.user_id == user_id, Lead.created_at >= threshold)
    result = await session.execute(stmt)
    lead = result.scalars().first()
    return lead is not None