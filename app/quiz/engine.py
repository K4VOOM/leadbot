import logging
import re

from aiogram import Bot
from aiogram.fsm.state import State, StatesGroup

from app.quiz.schema import Quiz, Step
from app.quiz.keyboards import build_lead_keyboard


class QuizStates(StatesGroup):
    in_progress = State()


def get_current_step(quiz: Quiz, step_index: int) -> Step | None:
    if step_index >= len(quiz.steps):
        return None
    return quiz.steps[step_index]


def validate_answer(step: Step, text: str) -> str | None:
    match step.type:
        case "choice":
            if text not in step.options:
                return "Оберіть вірну опцію"
        case "email":
            if re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", text) is None:
                return "Введіть дійсну адресу"
        case "phone":
            phone = text
            phone = phone.replace(" ", "")
            phone = phone.replace("-", "")
            if phone[0:1] == "+":
                phone = phone[1:]
            if phone[0:2] == "38":
                phone = phone[2:]
            if len(phone) != 10:
                return "Введіть дійсний номер"
        case "text":
            ...
        case "multi_choice":
            ...
    return None


def format_lead_summary(quiz: Quiz, answers: dict) -> str:
    lines = []
    for step in quiz.steps:
        answer = answers.get(step.id, "—")
        lines.append(f"{step.text}: {answer}")
    return "\n".join(lines)


async def notify_manager(bot: Bot, quiz: Quiz, answers: dict, lead_id: int) -> None:
    text = format_lead_summary(quiz, answers)
    try:
        await bot.send_message(chat_id=quiz.bot.manager_chat_id, text=text, reply_markup=build_lead_keyboard(lead_id))
    except Exception:
        logging.exception("Unable to send a notification to the manager")