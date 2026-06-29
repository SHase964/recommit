from __future__ import annotations

from collections.abc import Iterator
from typing import SupportsIndex

from pydantic import ConfigDict, RootModel, StrictStr, field_validator

NUM_CHOICES = 4


class Choice(RootModel[StrictStr]):
    model_config = ConfigDict(frozen=True)

    root: StrictStr

    @field_validator("root")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("選択肢のテキストが空です")
        return v


class Choices(RootModel[tuple[Choice, ...]]):
    model_config = ConfigDict(frozen=True)

    root: tuple[Choice, ...]

    @field_validator("root")
    @classmethod
    def _has_required_count(cls, v: tuple[Choice, ...]) -> tuple[Choice, ...]:
        if len(v) != NUM_CHOICES:
            raise ValueError(f"選択肢は{NUM_CHOICES}つ必要です（実際: {len(v)}）")
        return v

    def __len__(self) -> int:
        return len(self.root)

    def __getitem__(self, index: SupportsIndex) -> Choice:
        return self.root[index]

    def __iter__(self) -> Iterator[Choice]:  # type: ignore[override]
        return iter(self.root)
