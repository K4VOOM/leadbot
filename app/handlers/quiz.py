from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import quiz
from app.quiz.engine import QuizStates, get_current_step
from app.db.repo import get_or_create_user
from app.db.models import Lead

router = Router()


@router.message(QuizStates.in_progress)
async def quiz_answer_handler(
    message: Message, state: FSMContext, session: AsyncSession
) -> None:
    data = await state.get_data()
    step_index = data["step_index"]
    answers = data["answers"]

    current_step = get_current_step(quiz, step_index)
    if current_step is None:
        return

    answers[current_step.id] = message.text
    next_index = step_index + 1
    next_step = get_current_step(quiz, next_index)

    if next_step is not None:
        await state.update_data(step_index=next_index, answers=answers)
        await message.answer(next_step.text)
    else:
        user = await get_or_create_user(
            session=session,
            tg_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            utm_source=None,
            utm_campaign=None,
        )
        lead = Lead(user_id=user.id, answers=answers)
        session.add(lead)
        await message.answer(quiz.bot.finish)
        await state.clear()