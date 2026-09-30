import asyncio
import json
import logging

import gspread

from app.config import settings
from app.quiz.schema import Quiz

SHEET_NAME = "leadbot-sheet"


def _append_row_sync(answers: dict, quiz: Quiz) -> None:
    credentials_dict = json.loads(settings.google_credentials_json)
    gc = gspread.service_account_from_dict(credentials_dict)
    sh = gc.open(SHEET_NAME)
    worksheet = sh.sheet1
    row = [answers.get(step.id, "—") for step in quiz.steps]
    worksheet.append_row(row)


async def append_lead_to_sheet(quiz: Quiz, answers: dict) -> None:
    try:
        await asyncio.to_thread(_append_row_sync, answers, quiz)
    except Exception:
        logging.exception("Unable to write lead to Google Sheets")