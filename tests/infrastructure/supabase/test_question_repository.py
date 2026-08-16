from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.domain.entities import Question
from backend.domain.value_objects import Category, Choice, Choices, CorrectIndex, Source, SourceDocument, SourceType
from backend.infrastructure.supabase.question_repository import SupabaseQuestionRepository
from backend.infrastructure.supabase.source_document_repository import SupabaseSourceDocumentRepository


def _document(identifier: str = "sess-1") -> SourceDocument:
    return SourceDocument(source=Source(source_type=SourceType.CLAUDE_CODE, identifier=identifier), content="c")


def _question(*, identifier: str = "sess-1", prompt: str = "prompt") -> Question:
    return Question(
        prompt=prompt,
        choices=Choices(root=tuple(Choice(root=f"choice{i}") for i in range(4))),
        correct_index=CorrectIndex(root=0),
        explanation="explanation",
        category=Category(root="category"),
        source=Source(source_type=SourceType.CLAUDE_CODE, identifier=identifier),
    )


class TestSave:
    def test_inserts_questions(self, session: Session) -> None:
        SupabaseSourceDocumentRepository(session).save(_document())
        session.commit()

        SupabaseQuestionRepository(session).save([_question(prompt="q1"), _question(prompt="q2")])
        session.commit()

        rows = session.execute(text("select prompt from questions order by prompt")).all()
        assert [r.prompt for r in rows] == ["q1", "q2"]

    def test_does_not_replace_existing_questions_on_second_save(self, session: Session) -> None:
        SupabaseSourceDocumentRepository(session).save(_document())
        session.commit()
        repo = SupabaseQuestionRepository(session)

        repo.save([_question(prompt="night1")])
        session.commit()
        repo.save([_question(prompt="night2")])
        session.commit()

        rows = session.execute(text("select prompt from questions order by prompt")).all()
        assert [r.prompt for r in rows] == ["night1", "night2"]

    def test_rejects_question_without_matching_source_document(self, session: Session) -> None:
        SupabaseQuestionRepository(session).save([_question(identifier="no-such-session")])

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()
