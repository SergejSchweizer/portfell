"""PostgreSQL schema for compact project-scoped workflow projections."""

from __future__ import annotations

PROJECT_WORKFLOW_TABLE_SPECS = (
    (
        "portfell_app.project_research_run_mappings",
        True,
        False,
        "Durable project ownership for univariate and bivariate research runs.",
    ),
)

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

PROJECT_RESEARCH_RUN_MAPPING_SCHEMA_SQL = """
create table if not exists portfell_app.project_research_run_mappings (
    research_run_id text primary key
        references portfell_app.research_runs(research_run_id) on delete cascade,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    project_id uuid not null references portfell_app.projects(project_id) on delete cascade,
    unique (research_run_id, user_id),
    unique (research_run_id, project_id)
);
create index if not exists project_research_run_mappings_project_id_idx
    on portfell_app.project_research_run_mappings(project_id);
alter table portfell_app.project_research_run_mappings enable row level security;
alter table portfell_app.project_research_run_mappings force row level security;
drop policy if exists user_isolation on portfell_app.project_research_run_mappings;
create policy user_isolation on portfell_app.project_research_run_mappings
    using (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid)
    with check (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid);
grant select, insert, update on portfell_app.project_research_run_mappings to portfell_app;
grant select on portfell_app.project_research_run_mappings to portfell_readonly;
"""
