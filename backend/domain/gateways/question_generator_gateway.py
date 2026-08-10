from __future__ import annotations

from abc import ABC, abstractmethod

from backend.domain.entities.question import Question
from backend.domain.value_objects import SourceDocument


class IQuestionGeneratorGateway(ABC):
    @abstractmethod
    def generate_questions(self, document: SourceDocument, count: int) -> list[Question]:
        """学習素材から4択問題を生成する。

        count は生成したい問題数の希望値。素材が薄い場合や、生成結果がドメインの検証を
        通らなかった場合は、返る件数が count を下回ることがある（0件もありうる）。
        """
        pass
