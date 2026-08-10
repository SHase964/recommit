from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from datetime import datetime
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, StrictStr, field_validator


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ClaudeMessage(BaseModel):
    """セッション内の1発言。tool_use / thinking 等のノイズを除いたテキストのみを持つ。"""

    model_config = ConfigDict(frozen=True)

    role: MessageRole
    text: StrictStr
    timestamp: AwareDatetime

    @field_validator("text")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("メッセージ本文が空です")
        return v


class ClaudeCodeSession(BaseModel):
    """`~/.claude` の1セッション分の生データ（read-model）。

    Claude Code 固有の形であり、ドメインの一級市民ではない。加工して意味づけした
    素材（SourceDocument）はドメインサービスが別途生成する。
    """

    model_config = ConfigDict(frozen=True)

    session_id: StrictStr
    # 元の作業ディレクトリ（cwd）。レコードに cwd が1件も無ければ None（不明を騙らない）。
    project_path: StrictStr | None = None
    git_branch: StrictStr | None = None
    title: StrictStr | None = None  # aiTitle（自動採番されたセッションタイトル）
    # テキストを持つ発言のみの min/max。tool 操作だけで終わったセッションでも、
    # 学習素材として意味を持つ最終時刻（＝差分読み取りの基準にすべき時刻）はこちら。
    started_at: AwareDatetime
    ended_at: AwareDatetime
    messages: tuple[ClaudeMessage, ...]

    @field_validator("session_id")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("セッションIDが空です")
        return v


class IClaudeCodeGateway(ABC):
    @abstractmethod
    def read_sessions(self, since: datetime | None = None) -> Iterator[ClaudeCodeSession]:
        """`~/.claude` のセッション履歴を読み取り、セッション単位で返す。

        since を指定した場合は、それより後に終了したセッション（ended_at > since）のみを
        対象とする（差分読み取り）。None のときは全件を対象とする。
        since が naive な datetime の場合は、システムのローカル時刻として扱う
        （datetime.now() をそのまま渡せる）。

        jsonl には「セッション終了」を示す明示的なマーカーが無いため、進行中のセッションは
        同じ session_id のまま、内容が増えた状態で複数回の呼び出しにまたがって再度返ることが
        ある（冪等ではない）。呼び出し側は session_id をキーに upsert すること。
        """
        pass
