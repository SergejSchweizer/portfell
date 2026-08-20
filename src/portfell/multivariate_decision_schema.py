"""Idempotent PostgreSQL schema for Multivariate decision/history evidence."""

from __future__ import annotations

from portfell.hosted_catalog_ports import CatalogConnection

MULTIVARIATE_DECISION_SCHEMA_VERSION = 25
MULTIVARIATE_DECISION_SCHEMA_NAME = "multivariate_decision_history_evidence"

MULTIVARIATE_DECISION_SCHEMA_SQL = """
create table if not exists portfell_app.multivariate_decisions (
    decision_id text primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    project_id uuid not null references portfell_app.projects(project_id) on delete cascade,
    run_id text not null,
    stage text not null,
    canonical_payload jsonb not null,
    created_at timestamptz not null default now(),
    unique (user_id, project_id, run_id, stage, decision_id)
);

create table if not exists portfell_app.research_universe_snapshots (
    snapshot_id text primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    project_id uuid not null references portfell_app.projects(project_id) on delete cascade,
    run_id text not null,
    stage text not null,
    canonical_payload jsonb not null,
    created_at timestamptz not null default now(),
    unique (user_id, project_id, run_id, stage, snapshot_id)
);

create table if not exists portfell_app.multivariate_current_selections (
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    project_id uuid not null references portfell_app.projects(project_id) on delete cascade,
    selection_revision text not null,
    canonical_payload jsonb not null,
    updated_at timestamptz not null default now(),
    primary key (user_id, project_id)
);

alter table portfell_app.multivariate_decisions enable row level security;
alter table portfell_app.multivariate_decisions force row level security;
drop policy if exists user_isolation on portfell_app.multivariate_decisions;
create policy user_isolation on portfell_app.multivariate_decisions
    using (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid)
    with check (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid);

alter table portfell_app.research_universe_snapshots enable row level security;
alter table portfell_app.research_universe_snapshots force row level security;
drop policy if exists user_isolation on portfell_app.research_universe_snapshots;
create policy user_isolation on portfell_app.research_universe_snapshots
    using (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid)
    with check (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid);

alter table portfell_app.multivariate_current_selections enable row level security;
alter table portfell_app.multivariate_current_selections force row level security;
drop policy if exists user_isolation on portfell_app.multivariate_current_selections;
create policy user_isolation on portfell_app.multivariate_current_selections
    using (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid)
    with check (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid);

grant select, insert on portfell_app.multivariate_decisions to portfell_app;
grant select, insert on portfell_app.research_universe_snapshots to portfell_app;
grant select, insert, update on portfell_app.multivariate_current_selections to portfell_app;
grant select on portfell_app.multivariate_decisions, portfell_app.research_universe_snapshots,
    portfell_app.multivariate_current_selections to portfell_readonly;
"""


def apply_multivariate_decision_schema(connection: CatalogConnection) -> None:
    """Apply the create-only schema safely; statements are idempotent by construction."""

    connection.execute(MULTIVARIATE_DECISION_SCHEMA_SQL)
