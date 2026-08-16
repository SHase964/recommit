from __future__ import annotations

from datetime import datetime
import uuid

from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from backend.domain.entities import Question

# ORMモデルは schema.sql と対になる（Alembic等は使わず手書きSQLで管理しているため、
# 列の追加・変更時は両方を手で揃える必要がある）。


class Base(DeclarativeBase):
    pass


class SourceDocumentModel(Base):
    __tablename__ = "source_documents"
    __table_args__ = (UniqueConstraint("source_type", "identifier"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    source_type: Mapped[str] = mapped_column(nullable=False)
    identifier: Mapped[str] = mapped_column(nullable=False)
    title: Mapped[str | None] = mapped_column(nullable=True)
    content: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())


class QuestionModel(Base):
    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint("correct_index between 0 and 3"),
        ForeignKeyConstraint(
            ["source_type", "source_identifier"],
            ["source_documents.source_type", "source_documents.identifier"],
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    prompt: Mapped[str] = mapped_column(nullable=False)
    choices: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    correct_index: Mapped[int] = mapped_column(nullable=False)
    explanation: Mapped[str] = mapped_column(nullable=False)
    category: Mapped[str] = mapped_column(nullable=False)
    source_type: Mapped[str] = mapped_column(nullable=False)
    source_identifier: Mapped[str] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())

    @classmethod
    def from_domain(cls, question: Question) -> QuestionModel:
        return cls(
            prompt=question.prompt,
            choices=[choice.root for choice in question.choices],
            correct_index=question.correct_index.root,
            explanation=question.explanation,
            category=question.category.root,
            source_type=question.source.source_type.value,
            source_identifier=question.source.identifier,
        )


class CheckpointModel(Base):
    __tablename__ = "checkpoints"

    source_type: Mapped[str] = mapped_column(primary_key=True)
    last_processed_at: Mapped[datetime] = mapped_column(nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, server_default=func.now())
