from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
import re

from backend.domain.gateways.claude_code_gateway import ClaudeCodeSession, IClaudeCodeGateway
from backend.domain.value_objects import Source, SourceDocument, SourceType

# ハーネスが自動注入する非・学習テキスト（IDE状態・システム通知・スラッシュコマンド等）。
# これらは「ユーザが学んだ内容」ではないので学習素材から除外する。
_NOISE_TAG_PATTERN = re.compile(
    r"<(ide_opened_file|ide_selection|system-reminder|command-name|command-message"
    r"|command-args|local-command-stdout)>.*?</\1>",
    re.DOTALL,
)


class ClaudeCodeLearningService:
    def __init__(self, gateway: IClaudeCodeGateway, min_content_length: int = 200) -> None:
        self._gateway = gateway
        self._min_content_length = min_content_length

    def collect(self, since: datetime | None = None) -> Iterator[SourceDocument]:
        """gateway からセッションを読み取り、学習素材として意味を成すものだけを返す。"""
        for session in self._gateway.read_sessions(since):
            document = self.build_source_document(session)
            if document is not None:
                yield document

    def build_source_document(self, session: ClaudeCodeSession) -> SourceDocument | None:
        """1セッションを学習素材に変換する。薄すぎて学びにならない場合は None。"""
        blocks = [
            f"[{message.role.value}] {stripped}"
            for message in session.messages
            if (stripped := _NOISE_TAG_PATTERN.sub("", message.text).strip()) and stripped
        ]

        content = "\n\n".join(blocks).strip()
        if len(content) < self._min_content_length:
            return None

        return SourceDocument(
            source=Source(
                source_type=SourceType.CLAUDE_CODE,
                identifier=session.session_id,
                title=session.title,
            ),
            content=content,
        )

    @staticmethod
    def _strip_noise(text: str) -> str:
        return _NOISE_TAG_PATTERN.sub("", text).strip()
