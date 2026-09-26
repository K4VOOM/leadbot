from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from app.quiz.schema import Step


def build_keyboard(step: Step) -> ReplyKeyboardMarkup | None:
    if step.options is None:
        return ReplyKeyboardRemove()
    else:
        builder = ReplyKeyboardBuilder()
        for option in step.options:
            builder.button(text=option)
        builder.button(text="❌Скасувати")
        builder.adjust(1)
        return builder.as_markup(resize_keyboard=True)