from __future__ import annotations

from pydantic import BaseModel, ConfigDict, StrictStr, field_validator

from backend.domain.value_objects.source import Source


class SourceDocument(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source: Source
    content: StrictStr

    @field_validator("content")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("素材の本文が空です")
        return v
