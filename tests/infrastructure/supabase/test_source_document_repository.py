from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.domain.value_objects import Source, SourceDocument, SourceType
from backend.infrastructure.supabase.source_document_repository import SupabaseSourceDocumentRepository


def _document(*, identifier: str = "sess-1", content: str = "content", title: str | None = "title") -> SourceDocument:
    return SourceDocument(
        source=Source(source_type=SourceType.CLAUDE_CODE, identifier=identifier, title=title),
        content=content,
    )


class TestSave:
    def test_inserts_new_document(self, session: Session) -> None:
        SupabaseSourceDocumentRepository(session).save(_document())
        session.commit()

        rows = session.execute(text("select source_type, identifier, content from source_documents")).all()

        assert len(rows) == 1
        assert rows[0].source_type == "claude_code"
        assert rows[0].identifier == "sess-1"
        assert rows[0].content == "content"

    def test_upserts_when_same_source_saved_again(self, session: Session) -> None:
        repo = SupabaseSourceDocumentRepository(session)

        repo.save(_document(content="v1"))
        session.commit()
        repo.save(_document(content="v2"))
        session.commit()

        rows = session.execute(text("select content from source_documents")).all()
        assert len(rows) == 1
        assert rows[0].content == "v2"

    def test_does_not_mix_up_different_identifiers(self, session: Session) -> None:
        repo = SupabaseSourceDocumentRepository(session)

        repo.save(_document(identifier="sess-1", content="c1"))
        repo.save(_document(identifier="sess-2", content="c2"))
        session.commit()

        rows = session.execute(text("select identifier, content from source_documents order by identifier")).all()
        assert [(r.identifier, r.content) for r in rows] == [("sess-1", "c1"), ("sess-2", "c2")]
