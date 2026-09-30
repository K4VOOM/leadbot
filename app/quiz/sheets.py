import asyncio
import logging
from pathlib import Path

import gspread

from app.quiz.schema import Quiz

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CREDENTIALS_PATH = BASE_DIR / "secrets" / "google_credentials.json"

SHEET_NAME = "leadbot-sheet"


def _append_row_sync(answers: dict, quiz: Quiz) -> None:
    gc = gspread.service_account(filename=str(CREDENTIALS_PATH))
    sh = gc.open(SHEET_NAME)
    worksheet = sh.sheet1
    row = [answers.get(step.id, "—") for step in quiz.steps]
    worksheet.append_row(row)


async def append_lead_to_sheet(quiz: Quiz, answers: dict) -> None:
    try:
        await asyncio.to_thread(_append_row_sync, answers, quiz)
    except Exception:
        logging.exception("Unable to write lead to Google Sheets")