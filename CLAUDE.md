# recommit (Recall)

Claude Code の利用履歴から学習素材を作り、復習用の4択問題を自動生成するツール。cron で夜間実行するローカルバッチを想定（Web はまだない）。

## アーキテクチャ

DDD + クリーンアーキテクチャ。レイヤー構成:

- `backend/domain/gateways/` — 外部システムへのポート。`I{System}Gateway`、動詞はメソッド側。実装は `backend/infrastructure/{vendor}/`。
- `backend/domain/repositories/` — 永続化ポート。`I{Aggregate}Repository`（Gateway接尾辞は付けない）。**まだ存在しない（次のPRで追加予定）**。
- `backend/domain/services/` — ドメインサービス。生データ→中立な素材への変換など。
- `backend/domain/value_objects/` / `entities/` — VO・エンティティ。
- `backend/application/` — ユースケース配線・entrypoint。**まだ空（次のPRで追加予定）**。

命名・配置の詳細な規約はセッション開始時にユーザーへ確認するか、過去の議論を参照すること（B案で確定済み: ポートは能力/システム名で命名、ベンダー名はドメインに漏らさない、gatewayの生の戻り値型はinterfaceと同じファイルに置く 等）。

## 現在の状態（2026-08-10 時点）

PR #2（`feature/qa_llm` ブランチ）で以下が完成・マージ可能:

- `backend/domain/gateways/claude_code_gateway.py` + `backend/infrastructure/claude_code/claude_code_gateway.py` — `~/.claude/projects/*/*.jsonl` を読んで `ClaudeCodeSession` を返す Reader。
- `backend/domain/services/claude_code_learning.py` — セッションをノイズ除去・シークレットマスキングして `SourceDocument`（学習素材）に変換。
- `backend/domain/gateways/question_generator_gateway.py` + `backend/infrastructure/llm/claude_question_generator.py` — `SourceDocument` から Claude で4択 `Question` を生成。

テストは `tests/` 配下に66件（`make test` で実行）。`make lint` で ruff/mypy を backend + tests に対して実行。

## 次にやること（優先度順）

1. **永続化層**（`domain/repositories/IQuestionRepository` 等、Supabase実装を想定）。
   - `ClaudeCodeGateway`/`ClaudeCodeLearningService` は「進行中セッションは同じ identifier（session_id）のまま複数回返ることがある（冪等ではない）。呼び出し側は identifier をキーに upsert すること」という契約を docstring に明記済み。**この契約を実際に満たす Repository（upsert）を実装するのがここのゴール。**
2. **バッチのオーケストレーション / entrypoint**（`backend/application/` に配線）。
   - Reader → `ClaudeCodeLearningService` → `ClaudeQuestionGeneratorGateway` → Repository を繋ぐ。
   - 差分読み取り用の `last_processed_at`（`since` に渡す値）をどこかに永続化する必要がある。
   - 過去に `main.py` を削除した経緯があるので、entrypoint は再構築が必要。
3. **PR #2 のレビューで著者自身が明示的に先送りしたもの**（優先度低）:
   - `ClaudeQuestionGeneratorGateway` のモデルID/`max_tokens` を環境変数等の外部設定から注入できるようにする。
   - `ClaudeCodeLearningService.build_source_document` の `min_content_length` 判定が、本文だけでなくロール接頭辞（`[user] `/`[assistant] `）込みの文字数になっている件（実害が出たら対応）。

新しい会話でこのリポジトリの続きに着手するときは、まずこのファイルの「次にやること」を確認してから着手すること。完了した項目はこのファイルから消すか、状態を更新すること。
