from __future__ import annotations

from abc import ABC, abstractmethod

from backend.domain.entities import Question


class IQuestionRepository(ABC):
    @abstractmethod
    def save(self, questions: list[Question]) -> None:
        """問題を永続化する（追加保存）。

        upsertはしない。同じSourceDocumentから複数回（例えば夜間バッチが複数日にまたがって
        セッションを再処理した際に）Questionが生成されても、過去に保存した問題は復習対象の
        過去問として残し続けたいため、常に新規追加として保存する。
        """
        pass
