"""Forward-only schema for one durable exact-selection initial fill per project."""

# ruff: noqa: E501

PROJECT_BOOTSTRAP_SCHEMA_SQL = """
alter table portfell_app.project_selection_versions
    add column if not exists name text not null default 'metadata_selection';

create table if not exists portfell_app.project_initial_fills (
    project_id uuid primary key references portfell_app.projects(project_id) on delete restrict,
    user_id uuid not null references portfell_app.users(user_id) on delete restrict,
    selection_version_id uuid not null references portfell_app.project_selection_versions(selection_version_id) on delete restrict,
    membership_hash text not null check (btrim(membership_hash) <> ''),
    selected_listing_count integer not null check (selected_listing_count > 0),
    bootstrap_job_id uuid not null unique references portfell_app.jobs(job_id) on delete restrict,
    status text not null check (status in ('not_started', 'planning', 'running', 'ready', 'partial', 'failed')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (project_id, user_id, selection_version_id)
);

create index if not exists project_initial_fills_user_id_idx
    on portfell_app.project_initial_fills(user_id);

alter table portfell_app.project_initial_fills enable row level security;
alter table portfell_app.project_initial_fills force row level security;
drop policy if exists user_isolation on portfell_app.project_initial_fills;
create policy user_isolation on portfell_app.project_initial_fills
    using (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid)
    with check (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid);

grant select, insert, update on portfell_app.project_initial_fills to portfell_app, portfell_worker;
grant select on portfell_app.project_initial_fills to portfell_readonly;
revoke delete on portfell_app.project_initial_fills from portfell_app, portfell_worker;
"""
