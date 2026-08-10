from __future__ import annotations

from pydantic import ValidationError
import pytest

from backend.domain.value_objects import Source, SourceDocument, SourceType


def _source() -> Source:
    return Source(source_type=SourceType.CLAUDE_CODE, identifier="sess-1")


class TestSourceDocument:
    def test_rejects_blank_content(self) -> None:
        with pytest.raises(ValidationError):
            SourceDocument(source=_source(), content="   ")

    def test_rejects_unknown_fields(self) -> None:
        with pytest.raises(ValidationError):
            SourceDocument(source=_source(), content="ok", extra_field="not allowed")  # type: ignore[call-arg]

    def test_frozen(self) -> None:
        document = SourceDocument(source=_source(), content="ok")
        with pytest.raises(ValidationError):
            document.content = "changed"
