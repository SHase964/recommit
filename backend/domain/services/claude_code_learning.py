from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
import logging
import re

from backend.domain.gateways.claude_code_gateway import ClaudeCodeSession, IClaudeCodeGateway
from backend.domain.value_objects import Source, SourceDocument, SourceType

logger = logging.getLogger(__name__)

# ハーネスが自動注入する非・学習テキスト（IDE状態・システム通知・スラッシュコマンド等）。
_NOISE_TAG_PATTERN = re.compile(
    r"<(ide_opened_file|ide_selection|system-reminder|command-name|command-message"
    r"|command-args|local-command-stdout)(?:\s[^>]*)?>.*?</\1>",
    re.DOTALL,
)

# 頻出な形式のAPIキー・トークン・秘密鍵。
_SECRET_PATTERNS = (
    re.compile(r"sk-ant-[A-Za-z0-9\-_]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.DOTALL),
)
_REDACTED = "[REDACTED]"


def _sanitize(text: str) -> str:
    """ハーネス由来のノイズタグを剥がし、よくある形式のシークレットをマスクする。"""
    text = _NOISE_TAG_PATTERN.sub("", text).strip()
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub(_REDACTED, text)
    return text


class ClaudeCodeLearningService:
    def __init__(self, gateway: IClaudeCodeGateway, min_content_length: int = 200) -> None:
        # 文字数ベースの閾値（日本語/英語混在で情報量が変わるため目安値。
        # 判定精度を上げるならトークン数・発言数の併用を検討する）。
        if min_content_length <= 0:
            raise ValueError("min_content_length は正の整数である必要があります")
        self._gateway = gateway
        self._min_content_length = min_content_length

    def collect(self, since: datetime | None = None) -> Iterator[SourceDocument]:
        """gateway からセッションを読み取り、学習素材として意味を成すものだけを返す。

        進行中のセッションは同じ Source.identifier（session_id）のまま、内容が増えた
        SourceDocument として複数回返ることがある（冪等ではない）。呼び出し側は
        identifier をキーに upsert すること。
        """
        count = 0
        for session in self._gateway.read_sessions(since):
            document = self.build_source_document(session)
            if document is not None:
                count += 1
                yield document
        # gateway 側の想定外の例外はここまで伝播してくる（ジェネレータなので途中で
        # 打ち切られる）。このログが出ていれば最後まで完走した証拠になる。
        logger.info("収集完了: %d件のSourceDocumentを生成しました", count)

    def build_source_document(self, session: ClaudeCodeSession) -> SourceDocument | None:
        """1セッションを学習素材に変換する"""
        blocks = [
            f"[{message.role.value}] {sanitized}"
            for message in session.messages
            if (sanitized := _sanitize(message.text))
        ]

        content = "\n\n".join(blocks).strip()
        if len(content) < self._min_content_length:  # TODO: 内容が薄い場合の対処法だが、最適かは要検討
            return None

        return SourceDocument(
            source=Source(
                source_type=SourceType.CLAUDE_CODE,
                identifier=session.session_id,
                title=session.title,
            ),
            content=content,
        )
