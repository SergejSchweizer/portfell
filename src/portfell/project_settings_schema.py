"""D019 durable project-scoped selection settings."""

# ruff: noqa: E501

PROJECT_SETTINGS_SCHEMA_SQL = """
create table if not exists portfell_app.project_univariate_settings (
    project_id uuid primary key references portfell_app.projects(project_id) on delete cascade,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    settings jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now()
);
alter table portfell_app.project_univariate_settings enable row level security;
alter table portfell_app.project_univariate_settings force row level security;
drop policy if exists project_univariate_settings_user_isolation on portfell_app.project_univariate_settings;
create policy project_univariate_settings_user_isolation on portfell_app.project_univariate_settings
    using (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid)
    with check (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid);
grant select, insert, update on portfell_app.project_univariate_settings to portfell_app;
grant select on portfell_app.project_univariate_settings to portfell_readonly;
revoke delete on portfell_app.project_univariate_settings from portfell_app;
"""
