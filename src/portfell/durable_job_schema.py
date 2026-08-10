"""D017 durable job queue schema contracts."""

D017_DURABLE_JOB_SCHEMA_SQL = """
create table if not exists portfell_app.jobs (
    job_id uuid primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete restrict,
    project_id uuid not null references portfell_app.projects(project_id) on delete restrict,
    job_kind text not null check (btrim(job_kind) <> ''),
    input_hash text not null check (btrim(input_hash) <> ''),
    input_ref text not null check (btrim(input_ref) <> ''),
    status text not null check (
        status in ('queued', 'running', 'succeeded', 'partial', 'failed', 'cancelled')
    ),
    priority integer not null default 0,
    completed_units integer not null default 0 check (completed_units >= 0),
    total_units integer not null default 0 check (total_units >= 0),
    attempt_count integer not null default 0 check (attempt_count >= 0),
    available_at timestamptz not null default now(),
    lease_owner text,
    lease_token uuid,
    lease_expires_at timestamptz,
    heartbeat_at timestamptz,
    terminal_code text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (job_kind, input_hash),
    check ((lease_owner is null) = (lease_token is null)),
    check ((lease_token is null) = (lease_expires_at is null))
);

create table if not exists portfell_app.job_attempts (
    job_attempt_id uuid primary key,
    job_id uuid not null references portfell_app.jobs(job_id) on delete restrict,
    attempt_number integer not null check (attempt_number > 0),
    worker_id text not null check (btrim(worker_id) <> ''),
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    terminal_code text,
    unique (job_id, attempt_number)
);

create table if not exists portfell_app.outbox_events (
    event_id uuid primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete restrict,
    event_type text not null check (btrim(event_type) <> ''),
    aggregate_ref text not null check (btrim(aggregate_ref) <> ''),
    status text not null default 'pending' check (status in ('pending', 'delivered')),
    created_at timestamptz not null default now(),
    delivered_at timestamptz
);

create index if not exists jobs_claim_idx
    on portfell_app.jobs (status, available_at, priority desc, created_at);
create index if not exists job_attempts_job_id_idx on portfell_app.job_attempts (job_id);
create index if not exists outbox_events_status_idx
    on portfell_app.outbox_events (status, created_at);
"""
