"""Durable staged-analysis job and progress migration."""

from portfell.app_state.migrations.v001_initial import AppStateMigration

_ANALYSIS_JOBS_SQL = """
create table if not exists portfell.analysis_jobs (
    job_id text primary key check (btrim(job_id) <> ''),
    workspace_id text not null default 'default'
        references portfell.workspaces(workspace_id) on delete restrict,
    stage text not null check (stage in ('univariate', 'bivariate', 'multivariate')),
    input_ref text not null check (btrim(input_ref) <> ''),
    requested_objective text check (
        requested_objective is null
        or requested_objective in ('return_risk', 'return_drawdown', 'minimum_risk')
    ),
    status text not null check (status in (
        'queued', 'running', 'succeeded', 'failed', 'cancelled'
    )),
    run_id text references portfell.analysis_runs(run_id) on delete restrict,
    progress_current bigint not null default 0 check (progress_current >= 0),
    progress_total bigint check (progress_total is null or progress_total >= 0),
    progress_phase text,
    attempt integer not null default 0 check (attempt >= 0),
    heartbeat_at timestamptz,
    failure_code text,
    created_at timestamptz not null default now(),
    started_at timestamptz,
    completed_at timestamptz,
    check (progress_total is null or progress_current <= progress_total),
    check ((status in ('succeeded', 'failed', 'cancelled')) = (completed_at is not null)),
    check ((status = 'failed') = (failure_code is not null))
);

create unique index if not exists analysis_jobs_active_logical_idx
    on portfell.analysis_jobs (
        stage, input_ref, coalesce(requested_objective, '')
    )
    where status in ('queued', 'running');
create index if not exists analysis_jobs_stage_status_idx
    on portfell.analysis_jobs(stage, status, created_at desc, job_id);
create index if not exists analysis_jobs_recent_idx
    on portfell.analysis_jobs(created_at desc, job_id);
create index if not exists analysis_jobs_run_idx
    on portfell.analysis_jobs(run_id) where run_id is not null;

create or replace function portfell.enforce_analysis_job_transition()
returns trigger
language plpgsql
as $$
begin
    if old.job_id <> new.job_id
        or old.workspace_id <> new.workspace_id
        or old.stage <> new.stage
        or old.input_ref <> new.input_ref
        or old.requested_objective is distinct from new.requested_objective
        or old.created_at <> new.created_at then
        raise exception 'analysis_job_identity_immutable';
    end if;
    if old.status in ('succeeded', 'failed', 'cancelled') then
        raise exception 'analysis_job_terminal';
    end if;
    if new.attempt < old.attempt then
        raise exception 'analysis_job_attempt_regression';
    end if;
    if new.attempt = old.attempt and new.progress_current < old.progress_current then
        raise exception 'analysis_job_progress_regression';
    end if;
    if old.progress_total is not null
        and new.attempt = old.attempt
        and new.progress_total is distinct from old.progress_total then
        raise exception 'analysis_job_total_changed';
    end if;
    return new;
end;
$$;

create trigger analysis_jobs_transition
    before update on portfell.analysis_jobs
    for each row execute function portfell.enforce_analysis_job_transition();
""".strip()

_ANALYSIS_JOBS_DOWN_SQL = """
drop table if exists portfell.analysis_jobs;
drop function if exists portfell.enforce_analysis_job_transition();
""".strip()

MIGRATION_V002 = AppStateMigration(
    version=2,
    name="durable_analysis_jobs_v2",
    sql=_ANALYSIS_JOBS_SQL,
    destructive_down_sql=_ANALYSIS_JOBS_DOWN_SQL,
)
