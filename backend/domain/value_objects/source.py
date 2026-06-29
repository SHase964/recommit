from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, StrictStr, field_validator


class SourceType(StrEnum):
    CLAUDE_CODE = "claude_code"
    OTHER = "other"


class Source(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_type: SourceType
    identifier: StrictStr
    title: StrictStr | None = None

    @field_validator("identifier")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("ソースの識別子が空です")
        return v
