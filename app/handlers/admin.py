import csv
import io

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.repo import get_stats
from app.config import quiz
from app.db.models import Lead

admin_router = Router()
admin_router.message.filter(F.from_user.id.in_(settings.admin_ids))


@admin_router.message(Command("stats"))
async def stats_handler(message: Message, session: AsyncSession) -> None:
    stats = await get_stats(session)
    await message.answer(f"Усього лідів: {stats['total']}\nЗа сьогодні: {stats['today']}")

@admin_router.message(Command("export"))
async def export_handler(message: Message, session: AsyncSession) -> None:
    result = await session.execute(select(Lead).order_by(Lead.created_at))
    leads = result.scalars().all()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "user_id", "status", "created_at", *[step.id for step in quiz.steps]])
    for lead in leads:
        writer.writerow([lead.id, lead.user_id, lead.status, lead.created_at,
                         *[lead.answers.get(step.id, "") for step in quiz.steps]])

    file = BufferedInputFile(buffer.getvalue().encode("utf-8-sig"), filename="leads.csv")
    await message.answer_document(file)