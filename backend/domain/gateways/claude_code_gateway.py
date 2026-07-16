from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, StrictStr, field_validator


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class ClaudeMessage(BaseModel):
    """セッション内の1発言。tool_use / thinking 等のノイズを除いたテキストのみを持つ。"""

    model_config = ConfigDict(frozen=True)

    role: MessageRole
    text: StrictStr
    timestamp: datetime

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
    project_path: StrictStr  # 元の作業ディレクトリ（cwd）
    git_branch: StrictStr | None = None
    title: StrictStr | None = None  # aiTitle（自動採番されたセッションタイトル）
    started_at: datetime
    ended_at: datetime
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
    def read_sessions(self, since: datetime | None = None) -> Iterable[ClaudeCodeSession]:
        """`~/.claude` のセッション履歴を読み取り、セッション単位で返す。

        since を指定した場合は、それより後に終了したセッション（ended_at > since）のみを
        対象とする（差分読み取り）。None のときは全件を対象とする。
        """
        pass
