from __future__ import annotations

from pydantic import BaseModel, ConfigDict, StrictStr, field_validator

from .source import Source


class SourceDocument(BaseModel):
    """QA生成に渡す「学習素材」1件。ソース情報と、加工済みの本文テキストを持つ。

    参照実装の `ScrapedContent`（domain/value_objects）に当たる、ドメインサービスの出力VO。
    """

    model_config = ConfigDict(frozen=True)

    source: Source
    content: StrictStr

    @field_validator("content")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("素材の本文が空です")
        return v
