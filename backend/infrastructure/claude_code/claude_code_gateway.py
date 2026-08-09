from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
from typing import Any

from backend.domain.gateways.claude_code_gateway import (
    ClaudeCodeSession,
    ClaudeMessage,
    IClaudeCodeGateway,
    MessageRole,
)

logger = logging.getLogger(__name__)

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


class ClaudeCodeGateway(IClaudeCodeGateway):
    """`~/.claude/projects/*/*.jsonl` を走査してセッションを読み取るローカル実装。

    tool_use / thinking などのノイズを落とし、user/assistant のテキストだけを拾って
    セッション単位に組み立てる。テキストを持つ発言が1つも無いセッションは捨てる。
    """

    def __init__(self, projects_dir: Path = CLAUDE_PROJECTS_DIR) -> None:
        self._projects_dir = projects_dir

    def read_sessions(self, since: datetime | None = None) -> Iterator[ClaudeCodeSession]:
        if not self._projects_dir.is_dir():
            # glob は存在しないディレクトリでも例外を出さず空を返すため、
            # 設定ミス（パス間違い等）を「セッション0件」と区別できるようログしておく。
            logger.warning("projects_dir が存在しません: %s", self._projects_dir)
            return

        threshold = since.astimezone(UTC) if since is not None else None
        # 1ファイルの破損/読み取り失敗で全体を止めない。該当セッションだけ読み飛ばす。
        for path in sorted(self._projects_dir.glob("*/*.jsonl")):
            try:
                # jsonl は追記のみなので、mtime が閾値以前なら新しい発言は無い＝パース不要。
                if threshold is not None and datetime.fromtimestamp(path.stat().st_mtime, tz=UTC) <= threshold:
                    continue
                session = self._parse_session(path)
            except (OSError, ValueError) as exc:
                logger.warning("セッションの読み取りに失敗したためスキップします: %s (%s)", path, exc)
                continue
            if session is None:
                continue
            if threshold is not None and session.ended_at <= threshold:
                continue
            yield session

    def _parse_session(self, path: Path) -> ClaudeCodeSession | None:
        messages: list[ClaudeMessage] = []
        session_id: str | None = None
        project_path: str | None = None
        git_branch: str | None = None
        title: str | None = None

        for record in self._iter_records(path):
            session_id = record.get("sessionId") or session_id
            project_path = record.get("cwd") or project_path
            git_branch = record.get("gitBranch") or git_branch
            title = record.get("aiTitle") or title

            message = self._to_message(record)
            if message is not None:
                messages.append(message)

        if not messages:
            return None

        timestamps = [m.timestamp for m in messages]
        return ClaudeCodeSession(
            session_id=session_id or path.stem,
            project_path=project_path,
            git_branch=git_branch,
            title=title,
            started_at=min(timestamps),
            ended_at=max(timestamps),
            messages=tuple(messages),
        )

    @staticmethod
    def _iter_records(path: Path) -> Iterator[dict[str, Any]]:
        with path.open(encoding="utf-8") as fp:
            for line in fp:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                except json.JSONDecodeError:
                    logger.debug("JSONとして解釈できない行をスキップしました: %s", path)
                    continue
                if isinstance(record, dict):
                    yield record
                else:
                    logger.debug("dictでないレコードをスキップしました: %s", path)

    @classmethod
    def _to_message(cls, record: dict[str, Any]) -> ClaudeMessage | None:
        try:
            role = MessageRole(record.get("type", ""))
        except ValueError:
            return None
        # isSidechain: サブエージェント（Task tool）内部の会話。本人が読んでいない。
        # isMeta: ハーネスが注入する注意書き（system-reminder等）で、本人の発言ではない。
        # isCompactSummary: コンテキスト圧縮時の自動要約。元の発言と内容が重複する。
        if record.get("isSidechain") or record.get("isMeta") or record.get("isCompactSummary"):
            return None

        message = record.get("message")
        timestamp = record.get("timestamp")
        if not isinstance(message, dict) or timestamp is None:
            return None

        text = cls._extract_text(message.get("content"))
        if not text:
            return None

        return ClaudeMessage(
            role=role,
            text=text,
            timestamp=timestamp,
        )

    @staticmethod
    def _extract_text(content: Any) -> str:
        # content は文字列か、ブロック配列（text / thinking / tool_use ...）のどちらか
        if isinstance(content, str):
            return content.strip()
        if not isinstance(content, list):
            return ""

        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts).strip()
