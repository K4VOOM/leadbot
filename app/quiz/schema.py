from pydantic import BaseModel
from typing import Literal

class BotSetting(BaseModel):
    welcome: str
    finish: str
    manager_chat_id: int

class Step(BaseModel):
    id: str
    text: str
    type: Literal["choice", "multi_choice", "text", "phone", "email"]
    options: list[str] | None = None
    required: bool = True

class Quiz(BaseModel):
    bot: BotSetting
    steps: list[Step]