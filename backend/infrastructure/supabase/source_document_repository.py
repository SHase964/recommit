from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.domain.repositories.source_document_repository import ISourceDocumentRepository
from backend.domain.value_objects import SourceDocument
from backend.infrastructure.supabase.models import SourceDocumentModel


class SupabaseSourceDocumentRepository(ISourceDocumentRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, document: SourceDocument) -> None:
        stmt = insert(SourceDocumentModel).values(
            source_type=document.source.source_type.value,
            identifier=document.source.identifier,
            title=document.source.title,
            content=document.content,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[SourceDocumentModel.source_type, SourceDocumentModel.identifier],
            set_={
                "title": stmt.excluded.title,
                "content": stmt.excluded.content,
                "updated_at": func.now(),
            },
        )
        self._session.execute(stmt)
