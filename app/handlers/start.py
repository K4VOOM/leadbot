from aiogram import Router, html
from aiogram.filters import CommandStart
from aiogram.filters.command import CommandObject
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repo import get_or_create_user

router = Router()

@router.message(CommandStart())
async def command_start_handler(message: Message, command: CommandObject, session: AsyncSession) -> None:
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

    name = html.quote(message.from_user.full_name)
    await message.answer(f"Привіт, {name}!")