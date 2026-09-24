from pathlib import Path
import yaml

from app.quiz.schema import Quiz

BASE_DIR = Path(__file__).resolve().parent.parent.parent
QUIZ_PATH = BASE_DIR / "configs" / "quiz.yaml"


def load_quiz(path: Path) -> Quiz:
    with open(path) as f:
        data = yaml.safe_load(f)
        quiz = Quiz(**data)
    return quiz