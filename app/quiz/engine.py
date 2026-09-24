from aiogram.fsm.state import State, StatesGroup
from app.quiz.schema import Quiz, Step

class QuizStates(StatesGroup):
    in_progress = State()

def get_current_step(quiz: Quiz, step_index: int) -> Step | None:
    if step_index >= len(quiz.steps):
        return None
    return quiz.steps[step_index]