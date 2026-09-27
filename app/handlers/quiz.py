import logging

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram import F, Bot, Router
from aiogram.types import ReplyKeyboardRemove

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import quiz
from app.db.models import Lead
from app.db.repo import get_or_create_user, has_recent_lead
from app.quiz.keyboards import build_keyboard
from app.quiz.engine import QuizStates, get_current_step

import re

router = Router()


@router.message(QuizStates.in_progress, F.text == "❌Скасувати")
async def cancel_quiz_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Квіз скасовано.", reply_markup=ReplyKeyboardRemove())


@router.message(QuizStates.in_progress)
async def quiz_answer_handler(
        message: Message, state: FSMContext, session: AsyncSession, bot: Bot
) -> None:
    data = await state.get_data()
    step_index = data["step_index"]
    answers = data["answers"]

    current_step = get_current_step(quiz, step_index)
    if current_step is None:
        return

    match current_step.type:
        case "choice":
            if message.text not in current_step.options:
                await message.answer("Оберіть вірну опцію", reply_markup=build_keyboard(current_step))
                return
        case "email":
            if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", message.text) is None:
                await message.answer("Введіть дійсну адресу", reply_markup=build_keyboard(current_step))
                return
        case "phone":
            phone = message.text
            phone = phone.replace(" ", "")
            phone = phone.replace("-", "")
            if phone[0:1] == "+":
                phone = phone[1:]
            if phone[0:2] == "38":
                phone = phone[2:]
            if len(phone) != 10:
                await message.answer("Введіть дійсний номер", reply_markup=build_keyboard(current_step))
                return
        case "text":
            ...
        case "multi_choice":
            ...

    answers[current_step.id] = message.text
    next_index = step_index + 1
    next_step = get_current_step(quiz, next_index)

    if next_step is not None:
        await state.update_data(step_index=next_index, answers=answers)
        keyboard = build_keyboard(next_step)
        await message.answer(next_step.text, reply_markup=keyboard)
    else:
        user = await get_or_create_user(
            session=session,
            tg_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            utm_source=None,
            utm_campaign=None,
        )

        if await has_recent_lead(session, user.id):
            await message.answer("Ви вже залишали заявку нещодавно, ми зв'яжемось з вами найближчим часом")
        else:
            lead = Lead(user_id=user.id, answers=answers)
            session.add(lead)

            lines = []
            for step in quiz.steps:
                answer = answers.get(step.id, "—")
                lines.append(f"{step.text}: {answer}")
            text = "\n".join(lines)

            try:
                await bot.send_message(chat_id=quiz.bot.manager_chat_id, text=text)
            except Exception:
                logging.exception("Unable to send a notification to the manager")

            await message.answer(quiz.bot.finish)

        await state.clear()