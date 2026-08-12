"""Durable worker queue for shared metadata refresh requests."""

from __future__ import annotations

METADATA_REFRESH_JOB_SCHEMA_SQL = """
create table if not exists portfell_app.metadata_refresh_jobs (
    metadata_run_id uuid primary key
        references portfell_app.metadata_runs(metadata_run_id) on delete cascade,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    status text not null check (status in ('queued', 'running', 'succeeded', 'failed')),
    lease_token uuid,
    lease_expires_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check ((lease_token is null) = (lease_expires_at is null))
);
create index if not exists metadata_refresh_jobs_claim_idx
    on portfell_app.metadata_refresh_jobs (status, created_at);
"""
