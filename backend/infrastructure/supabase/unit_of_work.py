from __future__ import annotations

from sqlalchemy.orm import Session

from backend.domain.repositories.checkpoint_repository import ICheckpointRepository
from backend.domain.repositories.question_repository import IQuestionRepository
from backend.domain.repositories.source_document_repository import ISourceDocumentRepository
from backend.domain.services.unit_of_work import IUnitOfWork
from backend.infrastructure.supabase.checkpoint_repository import SupabaseCheckpointRepository
from backend.infrastructure.supabase.question_repository import SupabaseQuestionRepository
from backend.infrastructure.supabase.source_document_repository import SupabaseSourceDocumentRepository


class SupabaseUnitOfWork(IUnitOfWork):
    def __init__(self, session: Session) -> None:
        self._session = session
        self._source_documents = SupabaseSourceDocumentRepository(session)
        self._questions = SupabaseQuestionRepository(session)
        self._checkpoints = SupabaseCheckpointRepository(session)

    @property
    def source_documents(self) -> ISourceDocumentRepository:
        return self._source_documents

    @property
    def questions(self) -> IQuestionRepository:
        return self._questions

    @property
    def checkpoints(self) -> ICheckpointRepository:
        return self._checkpoints

    def commit(self) -> None:
        self._session.commit()

    def rollback(self) -> None:
        self._session.rollback()
