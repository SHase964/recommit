from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from backend.domain.value_objects import SourceType


class ICheckpointRepository(ABC):
    @abstractmethod
    def find_last_processed_at(self, source_type: SourceType) -> datetime | None:
        """指定したsource_typeの最終処理時刻を取得する。一度も処理していなければNone。"""
        pass

    @abstractmethod
    def save(self, source_type: SourceType, processed_at: datetime) -> None:
        """指定したsource_typeの最終処理時刻を保存する（source_typeをキーにupsert）。"""
        pass
