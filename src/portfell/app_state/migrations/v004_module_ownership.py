"""Owner schemas and ID-only hand-off tables for the independent stages."""

from portfell.app_state.migrations.v001_initial import AppStateMigration

_MODULE_OWNERSHIP_SQL = """
create schema if not exists workflow;
create schema if not exists metadata;
create schema if not exists univariate;
create schema if not exists bivariate;
create schema if not exists multivariate;

create table if not exists workflow.stage_commands (
    command_id text primary key check (btrim(command_id) <> ''),
    stage text not null check (stage in ('metadata', 'univariate', 'bivariate', 'multivariate')),
    input_ref text not null check (btrim(input_ref) <> ''),
    operation text not null check (btrim(operation) <> ''),
    idempotency_key text not null check (btrim(idempotency_key) <> ''),
    algorithm_version text not null check (btrim(algorithm_version) <> ''),
    status text not null default 'queued'
        check (status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    requested_at timestamptz not null default now(),
    claimed_at timestamptz,
    completed_at timestamptz,
    unique (stage, input_ref, operation, algorithm_version),
    unique (idempotency_key)
);

create table if not exists metadata.universes (
    metadata_universe_id text primary key check (btrim(metadata_universe_id) <> ''),
    source_snapshot_id text not null check (btrim(source_snapshot_id) <> ''),
    content_hash text not null check (btrim(content_hash) <> ''),
    member_count integer not null check (member_count >= 0),
    published_at timestamptz not null default now()
);

create table if not exists univariate.runs (
    univariate_run_id text primary key check (btrim(univariate_run_id) <> ''),
    metadata_universe_id text not null check (btrim(metadata_universe_id) <> ''),
    algorithm_version text not null check (btrim(algorithm_version) <> ''),
    status text not null check (
        status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')
    ),
    published_at timestamptz
);

create table if not exists univariate.selections (
    univariate_selection_id text primary key check (btrim(univariate_selection_id) <> ''),
    metadata_universe_id text not null check (btrim(metadata_universe_id) <> ''),
    univariate_run_id text not null check (btrim(univariate_run_id) <> ''),
    content_hash text not null check (btrim(content_hash) <> ''),
    member_count integer not null check (member_count >= 0),
    published_at timestamptz not null default now()
);

create table if not exists bivariate.runs (
    bivariate_run_id text primary key check (btrim(bivariate_run_id) <> ''),
    univariate_selection_id text not null check (btrim(univariate_selection_id) <> ''),
    algorithm_version text not null check (btrim(algorithm_version) <> ''),
    status text not null check (
        status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')
    ),
    candidate_pair_count integer not null check (candidate_pair_count >= 0),
    published_at timestamptz
);

create table if not exists multivariate.runs (
    multivariate_run_id text primary key check (btrim(multivariate_run_id) <> ''),
    bivariate_run_id text not null check (btrim(bivariate_run_id) <> ''),
    algorithm_version text not null check (btrim(algorithm_version) <> ''),
    status text not null check (
        status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')
    ),
    published_at timestamptz
);

create or replace function workflow.reject_immutable_row()
returns trigger language plpgsql as $$
begin raise exception 'module_handoff_immutable'; end;
$$;

create trigger universes_immutable before update or delete on metadata.universes
    for each row execute function workflow.reject_immutable_row();
create trigger selections_immutable before update or delete on univariate.selections
    for each row execute function workflow.reject_immutable_row();
create trigger bivariate_runs_immutable before update or delete on bivariate.runs
    for each row execute function workflow.reject_immutable_row();
create trigger multivariate_runs_immutable before update or delete on multivariate.runs
    for each row execute function workflow.reject_immutable_row();

revoke all on schema workflow, metadata, univariate, bivariate, multivariate from public;
revoke all on all tables in schema workflow, metadata, univariate, bivariate,
    multivariate from public;
""".strip()

_MODULE_OWNERSHIP_DOWN_SQL = """
drop schema if exists multivariate cascade;
drop schema if exists bivariate cascade;
drop schema if exists univariate cascade;
drop schema if exists metadata cascade;
drop schema if exists workflow cascade;
""".strip()

MIGRATION_V004 = AppStateMigration(
    version=4,
    name="module_postgres_ownership_v4",
    sql=_MODULE_OWNERSHIP_SQL,
    destructive_down_sql=_MODULE_OWNERSHIP_DOWN_SQL,
)
