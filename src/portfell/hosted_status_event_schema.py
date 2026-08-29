"""Durable, tenant-scoped status event schema for resumable hosted updates."""

HOSTED_STATUS_EVENT_SCHEMA_SQL = """
create table if not exists portfell_app.status_events (
    event_id bigint generated always as identity primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    project_id uuid references portfell_app.projects(project_id) on delete cascade,
    event_type text not null check (btrim(event_type) <> ''),
    aggregate_ref text not null check (btrim(aggregate_ref) <> ''),
    projection_revision text,
    terminal_status text,
    occurred_at timestamptz not null default now()
);
create index if not exists status_events_user_event_idx
    on portfell_app.status_events (user_id, event_id);
create index if not exists status_events_retention_idx
    on portfell_app.status_events (occurred_at);
alter table portfell_app.status_events enable row level security;
alter table portfell_app.status_events force row level security;
drop policy if exists user_isolation on portfell_app.status_events;
create policy user_isolation on portfell_app.status_events
    using (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid)
    with check (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid);
grant select, insert, delete on portfell_app.status_events to portfell_app;
grant select on portfell_app.status_events to portfell_readonly;
"""
