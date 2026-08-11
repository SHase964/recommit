from __future__ import annotations

from abc import ABC, abstractmethod

from backend.domain.value_objects import SourceDocument


class ISourceDocumentRepository(ABC):
    @abstractmethod
    def save(self, document: SourceDocument) -> None:
        """学習素材を永続化する。

        キーは document.source（source_type + identifier）。既に同じキーが存在する場合は
        内容を上書きする（upsert）。進行中のClaude Codeセッションのように、同じ
        identifierのまま内容が増えたSourceDocumentが複数回渡されることがあるため
        （ClaudeCodeLearningService.collect の契約を参照）。
        """
        pass
