from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import User


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