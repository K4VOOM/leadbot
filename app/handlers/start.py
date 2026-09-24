from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.filters.command import CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repo import get_or_create_user
from app.quiz.engine import QuizStates, get_current_step
from app.config import quiz

router = Router()

@router.message(CommandStart())
async def command_start_handler(
        message: Message,
        command: CommandObject,
        session: AsyncSession,
        state: FSMContext) -> None:
    utm_source = None
    utm_campaign = None
    if command.args is not None:
        utm_split = command.args.split("-",1)
        if len(utm_split) == 2:
            utm_source = utm_split[0]
            utm_campaign = utm_split[1]
        else:
            utm_source = utm_split[0]

    user = await get_or_create_user(
        session=session,
        tg_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name,
        utm_source=utm_source,
        utm_campaign=utm_campaign,
    )

    await state.update_data(step_index=0, answers={})
    await state.set_state(QuizStates.in_progress)

    await message.answer(quiz.bot.welcome)

    first_step = get_current_step(quiz, 0)
    if first_step is not None:
        await message.answer(first_step.text)