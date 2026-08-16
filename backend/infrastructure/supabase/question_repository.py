from __future__ import annotations

from sqlalchemy.orm import Session

from backend.domain.entities import Question
from backend.domain.repositories.question_repository import IQuestionRepository
from backend.infrastructure.supabase.models import QuestionModel


class SupabaseQuestionRepository(IQuestionRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, questions: list[Question]) -> None:
        self._session.add_all(QuestionModel.from_domain(question) for question in questions)
