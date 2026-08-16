from __future__ import annotations

from collections.abc import Iterator
import os
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session

# ローカル開発では docker (recommit-db) を、CIでは ci.yml の postgres service を指す。
_DEFAULT_DATABASE_URL = "postgresql+psycopg://postgres:recommit@localhost:55432/recommit"
_SCHEMA_SQL_PATH = Path(__file__).resolve().parents[3] / "backend/infrastructure/supabase/schema.sql"
# 外部キーの子(questions)から先に消す。checkpointsは他と依存関係が無い。
_TABLES_IN_DELETE_ORDER = ("questions", "source_documents", "checkpoints")


@pytest.fixture(scope="session")
def _engine() -> Iterator[Engine]:
    url = os.environ.get("TEST_DATABASE_URL", _DEFAULT_DATABASE_URL)
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"テスト用Postgresに接続できません（{url}）: {exc}")

    with engine.begin() as conn:
        for statement in _SCHEMA_SQL_PATH.read_text().split(";"):
            if statement.strip():
                conn.execute(text(statement))

    yield engine
    engine.dispose()


@pytest.fixture
def session(_engine: Engine) -> Iterator[Session]:
    with Session(_engine) as db_session:
        for table in _TABLES_IN_DELETE_ORDER:
            db_session.execute(text(f"truncate table {table} cascade"))
        db_session.commit()

        yield db_session

        db_session.rollback()
