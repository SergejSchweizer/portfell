"""PostgreSQL schema for compact project-scoped workflow projections."""

from __future__ import annotations

PROJECT_WORKFLOW_PROJECTION_SCHEMA_SQL = """
create table if not exists portfell_app.project_workflow_projections (
    project_id uuid primary key references portfell_app.projects(project_id) on delete restrict,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    projection_revision bigint not null default 0 check (projection_revision >= 0),
    payload jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now(),
    unique (project_id, user_id)
);
create index if not exists project_workflow_projections_user_id_idx
    on portfell_app.project_workflow_projections(user_id);
alter table portfell_app.project_workflow_projections enable row level security;
alter table portfell_app.project_workflow_projections force row level security;
drop policy if exists user_isolation on portfell_app.project_workflow_projections;
create policy user_isolation on portfell_app.project_workflow_projections
    using (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid)
    with check (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid);
grant select, insert, update on portfell_app.project_workflow_projections to portfell_app;
grant select on portfell_app.project_workflow_projections to portfell_readonly;
"""
