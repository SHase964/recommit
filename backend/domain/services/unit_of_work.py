from __future__ import annotations

from abc import abstractmethod
from contextlib import AbstractContextManager
from types import TracebackType

from backend.domain.repositories.question_repository import IQuestionRepository
from backend.domain.repositories.source_document_repository import ISourceDocumentRepository


class IUnitOfWork(AbstractContextManager["IUnitOfWork"]):
    """SourceDocument保存とQuestion保存を1つのトランザクションで確定させる境界。

    with ブロックを正常に抜けたときは commit、例外が発生したときは rollback を
    __exit__ で自動的に行う（呼び出し側は commit/rollback を明示しない）。
    片方だけ成功して片方が失敗する中途半端な状態（例: SourceDocumentは保存できたが
    Questionの保存に失敗し、差分読み取りの基準時刻だけが進んでしまい、そのセッション分の
    Questionが永久に生成されなくなる）を防ぐのが目的。
    """

    @property
    @abstractmethod
    def source_documents(self) -> ISourceDocumentRepository:
        raise NotImplementedError

    @property
    @abstractmethod
    def questions(self) -> IQuestionRepository:
        raise NotImplementedError

    @abstractmethod
    def commit(self) -> None: ...

    @abstractmethod
    def rollback(self) -> None: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if exc_type is None:
            try:
                self.commit()
            except BaseException:
                # commit自体が失敗した場合（例: 外部キー制約違反はflush/commit時に判明する）も、
                # 必ずrollbackしてから伝播させる。しないとセッションが中途半端な状態のまま残る。
                self.rollback()
                raise
        else:
            self.rollback()
