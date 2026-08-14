"""PostgreSQL schema for tenant-scoped navigation read projections."""

from __future__ import annotations

NAVIGATION_READ_MODEL_SCHEMA_SQL = """
create table if not exists portfell_app.navigation_projections (
    user_id uuid primary key references portfell_app.users(user_id) on delete cascade,
    projection_revision bigint not null default 0 check (projection_revision >= 0),
    payload jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);
alter table portfell_app.navigation_projections enable row level security;
alter table portfell_app.navigation_projections force row level security;
drop policy if exists user_isolation on portfell_app.navigation_projections;
create policy user_isolation on portfell_app.navigation_projections
    using (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid)
    with check (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid);
grant select, insert, update on portfell_app.navigation_projections to portfell_app;
grant select on portfell_app.navigation_projections to portfell_readonly;
"""