from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from backend.domain.repositories.checkpoint_repository import ICheckpointRepository
from backend.domain.value_objects import SourceType
from backend.infrastructure.supabase.models import CheckpointModel


class SupabaseCheckpointRepository(ICheckpointRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def find_last_processed_at(self, source_type: SourceType) -> datetime | None:
        stmt = select(CheckpointModel.last_processed_at).where(CheckpointModel.source_type == source_type.value)
        return self._session.execute(stmt).scalar_one_or_none()

    def save(self, source_type: SourceType, processed_at: datetime) -> None:
        stmt = insert(CheckpointModel).values(source_type=source_type.value, last_processed_at=processed_at)
        stmt = stmt.on_conflict_do_update(
            index_elements=[CheckpointModel.source_type],
            set_={
                "last_processed_at": stmt.excluded.last_processed_at,
                "updated_at": func.now(),
            },
        )
        self._session.execute(stmt)
