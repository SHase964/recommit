from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.domain.entities import Question
from backend.domain.value_objects import Category, Choice, Choices, CorrectIndex, Source, SourceDocument, SourceType
from backend.infrastructure.supabase.unit_of_work import SupabaseUnitOfWork


def _document(identifier: str = "sess-1") -> SourceDocument:
    return SourceDocument(source=Source(source_type=SourceType.CLAUDE_CODE, identifier=identifier), content="c")


def _question(identifier: str = "sess-1") -> Question:
    return Question(
        prompt="prompt",
        choices=Choices(root=tuple(Choice(root=f"choice{i}") for i in range(4))),
        correct_index=CorrectIndex(root=0),
        explanation="explanation",
        category=Category(root="category"),
        source=Source(source_type=SourceType.CLAUDE_CODE, identifier=identifier),
    )


def _counts(session: Session) -> tuple[int, int]:
    documents = session.execute(text("select count(*) from source_documents")).scalar_one()
    questions = session.execute(text("select count(*) from questions")).scalar_one()
    return documents, questions


class TestCommit:
    def test_commits_source_document_and_questions_together(self, session: Session) -> None:
        with SupabaseUnitOfWork(session) as uow:
            uow.source_documents.save(_document())
            uow.questions.save([_question()])

        assert _counts(session) == (1, 1)


class TestRollback:
    def test_rolls_back_both_when_block_raises(self, session: Session) -> None:
        with pytest.raises(RuntimeError, match="boom"), SupabaseUnitOfWork(session) as uow:
            uow.source_documents.save(_document())
            uow.questions.save([_question()])
            raise RuntimeError("boom")

        assert _counts(session) == (0, 0)

    def test_rolls_back_when_question_violates_foreign_key(self, session: Session) -> None:
        # SourceDocumentを保存せずQuestionだけ保存 → commit時にFK制約違反 → rollbackされる。
        # これが IUnitOfWork を導入した本来の理由（部分成功の防止）を実際に検証している。
        with pytest.raises(Exception, match="foreign key"), SupabaseUnitOfWork(session) as uow:
            uow.questions.save([_question(identifier="no-such-session")])

        assert _counts(session) == (0, 0)
