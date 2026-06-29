from __future__ import annotations

from pydantic import ConfigDict, RootModel, StrictStr, field_validator


class Category(RootModel[StrictStr]):
    model_config = ConfigDict(frozen=True)

    root: StrictStr

    @field_validator("root")
    @classmethod
    def _normalize(cls, v: str) -> str:
        v = " ".join(v.split())  # 連続空白の正規化
        if not v:
            raise ValueError("カテゴリ名が空です")
        return v
