"""Durable, monotonic checkpoints for resumable multivariate computation."""

from portfell.app_state.migrations.v001_initial import AppStateMigration


_SQL = """
create table if not exists portfell.multivariate_checkpoints (
    dataset_digest text primary key check (btrim(dataset_digest) <> ''),
    algorithm_version text not null check (btrim(algorithm_version) <> ''),
    phase integer not null check (phase >= 0 and phase <= 8),
    phase_name text not null check (btrim(phase_name) <> ''),
    payload bytea not null,
    payload_hash text not null check (btrim(payload_hash) <> ''),
    updated_at timestamptz not null default now()
);
create index if not exists multivariate_checkpoints_updated_idx
    on portfell.multivariate_checkpoints(updated_at desc);
""".strip()

MIGRATION_V007 = AppStateMigration(
    version=7,
    name="resumable_multivariate_checkpoints_v7",
    sql=_SQL,
    destructive_down_sql="drop table if exists portfell.multivariate_checkpoints;",
)
