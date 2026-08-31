"""Frozen v1 catalog contract for database ``portfell_dash``, schema ``portfell``."""

from __future__ import annotations

ANALYSIS_STAGES = ("metadata", "univariate", "bivariate", "multivariate")
ANALYSIS_STATUSES = ("queued", "running", "succeeded", "failed", "cancelled")
MULTIVARIATE_OBJECTIVES = ("return_risk", "return_drawdown", "minimum_risk")

APP_STATE_TABLES = (
    "schema_migrations",
    "workspaces",
    "market_source_snapshots",
    "metadata_universes",
    "metadata_universe_members",
    "analysis_runs",
    "analysis_artifacts",
    "univariate_selections",
    "univariate_selection_members",
    "decision_artifacts",
    "ui_preferences",
)

V1_SCHEMA_SQL = """
create schema if not exists portfell;

create table if not exists portfell.schema_migrations (
    version integer primary key check (version > 0),
    name text not null unique check (btrim(name) <> ''),
    checksum text not null check (btrim(checksum) <> ''),
    applied_at timestamptz not null default now()
);

create table if not exists portfell.workspaces (
    workspace_id text primary key check (workspace_id = 'default'),
    created_at timestamptz not null default now()
);
insert into portfell.workspaces (workspace_id)
values ('default')
on conflict (workspace_id) do nothing;

create table if not exists portfell.market_source_snapshots (
    snapshot_id text primary key check (btrim(snapshot_id) <> ''),
    source_fingerprint text not null check (btrim(source_fingerprint) <> ''),
    observed_at timestamptz not null,
    created_at timestamptz not null default now(),
    unique (source_fingerprint)
);

create table if not exists portfell.metadata_universes (
    universe_id text primary key check (btrim(universe_id) <> ''),
    workspace_id text not null default 'default'
        references portfell.workspaces(workspace_id) on delete restrict,
    source_snapshot_id text not null
        references portfell.market_source_snapshots(snapshot_id) on delete restrict,
    version integer not null check (version > 0),
    content_hash text not null check (btrim(content_hash) <> ''),
    created_at timestamptz not null default now(),
    published_at timestamptz not null default now(),
    unique (workspace_id, version),
    unique (workspace_id, content_hash)
);

create table if not exists portfell.metadata_universe_members (
    universe_id text not null
        references portfell.metadata_universes(universe_id) on delete restrict,
    isin text not null check (btrim(isin) <> ''),
    exchange text not null check (btrim(exchange) <> ''),
    code text not null check (btrim(code) <> ''),
    ordinal integer not null check (ordinal >= 0),
    created_at timestamptz not null default now(),
    primary key (universe_id, isin, exchange, code),
    unique (universe_id, ordinal)
);

create table if not exists portfell.analysis_runs (
    run_id text primary key check (btrim(run_id) <> ''),
    workspace_id text not null default 'default'
        references portfell.workspaces(workspace_id) on delete restrict,
    stage text not null check (stage in ('metadata', 'univariate', 'bivariate', 'multivariate')),
    status text not null check (status in (
        'queued', 'running', 'succeeded', 'failed', 'cancelled'
    )),
    input_snapshot_id text not null
        references portfell.market_source_snapshots(snapshot_id) on delete restrict,
    input_ref text not null check (btrim(input_ref) <> ''),
    logical_hash text not null check (btrim(logical_hash) <> ''),
    algorithm_version text not null check (btrim(algorithm_version) <> ''),
    failure_code text,
    created_at timestamptz not null default now(),
    started_at timestamptz,
    completed_at timestamptz,
    unique (workspace_id, stage, logical_hash),
    check ((status = 'running') = (started_at is not null and completed_at is null)
        or status <> 'running'),
    check ((status in ('succeeded', 'failed', 'cancelled')) = (completed_at is not null)),
    check ((status = 'failed') = (failure_code is not null))
);

create table if not exists portfell.analysis_artifacts (
    artifact_id text primary key check (btrim(artifact_id) <> ''),
    run_id text not null references portfell.analysis_runs(run_id) on delete restrict,
    artifact_type text not null check (btrim(artifact_type) <> ''),
    content_hash text not null check (btrim(content_hash) <> ''),
    document jsonb not null,
    created_at timestamptz not null default now(),
    unique (run_id, artifact_type),
    unique (artifact_type, content_hash)
);

create table if not exists portfell.univariate_selections (
    selection_id text primary key check (btrim(selection_id) <> ''),
    workspace_id text not null default 'default'
        references portfell.workspaces(workspace_id) on delete restrict,
    source_run_id text not null references portfell.analysis_runs(run_id) on delete restrict,
    version integer not null check (version > 0),
    content_hash text not null check (btrim(content_hash) <> ''),
    created_at timestamptz not null default now(),
    published_at timestamptz not null default now(),
    unique (workspace_id, version),
    unique (workspace_id, content_hash)
);

create table if not exists portfell.univariate_selection_members (
    selection_id text not null
        references portfell.univariate_selections(selection_id) on delete restrict,
    isin text not null check (btrim(isin) <> ''),
    exchange text not null check (btrim(exchange) <> ''),
    code text not null check (btrim(code) <> ''),
    ordinal integer not null check (ordinal >= 0),
    created_at timestamptz not null default now(),
    primary key (selection_id, isin, exchange, code),
    unique (selection_id, ordinal)
);

create table if not exists portfell.decision_artifacts (
    decision_id text primary key check (btrim(decision_id) <> ''),
    run_id text not null unique references portfell.analysis_runs(run_id) on delete restrict,
    objective text not null check (objective in ('return_risk', 'return_drawdown', 'minimum_risk')),
    winning_candidate_id text not null check (btrim(winning_candidate_id) <> ''),
    requested_method text not null check (btrim(requested_method) <> ''),
    actual_method text not null check (btrim(actual_method) <> ''),
    available boolean not null,
    production_eligible boolean not null,
    reason text,
    document jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists portfell.ui_preferences (
    workspace_id text not null default 'default'
        references portfell.workspaces(workspace_id) on delete restrict,
    preference_key text not null check (btrim(preference_key) <> ''),
    value jsonb not null,
    updated_at timestamptz not null default now(),
    primary key (workspace_id, preference_key)
);

create index if not exists metadata_universes_snapshot_idx
    on portfell.metadata_universes(source_snapshot_id);
create index if not exists metadata_universe_members_identity_idx
    on portfell.metadata_universe_members(isin, exchange, code);
create index if not exists analysis_runs_stage_created_idx
    on portfell.analysis_runs(stage, created_at desc);
create index if not exists analysis_runs_snapshot_idx
    on portfell.analysis_runs(input_snapshot_id);
create index if not exists analysis_artifacts_run_idx
    on portfell.analysis_artifacts(run_id);
create index if not exists univariate_selection_members_identity_idx
    on portfell.univariate_selection_members(isin, exchange, code);

create or replace function portfell.reject_immutable_row()
returns trigger
language plpgsql
as $$
begin
    raise exception 'app_state_immutable';
end;
$$;

create or replace function portfell.enforce_analysis_run_transition()
returns trigger
language plpgsql
as $$
begin
    if old.run_id <> new.run_id
        or old.workspace_id <> new.workspace_id
        or old.stage <> new.stage
        or old.input_snapshot_id <> new.input_snapshot_id
        or old.input_ref <> new.input_ref
        or old.logical_hash <> new.logical_hash
        or old.algorithm_version <> new.algorithm_version
        or old.created_at <> new.created_at then
        raise exception 'analysis_run_identity_immutable';
    end if;
    if old.status in ('succeeded', 'failed', 'cancelled') then
        raise exception 'analysis_run_terminal';
    end if;
    if old.status = 'queued' and new.status not in ('queued', 'running', 'failed', 'cancelled') then
        raise exception 'analysis_run_transition_invalid';
    end if;
    if old.status = 'running' and new.status not in (
        'running', 'succeeded', 'failed', 'cancelled'
    ) then
        raise exception 'analysis_run_transition_invalid';
    end if;
    return new;
end;
$$;

create trigger market_source_snapshots_immutable
    before update or delete on portfell.market_source_snapshots
    for each row execute function portfell.reject_immutable_row();
create trigger metadata_universes_immutable
    before update or delete on portfell.metadata_universes
    for each row execute function portfell.reject_immutable_row();
create trigger metadata_universe_members_immutable
    before update or delete on portfell.metadata_universe_members
    for each row execute function portfell.reject_immutable_row();
create trigger analysis_artifacts_immutable
    before update or delete on portfell.analysis_artifacts
    for each row execute function portfell.reject_immutable_row();
create trigger univariate_selections_immutable
    before update or delete on portfell.univariate_selections
    for each row execute function portfell.reject_immutable_row();
create trigger univariate_selection_members_immutable
    before update or delete on portfell.univariate_selection_members
    for each row execute function portfell.reject_immutable_row();
create trigger decision_artifacts_immutable
    before update or delete on portfell.decision_artifacts
    for each row execute function portfell.reject_immutable_row();
create trigger analysis_runs_transition
    before update on portfell.analysis_runs
    for each row execute function portfell.enforce_analysis_run_transition();

revoke all on schema portfell from public;
revoke all on all tables in schema portfell from public;
""".strip()

V1_DESTRUCTIVE_DOWN_SQL = """
drop schema if exists portfell cascade;
""".strip()
