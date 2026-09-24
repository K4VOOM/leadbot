import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import settings
from app.db.session import async_session
from app.middlewares.db import DbSessionMiddleware

from app.handlers.start import router as start_router

TOKEN = settings.bot_token

dp = Dispatcher()
dp.include_router(start_router)

dp.update.outer_middleware(DbSessionMiddleware(session_pool=async_session))


async def main() -> None:
  bot = Bot(
      token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML)
  )

  await dp.start_polling(bot)


if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO, stream=sys.stdout)
  asyncio.run(main())