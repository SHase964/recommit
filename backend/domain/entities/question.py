from __future__ import annotations

from pydantic import BaseModel, StrictStr, field_validator

from backend.domain.value_objects import Category, Choice, Choices, CorrectIndex, Source


class Question(BaseModel):
    prompt: StrictStr
    choices: Choices
    correct_index: CorrectIndex
    explanation: StrictStr
    category: Category
    source: Source

    @field_validator("prompt")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("問題文が空です")
        return v

    @property
    def correct_choice(self) -> Choice:
        return self.choices[self.correct_index]
