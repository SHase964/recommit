from __future__ import annotations

from anthropic import Anthropic
from pydantic import BaseModel, ValidationError

from backend.domain.entities.question import Question
from backend.domain.gateways.question_generator_gateway import IQuestionGeneratorGateway
from backend.domain.value_objects import Category, Choice, Choices, CorrectIndex, Source, SourceDocument

_DEFAULT_MODEL = "claude-opus-4-8"
_DEFAULT_MAX_TOKENS = 16000
_DEFAULT_MAX_CONTENT_LENGTH = 20_000  # コスト対策: 長大なセッションは先頭のみ送る


class _GeneratedQuestion(BaseModel):
    """LLM が返す1問分のJSON（このアダプタ内部のDTO）。ドメインの Question とは別物。"""

    prompt: str
    choices: list[str]
    correct_index: int
    explanation: str
    category: str


class _GeneratedQuestionSet(BaseModel):
    questions: list[_GeneratedQuestion]


class ClaudeQuestionGeneratorGateway(IQuestionGeneratorGateway):
    """Anthropic Claude で学習素材から4択問題を生成するアダプタ。

    LLM の出力は内部DTO `_GeneratedQuestion` で受け、ドメインの `Question` に変換する。
    変換時にドメインのバリデーション（選択肢4つ・正解index 0-3 等）を通らない問題は捨てる。
    """

    def __init__(
        self,
        client: Anthropic | None = None,
        *,
        model: str = _DEFAULT_MODEL,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
        use_thinking: bool = True,
        max_content_length: int = _DEFAULT_MAX_CONTENT_LENGTH,
    ) -> None:
        self._client = client or Anthropic()
        self._model = model
        self._max_tokens = max_tokens
        self._use_thinking = use_thinking
        self._max_content_length = max_content_length

    def generate_questions(self, document: SourceDocument, count: int) -> list[Question]:
        response = self._client.messages.parse(
            model=self._model,
            max_tokens=self._max_tokens,
            thinking={"type": "adaptive"} if self._use_thinking else {"type": "disabled"},
            system=self._build_system_prompt(count),
            messages=[{"role": "user", "content": self._build_user_prompt(document)}],
            output_format=_GeneratedQuestionSet,
        )
        generated = response.parsed_output
        if generated is None:
            return []
        return [
            question
            for candidate in generated.questions
            if (question := self._to_question(candidate, document.source)) is not None
        ]

    @staticmethod
    def _build_system_prompt(count: int) -> str:
        return (
            "あなたは学習内容の理解度を測る出題者です。"
            f"与えられた学習素材から、4択問題を最大{count}問生成してください。"
            "各問題は 問題文 / 選択肢4つ / 正解の選択肢番号(0-3) / 解説 / カテゴリ を持ちます。"
            "カテゴリは素材の主題を表す短い日本語（例: LLM, プログラミング基礎, Webアーキテクチャ）。"
            "素材から答えが一意に確定できる問題だけを作り、無理に数を埋めないこと。"
        )

    def _build_user_prompt(self, document: SourceDocument) -> str:
        title = document.source.title or "（無題）"
        content = document.content[: self._max_content_length]
        return f"# 学習素材\nタイトル: {title}\n\n{content}"

    @staticmethod
    def _to_question(candidate: _GeneratedQuestion, source: Source) -> Question | None:
        try:
            return Question(
                prompt=candidate.prompt,
                choices=Choices(root=tuple(Choice(root=text) for text in candidate.choices)),
                correct_index=CorrectIndex(root=candidate.correct_index),
                explanation=candidate.explanation,
                category=Category(root=candidate.category),
                source=source,
            )
        except ValidationError:
            # 選択肢が4つでない・正解indexが範囲外・空文字 等はドメインが弾く → その問題は捨てる
            return None
