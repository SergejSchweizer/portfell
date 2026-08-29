"""D020 durable Multivariate run lifecycle schema."""

# ruff: noqa: E501

MULTIVARIATE_LIFECYCLE_SCHEMA_SQL = """
create table if not exists portfell_app.multivariate_runs (
    multivariate_run_id text primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    project_id uuid not null references portfell_app.projects(project_id) on delete cascade,
    bivariate_run_id text not null,
    input_snapshot_id text not null,
    logical_hash text not null,
    status text not null,
    phase text not null,
    completed_units integer not null check (completed_units >= 0),
    total_units integer not null check (total_units >= completed_units),
    started_at_epoch double precision not null,
    document jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, logical_hash)
);
create table if not exists portfell_app.current_multivariate_run_preferences (
    project_id uuid primary key references portfell_app.projects(project_id) on delete cascade,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    multivariate_run_id text not null references portfell_app.multivariate_runs(multivariate_run_id) on delete cascade,
    updated_at timestamptz not null default now()
);
alter table portfell_app.multivariate_runs enable row level security;
alter table portfell_app.multivariate_runs force row level security;
alter table portfell_app.current_multivariate_run_preferences enable row level security;
alter table portfell_app.current_multivariate_run_preferences force row level security;
do $$
declare table_name text;
begin
    foreach table_name in array array['multivariate_runs', 'current_multivariate_run_preferences'] loop
        execute format('drop policy if exists multivariate_user_isolation on portfell_app.%I', table_name);
        execute format(
            'create policy multivariate_user_isolation on portfell_app.%I using (user_id = nullif(current_setting(''portfell.current_user_id'', true), '''')::uuid) with check (user_id = nullif(current_setting(''portfell.current_user_id'', true), '''')::uuid)',
            table_name
        );
    end loop;
end $$;
grant select, insert, update on portfell_app.multivariate_runs,
    portfell_app.current_multivariate_run_preferences to portfell_app;
grant select on portfell_app.multivariate_runs,
    portfell_app.current_multivariate_run_preferences to portfell_readonly;
revoke delete on portfell_app.multivariate_runs,
    portfell_app.current_multivariate_run_preferences from portfell_app;
"""
