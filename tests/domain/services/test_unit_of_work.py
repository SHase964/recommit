from __future__ import annotations

from datetime import datetime

import pytest

from backend.domain.entities import Question
from backend.domain.repositories.checkpoint_repository import ICheckpointRepository
from backend.domain.repositories.question_repository import IQuestionRepository
from backend.domain.repositories.source_document_repository import ISourceDocumentRepository
from backend.domain.services.unit_of_work import IUnitOfWork
from backend.domain.value_objects import SourceDocument, SourceType


class _FakeQuestionRepository(IQuestionRepository):
    def save(self, questions: list[Question]) -> None:
        pass


class _FakeSourceDocumentRepository(ISourceDocumentRepository):
    def save(self, document: SourceDocument) -> None:
        pass


class _FakeCheckpointRepository(ICheckpointRepository):
    def find_last_processed_at(self, source_type: SourceType) -> datetime | None:
        return None

    def save(self, source_type: SourceType, processed_at: datetime) -> None:
        pass


class _FakeUnitOfWork(IUnitOfWork):
    def __init__(self, *, fail_on_commit: bool = False) -> None:
        self.committed = False
        self.rolled_back = False
        self._fail_on_commit = fail_on_commit
        self._source_documents = _FakeSourceDocumentRepository()
        self._questions = _FakeQuestionRepository()
        self._checkpoints = _FakeCheckpointRepository()

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
        if self._fail_on_commit:
            raise RuntimeError("commit failed")
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

    def test_rolls_back_and_reraises_when_commit_itself_fails(self) -> None:
        uow = _FakeUnitOfWork(fail_on_commit=True)

        with pytest.raises(RuntimeError, match="commit failed"):
            with uow:
                pass  # ブロック自体は例外を投げない。commit()の実行時に初めて失敗する。

        assert uow.committed is False
        assert uow.rolled_back is True
