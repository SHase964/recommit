# recommit (Recall)

Claude Code の利用履歴から学習素材を作り、復習用の4択問題を自動生成するツール。cron で夜間実行するローカルバッチを想定（Web はまだない）。

## アーキテクチャ

DDD + クリーンアーキテクチャ。レイヤー構成:

- `backend/domain/gateways/` — 外部システムへのポート。`I{System}Gateway`、動詞はメソッド側。実装は `backend/infrastructure/{vendor}/`。
- `backend/domain/repositories/` — 永続化ポート。`I{Aggregate}Repository`（Gateway接尾辞は付けない）。`ISourceDocumentRepository`（upsert、キーは`Source`=source_type+identifier）と`IQuestionRepository`（insertのみ、洗い替えしない）を定義済み。実装は `backend/infrastructure/supabase/`（SQLAlchemy + psycopgでPostgres直結）。
- `backend/domain/services/` — ドメインサービス。生データ→中立な素材への変換、`IUnitOfWork`（トランザクション境界）など。
- `backend/domain/value_objects/` / `entities/` — VO・エンティティ。
- `backend/application/` — ユースケース配線・entrypoint。**まだ空（次のPRで追加予定）**。

命名・配置の詳細な規約はセッション開始時にユーザーへ確認するか、過去の議論を参照すること（B案で確定済み: ポートは能力/システム名で命名、ベンダー名はドメインに漏らさない、gatewayの生の戻り値型はinterfaceと同じファイルに置く 等）。

## 現在の状態（2026-08-12 時点）

PR #2（`feature/qa_llm` ブランチ）で以下が完成・マージ可能:

- `backend/domain/gateways/claude_code_gateway.py` + `backend/infrastructure/claude_code/claude_code_gateway.py` — `~/.claude/projects/*/*.jsonl` を読んで `ClaudeCodeSession` を返す Reader。
- `backend/domain/services/claude_code_learning.py` — セッションをノイズ除去・シークレットマスキングして `SourceDocument`（学習素材）に変換。
- `backend/domain/gateways/question_generator_gateway.py` + `backend/infrastructure/llm/claude_question_generator.py` — `SourceDocument` から Claude で4択 `Question` を生成。

永続化層（ドメインポート + Supabaseインフラ実装、両方完成）:

- `backend/domain/repositories/source_document_repository.py` — `ISourceDocumentRepository.save()`。`Source`（source_type+identifier）をキーにupsert。
- `backend/domain/repositories/question_repository.py` — `IQuestionRepository.save()`。insertのみ、洗い替えしない（復習アプリなので過去の問題も履歴として残す方針）。
- `backend/domain/services/unit_of_work.py` — `IUnitOfWork`。`source_documents`/`questions` の2つのRepositoryを束ね、`with`ブロックの正常終了でcommit・例外でrollback（`__exit__`に実装済み）。**commit自体が失敗した場合も必ずrollbackしてから例外を伝播させる**（実DBで統合テストして見つけた抜けを修正済み）。
- `backend/infrastructure/supabase/schema.sql` — 手書きDDL（`source_documents`/`questions`の2テーブルのみなのでAlembic等は未導入）。`questions`は`(source_type, source_identifier)`の外部キーで`source_documents`を参照する。
- `backend/infrastructure/supabase/models.py` — SQLAlchemy ORMモデル（`from_domain()`のみ、`to_domain()`は読み取りメソッドが無いのでYAGNIで未実装）。schema.sqlと手動で同期させる必要がある点に注意。
- `backend/infrastructure/supabase/source_document_repository.py` / `question_repository.py` / `unit_of_work.py` — 実装クラス。`Session`をコンストラクタで受け取る（Session/Engineの生成はentrypoint側の責務、まだ配線されていない）。upsertは`sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_update(...)`。

設計判断のメモ:

