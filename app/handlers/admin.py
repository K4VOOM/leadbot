import csv
import io
import asyncio

from aiogram import F, Router, Bot
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest
from aiogram.fsm.context import FSMContext

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.repo import get_stats
from app.config import quiz
from app.db.models import Lead
from app.db.models import User
from app.quiz.engine import BroadcastStates

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

@admin_router.message(Command("broadcast"))
async def broadcast_start_handler(message: Message, state: FSMContext) -> None:
    await message.answer("Надішліть текст розсилки:")
    await state.set_state(BroadcastStates.waiting_for_text)

@admin_router.message(BroadcastStates.waiting_for_text)
async def broadcast_send_handler(message: Message, state: FSMContext, session: AsyncSession, bot: Bot) -> None:
    await state.clear()
    text = message.text

    result = await session.execute(select(User).where(User.subscribed == True))
    users = result.scalars().all()

    sent = 0
    failed = 0
    for user in users:
        try:
            await bot.send_message(chat_id=user.tg_id, text=text)
            sent += 1
        except (TelegramForbiddenError, TelegramBadRequest):
            user.subscribed = False
            failed += 1
        await asyncio.sleep(0.05)

    await message.answer(f"Розіслано: {sent}, не вдалось: {failed}")