"""D021 durable hosted analysis record schema."""

# ruff: noqa: E501

ANALYSIS_LIFECYCLE_SCHEMA_SQL = """
create table if not exists portfell_app.hosted_analysis_records (
    analysis_record_id uuid primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    project_id uuid not null references portfell_app.projects(project_id) on delete cascade,
    selection_id uuid not null references portfell_app.project_selection_versions(selection_version_id) on delete restrict,
    logical_hash text not null,
    status text not null,
    document jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, logical_hash)
);
alter table portfell_app.hosted_analysis_records enable row level security;
alter table portfell_app.hosted_analysis_records force row level security;
drop policy if exists hosted_analysis_records_user_isolation on portfell_app.hosted_analysis_records;
create policy hosted_analysis_records_user_isolation on portfell_app.hosted_analysis_records
    using (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid)
    with check (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid);
grant select, insert, update on portfell_app.hosted_analysis_records to portfell_app;
grant select on portfell_app.hosted_analysis_records to portfell_readonly;
revoke delete on portfell_app.hosted_analysis_records from portfell_app;
"""
