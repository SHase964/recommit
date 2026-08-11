# recommit (Recall)

Claude Code の利用履歴から学習素材を作り、復習用の4択問題を自動生成するツール。cron で夜間実行するローカルバッチを想定（Web はまだない）。

## アーキテクチャ

DDD + クリーンアーキテクチャ。レイヤー構成:

- `backend/domain/gateways/` — 外部システムへのポート。`I{System}Gateway`、動詞はメソッド側。実装は `backend/infrastructure/{vendor}/`。
- `backend/domain/repositories/` — 永続化ポート。`I{Aggregate}Repository`（Gateway接尾辞は付けない）。`ISourceDocumentRepository`（upsert、キーは`Source`=source_type+identifier）と`IQuestionRepository`（insertのみ、洗い替えしない）を定義済み。実装はまだ無い。
- `backend/domain/services/` — ドメインサービス。生データ→中立な素材への変換、`IUnitOfWork`（トランザクション境界）など。
- `backend/domain/value_objects/` / `entities/` — VO・エンティティ。
- `backend/application/` — ユースケース配線・entrypoint。**まだ空（次のPRで追加予定）**。

命名・配置の詳細な規約はセッション開始時にユーザーへ確認するか、過去の議論を参照すること（B案で確定済み: ポートは能力/システム名で命名、ベンダー名はドメインに漏らさない、gatewayの生の戻り値型はinterfaceと同じファイルに置く 等）。

## 現在の状態（2026-08-12 時点）

PR #2（`feature/qa_llm` ブランチ）で以下が完成・マージ可能:

- `backend/domain/gateways/claude_code_gateway.py` + `backend/infrastructure/claude_code/claude_code_gateway.py` — `~/.claude/projects/*/*.jsonl` を読んで `ClaudeCodeSession` を返す Reader。
- `backend/domain/services/claude_code_learning.py` — セッションをノイズ除去・シークレットマスキングして `SourceDocument`（学習素材）に変換。
- `backend/domain/gateways/question_generator_gateway.py` + `backend/infrastructure/llm/claude_question_generator.py` — `SourceDocument` から Claude で4択 `Question` を生成。

永続化層のドメインポート（インターフェースのみ、実装はまだ無い）:

- `backend/domain/repositories/source_document_repository.py` — `ISourceDocumentRepository.save()`。`Source`（source_type+identifier）をキーにupsert。
- `backend/domain/repositories/question_repository.py` — `IQuestionRepository.save()`。insertのみ、洗い替えしない（復習アプリなので過去の問題も履歴として残す方針）。
- `backend/domain/services/unit_of_work.py` — `IUnitOfWork`。`source_documents`/`questions` の2つのRepositoryを束ね、`with`ブロックの正常終了でcommit・例外でrollback（`__exit__`に実装済み、テストも書いてある）。SourceDocument保存とQuestion保存が部分的にしか成功しない状態を防ぐのが目的。

設計判断のメモ（次にインフラ実装するときに参照）:

- 永続化技術は **SQLAlchemy（またはpsycopg）でSupabaseのPostgresに直接接続**する方針に決定。`supabase-py`のRESTクライアントは複数テーブルをまたぐ本物のトランザクションができないため、`IUnitOfWork`のcommit/rollbackと相性が悪い。
- `supabase-py` + RLS（ユーザー起点CRUD向けの一般的なパターン）は、recommitにはまだ不要と判断。理由: 今のところ書き込み経路は夜間バッチ1本のみで、エンドユーザーが直接Supabaseを叩く経路（Webフロントエンド）が存在しないため。Web版を作る段階になったら再検討する。
- DIコンテナは導入しない。`injector`のようなライブラリは、バッチ1本のentrypointの規模には過剰。`backend/application/`のentrypointで手動でオブジェクトを組み立てる（軽量な自前wiring）方針。

テストは `tests/` 配下に68件（`make test` で実行）。`make lint` で ruff/mypy を backend + tests に対して実行。

## 次にやること（優先度順）

1. **永続化層のインフラ実装**（`backend/infrastructure/supabase/` 想定、SQLAlchemy/psycopgでPostgres直結）。
   - `ISourceDocumentRepository` / `IQuestionRepository` / `IUnitOfWork` の実装クラスを作る。
   - `ClaudeCodeGateway`/`ClaudeCodeLearningService` の「進行中セッションは同じ identifier のまま複数回返ることがある（冪等ではない）」契約を、`ISourceDocumentRepository`のupsertで実際に満たすこと。
   - テーブルスキーマ・マイグレーション方法（Alembic等）も未検討。
2. **バッチのオーケストレーション / entrypoint**（`backend/application/` に配線）。
   - Reader → `ClaudeCodeLearningService` → `ClaudeQuestionGeneratorGateway` → `IUnitOfWork` を繋ぐ。
   - 差分読み取り用の `last_processed_at`（`since` に渡す値）をどこかに永続化する必要がある。
   - 過去に `main.py` を削除した経緯があるので、entrypoint は再構築が必要。
3. **PR #2 のレビューで著者自身が明示的に先送りしたもの**（優先度低）:
   - `ClaudeQuestionGeneratorGateway` のモデルID/`max_tokens` を環境変数等の外部設定から注入できるようにする。
   - `ClaudeCodeLearningService.build_source_document` の `min_content_length` 判定が、本文だけでなくロール接頭辞（`[user] `/`[assistant] `）込みの文字数になっている件（実害が出たら対応）。

新しい会話でこのリポジトリの続きに着手するときは、まずこのファイルの「次にやること」を確認してから着手すること。完了した項目はこのファイルから消すか、状態を更新すること。
