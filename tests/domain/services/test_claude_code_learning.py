from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
import logging

import pytest

from backend.domain.gateways.claude_code_gateway import (
    ClaudeCodeSession,
    ClaudeMessage,
    IClaudeCodeGateway,
    MessageRole,
)
from backend.domain.services.claude_code_learning import ClaudeCodeLearningService
from backend.domain.value_objects import SourceType

_TS = datetime(2026, 8, 6, 12, 0, tzinfo=UTC)


def _message(role: MessageRole, text: str) -> ClaudeMessage:
    return ClaudeMessage(role=role, text=text, timestamp=_TS)


def _session(
    messages: tuple[ClaudeMessage, ...], *, session_id: str = "sess-1", title: str | None = None
) -> ClaudeCodeSession:
    return ClaudeCodeSession(
        session_id=session_id,
        started_at=_TS,
        ended_at=_TS,
        title=title,
        messages=messages,
    )


class _FakeGateway(IClaudeCodeGateway):
    def __init__(self, sessions: list[ClaudeCodeSession]) -> None:
        self._sessions = sessions

    def read_sessions(self, since: datetime | None = None) -> Iterator[ClaudeCodeSession]:
        yield from self._sessions


class TestInit:
    @pytest.mark.parametrize("bad_length", [0, -1])
    def test_rejects_non_positive_min_content_length(self, bad_length: int) -> None:
        with pytest.raises(ValueError, match="正の整数"):
            ClaudeCodeLearningService(gateway=_FakeGateway([]), min_content_length=bad_length)


class TestBuildSourceDocument:
    def test_returns_none_when_below_min_content_length(self) -> None:
        service = ClaudeCodeLearningService(gateway=_FakeGateway([]), min_content_length=200)
        session = _session((_message(MessageRole.USER, "短い"),))

        assert service.build_source_document(session) is None

    def test_builds_document_when_above_threshold(self) -> None:
        service = ClaudeCodeLearningService(gateway=_FakeGateway([]), min_content_length=10)
        session = _session(
            (_message(MessageRole.USER, "質問です" * 5), _message(MessageRole.ASSISTANT, "回答です" * 5)),
            session_id="sess-42",
            title="タイトル",
        )

        document = service.build_source_document(session)

        assert document is not None
        assert document.source.source_type == SourceType.CLAUDE_CODE
        assert document.source.identifier == "sess-42"
        assert document.source.title == "タイトル"
        assert "[user]" in document.content
        assert "[assistant]" in document.content

    def test_strips_noise_tags_including_attributed_ones(self) -> None:
        service = ClaudeCodeLearningService(gateway=_FakeGateway([]), min_content_length=1)
        text = (
            '<ide_opened_file path="foo.py">The user opened foo.py</ide_opened_file>'
            "本文はここだけ残る"
            "<system-reminder>注意書き</system-reminder>"
        )
        session = _session((_message(MessageRole.USER, text),))

        document = service.build_source_document(session)

        assert document is not None
        assert "本文はここだけ残る" in document.content
        assert "ide_opened_file" not in document.content
        assert "system-reminder" not in document.content

    @pytest.mark.parametrize(
        ("label", "secret"),
        [
            ("anthropic_api_key", "sk-ant-api03-" + "a" * 30),
            ("github_token", "ghp_" + "a" * 36),
            ("aws_access_key_id", "AKIA" + "ABCD1234EFGH5678"),
            (
                "pem_private_key",
                "-----BEGIN RSA PRIVATE KEY-----\nMIIBOgIBAAJBAK...\n-----END RSA PRIVATE KEY-----",
            ),
        ],
    )
    def test_redacts_secrets_in_message_text(self, label: str, secret: str) -> None:
        service = ClaudeCodeLearningService(gateway=_FakeGateway([]), min_content_length=1)
        session = _session((_message(MessageRole.USER, f"key: {secret} を使ってください"),))

        document = service.build_source_document(session)

        assert document is not None, label
        assert secret not in document.content, label
        assert "[REDACTED]" in document.content, label

    def test_messages_with_only_noise_are_excluded_from_content(self) -> None:
        service = ClaudeCodeLearningService(gateway=_FakeGateway([]), min_content_length=1)
        session = _session(
            (
                _message(MessageRole.USER, "<system-reminder>注意書きのみ</system-reminder>"),
                _message(MessageRole.ASSISTANT, "本物の発言"),
            )
        )

        document = service.build_source_document(session)

        assert document is not None
        assert document.content == "[assistant] 本物の発言"


class TestCollect:
    def test_yields_documents_only_for_sessions_that_meet_threshold(self) -> None:
        thin_session = _session((_message(MessageRole.USER, "短い"),), session_id="thin")
        thick_session = _session((_message(MessageRole.USER, "十分に長い本文です" * 5),), session_id="thick")
        service = ClaudeCodeLearningService(gateway=_FakeGateway([thin_session, thick_session]), min_content_length=10)

        documents = list(service.collect())

        assert [d.source.identifier for d in documents] == ["thick"]

    def test_logs_completion_count(self, caplog: pytest.LogCaptureFixture) -> None:
        session = _session((_message(MessageRole.USER, "十分に長い本文です" * 5),))
        service = ClaudeCodeLearningService(gateway=_FakeGateway([session]), min_content_length=10)

        with caplog.at_level(logging.INFO):
            list(service.collect())

        assert "収集完了" in caplog.text
        assert "1件" in caplog.text
