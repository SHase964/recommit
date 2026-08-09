from __future__ import annotations

from datetime import UTC, datetime

from pydantic import ValidationError
import pytest

from backend.domain.gateways.claude_code_gateway import ClaudeCodeSession, ClaudeMessage, MessageRole

_AWARE_TS = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
_NAIVE_TS = datetime(2026, 8, 6, 12, 0)


def _message(**overrides: object) -> ClaudeMessage:
    fields: dict[str, object] = {"role": MessageRole.USER, "text": "hello", "timestamp": _AWARE_TS}
    fields.update(overrides)
    return ClaudeMessage(**fields)  # type: ignore[arg-type]


def _session(**overrides: object) -> ClaudeCodeSession:
    fields: dict[str, object] = {
        "session_id": "abc",
        "started_at": _AWARE_TS,
        "ended_at": _AWARE_TS,
        "messages": (),
    }
    fields.update(overrides)
    return ClaudeCodeSession(**fields)  # type: ignore[arg-type]


class TestClaudeMessage:
    def test_rejects_blank_text(self) -> None:
        with pytest.raises(ValidationError):
            _message(text="   ")

    def test_strips_surrounding_whitespace(self) -> None:
        message = _message(text="  hello  ")
        assert message.text == "hello"

    def test_rejects_naive_timestamp(self) -> None:
        with pytest.raises(ValidationError):
            _message(timestamp=_NAIVE_TS)

    def test_frozen(self) -> None:
        message = _message()
        with pytest.raises(ValidationError):
            message.text = "changed"


class TestClaudeCodeSession:
    def test_rejects_blank_session_id(self) -> None:
        with pytest.raises(ValidationError):
            _session(session_id="   ")

    def test_project_path_defaults_to_none_when_omitted(self) -> None:
        session = _session()
        assert session.project_path is None

    def test_rejects_naive_started_at(self) -> None:
        with pytest.raises(ValidationError):
            _session(started_at=_NAIVE_TS)

    def test_rejects_naive_ended_at(self) -> None:
        with pytest.raises(ValidationError):
            _session(ended_at=_NAIVE_TS)
