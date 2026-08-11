from __future__ import annotations

import pytest

from backend.domain.entities import Question
from backend.domain.repositories.question_repository import IQuestionRepository
from backend.domain.repositories.source_document_repository import ISourceDocumentRepository
from backend.domain.services.unit_of_work import IUnitOfWork
from backend.domain.value_objects import SourceDocument


class _FakeQuestionRepository(IQuestionRepository):
    def save(self, questions: list[Question]) -> None:
        pass


class _FakeSourceDocumentRepository(ISourceDocumentRepository):
    def save(self, document: SourceDocument) -> None:
        pass


class _FakeUnitOfWork(IUnitOfWork):
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self._source_documents = _FakeSourceDocumentRepository()
        self._questions = _FakeQuestionRepository()

    @property
    def source_documents(self) -> ISourceDocumentRepository:
        return self._source_documents

    @property
    def questions(self) -> IQuestionRepository:
        return self._questions

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class TestExit:
    def test_commits_when_block_succeeds(self) -> None:
        uow = _FakeUnitOfWork()

        with uow:
            pass

        assert uow.committed is True
        assert uow.rolled_back is False

    def test_rolls_back_and_reraises_when_block_raises(self) -> None:
        uow = _FakeUnitOfWork()

        with pytest.raises(RuntimeError, match="boom"):
            with uow:
                raise RuntimeError("boom")

        assert uow.committed is False
        assert uow.rolled_back is True
