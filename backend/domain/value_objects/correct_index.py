from __future__ import annotations

from typing import Annotated

from pydantic import ConfigDict, Field, RootModel, StrictInt

from backend.domain.value_objects.choice import NUM_CHOICES


class CorrectIndex(RootModel[Annotated[StrictInt, Field(ge=0, le=NUM_CHOICES - 1)]]):
    model_config = ConfigDict(frozen=True)

    def __index__(self) -> int:
        # choices[correct_index] のように、そのまま添字として使えるようにする
        return self.root