- 永続化技術は **SQLAlchemy + psycopg[binary] でSupabaseのPostgresに直接接続**（`supabase-py`のRESTクライアントは複数テーブルをまたぐ本物のトランザクションができないため不採用）。
- `supabase-py` + RLS（ユーザー起点CRUD向けの一般的なパターン）は、recommitにはまだ不要と判断。理由: 今のところ書き込み経路は夜間バッチ1本のみで、エンドユーザーが直接Supabaseを叩く経路（Webフロントエンド）が存在しないため。Web版を作る段階になったら再検討する。
- DIコンテナは導入しない。`injector`のようなライブラリは、バッチ1本のentrypointの規模には過剰。`backend/application/`のentrypointで手動でオブジェクトを組み立てる（軽量な自前wiring）方針。
- `backend/infrastructure/supabase/`の統合テスト（`tests/infrastructure/supabase/`）は実Postgresが必要。ローカルはdocker（`docker run -d --name recommit-db -p 55432:5432 -e POSTGRES_PASSWORD=recommit -e POSTGRES_DB=recommit postgres:16`）、CIは`.github/workflows/ci.yml`の`services.postgres`。接続先は`TEST_DATABASE_URL`環境変数（未設定時はローカルdocker想定のデフォルト値）。DBに接続できない場合はテストがskipされる。
- まだ本物のSupabaseプロジェクトには繋いでいない（接続情報が無いため）。ローカルdockerでの動作確認のみ。
- `schema.sql`は`backend/infrastructure/supabase/`の中に置いている（Postgres固有の実装詳細でありドメインではないため、`models.py`と同じ理由でここが適切）。neo-smart-chatはAlembicのマイグレーション（`versions/`配下に変更履歴を積み上げる形式）を`infrastructures/`の外の兄弟フォルダ（`api/migrations/`）に置いているが、それは「時系列の変更履歴」という別種の成果物だから。recommitは今のところ履歴を持たない単一の`schema.sql`（`CREATE TABLE IF NOT EXISTS`で「あるべき最終形」を書くだけ）なので`infrastructure/supabase/`内で問題ない。将来Alembicを導入するとき（既存テーブルへのALTERが必要になった時など）は、`backend/migrations/`のような兄弟フォルダへの切り出しを検討する。その際も`models.py`はそのまま流用できる（Alembicの自動生成はSQLAlchemyモデルとDBの差分を見て変更ファイルを作る仕組みのため）。

テストは `tests/` 配下に78件（`make test` で実行）。`make lint` で ruff/mypy を backend + tests に対して実行。

## 次にやること（優先度順）

1. **バッチのオーケストレーション / entrypoint**（`backend/application/` に配線）。
   - Reader → `ClaudeCodeLearningService` → `ClaudeQuestionGeneratorGateway` → `IUnitOfWork` を繋ぐ。
   - 接続文字列（Supabaseの本番 or ローカルdocker）から`Session`/`Engine`を作る部分がまだ無い。環境変数から読む想定。
   - 実際のSupabaseプロジェクトを作り、`backend/infrastructure/supabase/schema.sql`を適用する必要がある（現状ローカルdockerでのみ動作確認済み）。
   - 差分読み取り用の `last_processed_at`（`since` に渡す値）をどこかに永続化する必要がある。
   - 過去に `main.py` を削除した経緯があるので、entrypoint は再構築が必要。
2. **PR #2 のレビューで著者自身が明示的に先送りしたもの**（優先度低）:
   - `ClaudeQuestionGeneratorGateway` のモデルID/`max_tokens` を環境変数等の外部設定から注入できるようにする。
   - `ClaudeCodeLearningService.build_source_document` の `min_content_length` 判定が、本文だけでなくロール接頭辞（`[user] `/`[assistant] `）込みの文字数になっている件（実害が出たら対応）。

新しい会話でこのリポジトリの続きに着手するときは、まずこのファイルの「次にやること」を確認してから着手すること。完了した項目はこのファイルから消すか、状態を更新すること。
