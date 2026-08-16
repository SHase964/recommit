-- recommit の永続化スキーマ。テーブルが2つだけの規模なので、Alembic等は導入せず
-- 手書きSQLで管理する（テーブルが増えてきたら再検討する）。
--
-- gen_random_uuid() は PostgreSQL 13 以降コア機能なので拡張のインストールは不要。

create table if not exists source_documents (
    id uuid primary key default gen_random_uuid(),
    source_type text not null,
    identifier text not null,
    title text,
    content text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (source_type, identifier)
);

create table if not exists questions (
    id uuid primary key default gen_random_uuid(),
    prompt text not null,
    choices jsonb not null,
    correct_index smallint not null check (correct_index between 0 and 3),
    explanation text not null,
    category text not null,
    source_type text not null,
    source_identifier text not null,
    created_at timestamptz not null default now(),
    foreign key (source_type, source_identifier)
        references source_documents (source_type, identifier)
);
