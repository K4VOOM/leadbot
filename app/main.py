import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import async_session
from app.middlewares.db import DbSessionMiddleware

TOKEN = settings.bot_token

dp = Dispatcher()

dp.update.outer_middleware(DbSessionMiddleware(session_pool=async_session))


@dp.message(CommandStart())
async def command_start_handler(message: Message, session: AsyncSession) -> None:
    name = html.quote(message.from_user.full_name)
    await message.answer(f"Привіт, {name}!")


@dp.message()
async def echo_handler(message: Message) -> None:
  try:
    await message.send_copy(chat_id=message.chat.id)
  except TypeError:
    await message.answer("Я розумію лише текстові повідомлення!")


async def main() -> None:
  bot = Bot(
      token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
  )

  await dp.start_polling(bot)


if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO, stream=sys.stdout)
  asyncio.run(main())