from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.repo import get_stats

admin_router = Router()
admin_router.message.filter(F.from_user.id.in_(settings.admin_ids))

@admin_router.message(Command("stats"))
async def stats_handler(message: Message, session: AsyncSession) -> None:
    stats = await get_stats(session)
    await message.answer(f"Усього лідів: {stats['total']}\nЗа сьогодні: {stats['today']}")