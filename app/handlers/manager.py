from aiogram import Router
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import quiz
from app.db.repo import set_lead_status
from app.quiz.engine import format_lead_message
from app.quiz.keyboards import LeadAction, build_lead_keyboard


router = Router()


@router.callback_query(LeadAction.filter())
async def lead_action_handler(
    callback: CallbackQuery, callback_data: LeadAction, session: AsyncSession
) -> None:
    lead = await set_lead_status(session, callback_data.lead_id, callback_data.action)
    if lead is None:
        await callback.answer("Заявку не знайдено", show_alert=True)
        return

    text = format_lead_message(quiz, lead.answers, lead.status)
    try:
        await callback.message.edit_text(text, reply_markup=build_lead_keyboard(lead.id))
    except TelegramRetryAfter as e:
        await session.rollback()
        await callback.answer(f"Забагато змін, зачекайте {e.retry_after} с", show_alert=True)
        return
    except TelegramBadRequest as e:
        if "message is not modified" not in str(e):
            raise
    await callback.answer("Статус оновлено")