from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from aiogram.filters.callback_data import CallbackData

from app.quiz.schema import Step


class LeadAction(CallbackData, prefix="lead"):
    lead_id: int
    action: str


def build_keyboard(step: Step) -> ReplyKeyboardMarkup | ReplyKeyboardRemove:
    if step.options is None:
        return ReplyKeyboardRemove()
    else:
        builder = ReplyKeyboardBuilder()
        for option in step.options:
            builder.button(text=option)
        builder.button(text="❌Скасувати")
        builder.adjust(1)
        return builder.as_markup(resize_keyboard=True)


def build_lead_keyboard(lead_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Взяв у роботу",
        callback_data=LeadAction(lead_id=lead_id, action="in_work"),
    )
    builder.button(
        text="🔒 Закрито",
        callback_data=LeadAction(lead_id=lead_id, action="closed"),
    )
    builder.adjust(1)
    return builder.as_markup()