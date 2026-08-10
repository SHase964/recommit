from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
import os
from pathlib import Path
from typing import Any

import pytest

from backend.domain.gateways.claude_code_gateway import MessageRole
from backend.infrastructure.claude_code.claude_code_gateway import ClaudeCodeGateway


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def _record(
    *,
    type_: str = "user",
    text: str = "hello",
    timestamp: str | None = "2026-08-06T12:00:00.000Z",
    session_id: str = "sess-1",
    cwd: str | None = "/home/user/project",
    git_branch: str | None = "main",
    is_sidechain: bool = False,
    is_meta: bool = False,
    is_compact_summary: bool = False,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "type": type_,
        "sessionId": session_id,
        "cwd": cwd,
        "gitBranch": git_branch,
        "message": {"content": text},
        "isSidechain": is_sidechain,
        "isMeta": is_meta,
        "isCompactSummary": is_compact_summary,
    }
    if timestamp is not None:
        record["timestamp"] = timestamp
    return record


class TestReadSessions:
    def test_missing_projects_dir_returns_empty_and_logs_warning(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        gateway = ClaudeCodeGateway(projects_dir=tmp_path / "does-not-exist")

        with caplog.at_level(logging.WARNING):
            sessions = list(gateway.read_sessions())

        assert sessions == []
        assert "存在しません" in caplog.text

    def test_reads_a_simple_session(self, tmp_path: Path) -> None:
        _write_jsonl(
            tmp_path / "proj" / "sess-1.jsonl",
            [
                _record(type_="user", text="質問です"),
                _record(type_="assistant", text="回答です", timestamp="2026-08-06T12:05:00.000Z"),
            ],
        )
        gateway = ClaudeCodeGateway(projects_dir=tmp_path)

        sessions = list(gateway.read_sessions())

        assert len(sessions) == 1
        session = sessions[0]
        assert session.session_id == "sess-1"
        assert session.project_path == "/home/user/project"
        assert session.git_branch == "main"
        assert len(session.messages) == 2
        assert session.started_at == datetime(2026, 8, 6, 12, 0, tzinfo=UTC)
        assert session.ended_at == datetime(2026, 8, 6, 12, 5, tzinfo=UTC)

    def test_session_with_only_meta_messages_is_dropped(self, tmp_path: Path) -> None:
        _write_jsonl(tmp_path / "proj" / "sess-1.jsonl", [_record(is_meta=True)])
        gateway = ClaudeCodeGateway(projects_dir=tmp_path)

        assert list(gateway.read_sessions()) == []

    def test_session_with_only_empty_text_messages_is_dropped(self, tmp_path: Path) -> None:
        _write_jsonl(tmp_path / "proj" / "sess-1.jsonl", [_record(text="")])
        gateway = ClaudeCodeGateway(projects_dir=tmp_path)

        assert list(gateway.read_sessions()) == []

    def test_since_filters_out_sessions_that_ended_before_threshold(self, tmp_path: Path) -> None:
        _write_jsonl(
            tmp_path / "proj" / "old.jsonl",
            [_record(session_id="old", timestamp="2026-08-01T00:00:00.000Z")],
        )
        _write_jsonl(
            tmp_path / "proj" / "new.jsonl",
            [_record(session_id="new", timestamp="2026-08-10T00:00:00.000Z")],
        )
        gateway = ClaudeCodeGateway(projects_dir=tmp_path)

        sessions = list(gateway.read_sessions(since=datetime(2026, 8, 5, tzinfo=UTC)))

        assert [s.session_id for s in sessions] == ["new"]

    def test_since_accepts_naive_datetime_without_raising(self, tmp_path: Path) -> None:
        _write_jsonl(
            tmp_path / "proj" / "sess.jsonl",
            [_record(timestamp="2026-08-10T00:00:00.000Z")],
        )
        gateway = ClaudeCodeGateway(projects_dir=tmp_path)

        # naive datetime を渡しても TypeError にならず、ローカル時刻として扱われること。
        sessions = list(gateway.read_sessions(since=datetime(2020, 1, 1)))

        assert len(sessions) == 1

    def test_mtime_prefilter_skips_stale_files_without_parsing(self, tmp_path: Path) -> None:
        path = tmp_path / "proj" / "sess.jsonl"
        # ファイルの中身は since より新しいが、mtime だけを since より古く設定する。
        # mtime 単独で足切りされる（中身のtimestampなら通過するはず）ことを確認する。
        _write_jsonl(path, [_record(timestamp="2026-08-10T00:00:00.000Z")])
        old_time = datetime(2020, 1, 1, tzinfo=UTC).timestamp()
        os.utime(path, (old_time, old_time))
        gateway = ClaudeCodeGateway(projects_dir=tmp_path)

        sessions = list(gateway.read_sessions(since=datetime(2026, 8, 5, tzinfo=UTC)))

        assert sessions == []

    def test_skips_session_with_invalid_data_and_continues(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        _write_jsonl(
            tmp_path / "proj" / "broken.jsonl",
            [_record(session_id="broken", timestamp="not-a-valid-timestamp")],
        )
        _write_jsonl(tmp_path / "proj" / "ok.jsonl", [_record(session_id="ok")])
        gateway = ClaudeCodeGateway(projects_dir=tmp_path)

        with caplog.at_level(logging.WARNING):
            sessions = list(gateway.read_sessions())

        assert [s.session_id for s in sessions] == ["ok"]
        assert "スキップ" in caplog.text


class TestParseSession:
    def test_session_id_falls_back_to_filename_stem(self, tmp_path: Path) -> None:
        path = tmp_path / "proj" / "my-session-id.jsonl"
        _write_jsonl(path, [_record(session_id="")])
        gateway = ClaudeCodeGateway(projects_dir=tmp_path)

        session = gateway._parse_session(path)

        assert session is not None
        assert session.session_id == "my-session-id"

    def test_project_path_uses_last_non_null_cwd(self, tmp_path: Path) -> None:
        path = tmp_path / "proj" / "sess.jsonl"
        _write_jsonl(
            path,
            [
                _record(cwd="/first", timestamp="2026-08-06T12:00:00.000Z"),
                _record(cwd="/second", timestamp="2026-08-06T12:01:00.000Z"),
            ],
        )
        gateway = ClaudeCodeGateway(projects_dir=tmp_path)

        session = gateway._parse_session(path)

        assert session is not None
        assert session.project_path == "/second"

    def test_project_path_is_none_when_no_record_has_cwd(self, tmp_path: Path) -> None:
        path = tmp_path / "proj" / "sess.jsonl"
        _write_jsonl(path, [_record(cwd=None)])
        gateway = ClaudeCodeGateway(projects_dir=tmp_path)

        session = gateway._parse_session(path)

        assert session is not None
        assert session.project_path is None

    def test_returns_none_when_only_meta_messages(self, tmp_path: Path) -> None:
        path = tmp_path / "proj" / "sess.jsonl"
        _write_jsonl(path, [_record(is_meta=True)])
        gateway = ClaudeCodeGateway(projects_dir=tmp_path)

        assert gateway._parse_session(path) is None

    def test_returns_none_when_message_text_is_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "proj" / "sess.jsonl"
        _write_jsonl(path, [_record(text="")])
        gateway = ClaudeCodeGateway(projects_dir=tmp_path)

        assert gateway._parse_session(path) is None


class TestIterRecords:
    def test_skips_blank_lines_invalid_json_and_non_dict_records(self, tmp_path: Path) -> None:
        path = tmp_path / "raw.jsonl"
        path.write_text(
            "\n".join(
                [
                    "",
                    "   ",
                    "{not valid json",
                    json.dumps([1, 2, 3]),
                    json.dumps({"type": "user"}),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        records = list(ClaudeCodeGateway._iter_records(path))

        assert records == [{"type": "user"}]


class TestToMessage:
    def test_returns_none_for_unknown_type(self) -> None:
        assert ClaudeCodeGateway._to_message(_record(type_="system")) is None

    @pytest.mark.parametrize("flag", ["isSidechain", "isMeta", "isCompactSummary"])
    def test_returns_none_when_noise_flag_set(self, flag: str) -> None:
        record = _record()
        record[flag] = True
        assert ClaudeCodeGateway._to_message(record) is None

    def test_returns_none_when_message_is_not_a_dict(self) -> None:
        record = _record()
        record["message"] = "not a dict"
        assert ClaudeCodeGateway._to_message(record) is None

    def test_returns_none_when_timestamp_missing(self) -> None:
        assert ClaudeCodeGateway._to_message(_record(timestamp=None)) is None

    def test_returns_none_when_extracted_text_is_empty(self) -> None:
        assert ClaudeCodeGateway._to_message(_record(text="")) is None

    def test_builds_message_for_valid_record(self) -> None:
        message = ClaudeCodeGateway._to_message(_record(type_="assistant", text="hi"))

        assert message is not None
        assert message.role == MessageRole.ASSISTANT
        assert message.text == "hi"


class TestExtractText:
    def test_plain_string(self) -> None:
        assert ClaudeCodeGateway._extract_text("  hi  ") == "hi"

    def test_block_list_keeps_only_text_blocks(self) -> None:
        content = [
            {"type": "text", "text": "first"},
            {"type": "tool_use", "input": {}},
            {"type": "text", "text": "second"},
        ]
        assert ClaudeCodeGateway._extract_text(content) == "first\nsecond"

    def test_non_str_non_list_returns_empty(self) -> None:
        assert ClaudeCodeGateway._extract_text(None) == ""
        assert ClaudeCodeGateway._extract_text(42) == ""
