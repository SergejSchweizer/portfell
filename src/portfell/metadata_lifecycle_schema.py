"""D017 durable metadata lifecycle schema migration."""

# ruff: noqa: E501

from __future__ import annotations

METADATA_LIFECYCLE_SCHEMA_SQL = """
create table if not exists portfell_app.metadata_runs (
    metadata_run_id uuid primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    status text not null check (status in ('running', 'succeeded', 'failed')),
    total bigint not null check (total >= 0),
    completed bigint not null check (completed >= 0 and completed <= total),
    skipped_exchange_count bigint not null check (skipped_exchange_count >= 0),
    percent integer not null check (percent between 0 and 100),
    summary jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    finished_at timestamptz
);
create table if not exists portfell_app.metadata_revision_pointers (
    user_id uuid primary key references portfell_app.users(user_id) on delete cascade,
    revision_id text not null,
    updated_at timestamptz not null default now()
);
create table if not exists portfell_app.request_idempotency (
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    operation text not null,
    idempotency_key text not null,
    request_hash text not null,
    response_ref text not null,
    created_at timestamptz not null default now(),
    primary key (user_id, operation, idempotency_key)
);
alter table portfell_app.metadata_runs enable row level security;
alter table portfell_app.metadata_runs force row level security;
alter table portfell_app.metadata_revision_pointers enable row level security;
alter table portfell_app.metadata_revision_pointers force row level security;
alter table portfell_app.request_idempotency enable row level security;
alter table portfell_app.request_idempotency force row level security;
drop policy if exists metadata_runs_user_isolation on portfell_app.metadata_runs;
create policy metadata_runs_user_isolation on portfell_app.metadata_runs using (user_id = current_setting('portfell.current_user_id', true)::uuid) with check (user_id = current_setting('portfell.current_user_id', true)::uuid);
drop policy if exists metadata_revision_pointers_user_isolation on portfell_app.metadata_revision_pointers;
create policy metadata_revision_pointers_user_isolation on portfell_app.metadata_revision_pointers using (user_id = current_setting('portfell.current_user_id', true)::uuid) with check (user_id = current_setting('portfell.current_user_id', true)::uuid);
drop policy if exists request_idempotency_user_isolation on portfell_app.request_idempotency;
create policy request_idempotency_user_isolation on portfell_app.request_idempotency using (user_id = current_setting('portfell.current_user_id', true)::uuid) with check (user_id = current_setting('portfell.current_user_id', true)::uuid);
"""
