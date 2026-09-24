from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.quiz.loader import load_quiz, QUIZ_PATH

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    bot_token: str
    database_url: str

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        extra="ignore",
    )


settings = Settings()
quiz = load_quiz(QUIZ_PATH)