from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from backend.domain.value_objects import SourceType
from backend.infrastructure.supabase.checkpoint_repository import SupabaseCheckpointRepository


class TestFindLastProcessedAt:
    def test_returns_none_when_never_saved(self, session: Session) -> None:
        repo = SupabaseCheckpointRepository(session)

        assert repo.find_last_processed_at(SourceType.CLAUDE_CODE) is None


class TestSave:
    def test_can_read_back_saved_value(self, session: Session) -> None:
        repo = SupabaseCheckpointRepository(session)
        processed_at = datetime(2026, 8, 12, 12, 0, tzinfo=UTC)

        repo.save(SourceType.CLAUDE_CODE, processed_at)
        session.commit()

        assert repo.find_last_processed_at(SourceType.CLAUDE_CODE) == processed_at

    def test_upserts_when_saved_again(self, session: Session) -> None:
        repo = SupabaseCheckpointRepository(session)
        first = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)
        second = datetime(2026, 8, 12, 18, 0, tzinfo=UTC)

        repo.save(SourceType.CLAUDE_CODE, first)
        session.commit()
        repo.save(SourceType.CLAUDE_CODE, second)
        session.commit()

        assert repo.find_last_processed_at(SourceType.CLAUDE_CODE) == second

    def test_keeps_different_source_types_independent(self, session: Session) -> None:
        repo = SupabaseCheckpointRepository(session)
        claude_code_at = datetime(2026, 8, 12, 9, 0, tzinfo=UTC)

        repo.save(SourceType.CLAUDE_CODE, claude_code_at)
        session.commit()

        assert repo.find_last_processed_at(SourceType.OTHER) is None
        assert repo.find_last_processed_at(SourceType.CLAUDE_CODE) == claude_code_at
