"""Forward-only PostgreSQL migration SQL for D017 tenant control state."""

# ruff: noqa: E501

from __future__ import annotations

from portfell.durable_job_schema import D017_DURABLE_JOB_SCHEMA_SQL

__all__ = [
    "D017_DURABLE_JOB_SCHEMA_SQL",
    "D017_ROLE_SPECS",
    "D017_TABLE_SPECS",
    "D017_TENANT_CONTROL_SCHEMA_SQL",
]

D017_ROLE_SPECS: tuple[tuple[str, str, bool, bool], ...] = (
    (
        "portfell_worker",
        "Ingestion and analysis worker role without table ownership or RLS bypass.",
        False,
        False,
    ),
)

D017_TABLE_SPECS: tuple[tuple[str, bool, bool, str], ...] = (
    (
        "portfell_app.project_selection_versions",
        True,
        True,
        "Immutable canonical project membership versions.",
    ),
    (
        "portfell_app.project_selection_members",
        True,
        True,
        "One canonical listing per ISIN in an immutable project membership.",
    ),
    (
        "portfell_app.project_artifact_refs",
        True,
        True,
        "Tenant authorization references to future shared artifacts.",
    ),
)

D017_TENANT_CONTROL_SCHEMA_SQL = """
alter table portfell_app.projects
    add column if not exists status text not null default 'active',
    add column if not exists deleted_at timestamptz;

alter table portfell_app.projects
    drop constraint if exists projects_d017_status_deleted_at_check;
alter table portfell_app.projects
    add constraint projects_d017_status_deleted_at_check
    check (
        (status in ('active', 'deleted'))
        and ((status = 'deleted') = (deleted_at is not null))
    ) not valid;
alter table portfell_app.projects
    drop constraint if exists projects_project_id_user_id_key;
alter table portfell_app.projects
    add constraint projects_project_id_user_id_key unique (project_id, user_id);

create table if not exists portfell_app.project_selection_versions (
    selection_version_id uuid primary key,
    project_id uuid not null,
    user_id uuid not null,
    membership_hash text not null check (btrim(membership_hash) <> ''),
    canonical_listing_policy_version text not null check (btrim(canonical_listing_policy_version) <> ''),
    created_at timestamptz not null default now(),
    membership_sealed_at timestamptz,
    unique (project_id),
    unique (selection_version_id, project_id, user_id),
    foreign key (project_id, user_id)
        references portfell_app.projects(project_id, user_id)
        on delete restrict
);

create table if not exists portfell_app.project_selection_members (
    selection_version_id uuid not null,
    project_id uuid not null,
    user_id uuid not null,
    isin text not null check (btrim(isin) <> ''),
    provider text not null check (btrim(provider) <> ''),
    exchange text not null check (btrim(exchange) <> ''),
    code text not null check (btrim(code) <> ''),
    canonical_listing_id text not null check (btrim(canonical_listing_id) <> ''),
    created_at timestamptz not null default now(),
    primary key (selection_version_id, isin),
    unique (selection_version_id, canonical_listing_id),
    foreign key (selection_version_id, project_id, user_id)
        references portfell_app.project_selection_versions(selection_version_id, project_id, user_id)
        on delete restrict
);

create table if not exists portfell_app.project_artifact_refs (
    project_artifact_ref_id uuid primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete restrict,
    project_id uuid not null references portfell_app.projects(project_id) on delete restrict,
    analysis_run_id uuid not null references portfell_app.analysis_runs(analysis_run_id) on delete restrict,
    artifact_id text not null check (btrim(artifact_id) <> ''),
    created_at timestamptz not null default now(),
    unique (project_id, analysis_run_id, artifact_id)
);

create index if not exists project_selection_versions_user_id_idx
    on portfell_app.project_selection_versions(user_id);
create index if not exists project_selection_members_project_id_idx
    on portfell_app.project_selection_members(project_id);
create index if not exists project_artifact_refs_user_id_idx
    on portfell_app.project_artifact_refs(user_id);

create or replace function portfell_app.reject_project_membership_mutation()
returns trigger
language plpgsql
as $$
begin
    if tg_table_name = 'project_selection_versions'
        and tg_op = 'UPDATE'
        and old.membership_sealed_at is null
        and new.membership_sealed_at is not null then
        return new;
    end if;
    if tg_table_name = 'project_selection_members'
        and tg_op = 'INSERT'
        and not exists (
            select 1
            from portfell_app.project_selection_versions
            where selection_version_id = new.selection_version_id
              and membership_sealed_at is not null
        ) then
        return new;
    end if;
    raise exception 'project_membership_immutable';
end;
$$;

drop trigger if exists project_selection_versions_immutable on portfell_app.project_selection_versions;
create trigger project_selection_versions_immutable
    before update or delete on portfell_app.project_selection_versions
    for each row execute function portfell_app.reject_project_membership_mutation();
drop trigger if exists project_selection_members_immutable on portfell_app.project_selection_members;
create trigger project_selection_members_immutable
    before insert or update or delete on portfell_app.project_selection_members
    for each row execute function portfell_app.reject_project_membership_mutation();

alter table portfell_app.project_selection_versions enable row level security;
alter table portfell_app.project_selection_members enable row level security;
alter table portfell_app.project_artifact_refs enable row level security;
alter table portfell_app.project_selection_versions force row level security;
alter table portfell_app.project_selection_members force row level security;
alter table portfell_app.project_artifact_refs force row level security;

do $$
declare
    table_name text;
begin
    foreach table_name in array array[
        'project_selection_versions',
        'project_selection_members',
        'project_artifact_refs'
    ]
    loop
        execute format('drop policy if exists user_isolation on portfell_app.%I', table_name);
        execute format(
            'create policy user_isolation on portfell_app.%I
             using (user_id = nullif(current_setting(''portfell.current_user_id'', true), '''')::uuid)
             with check (user_id = nullif(current_setting(''portfell.current_user_id'', true), '''')::uuid)',
            table_name
        );
    end loop;
end $$;

grant usage on schema portfell_app to portfell_worker;
grant select, insert, update on portfell_app.project_selection_versions to portfell_app, portfell_worker;
grant select, insert, update on portfell_app.project_selection_members to portfell_app, portfell_worker;
grant select, insert, update on portfell_app.project_artifact_refs to portfell_app, portfell_worker;
grant select on portfell_app.project_selection_versions to portfell_readonly;
grant select on portfell_app.project_selection_members to portfell_readonly;
grant select on portfell_app.project_artifact_refs to portfell_readonly;
revoke delete on portfell_app.project_selection_versions from portfell_app, portfell_worker;
revoke delete on portfell_app.project_selection_members from portfell_app, portfell_worker;
revoke delete on portfell_app.project_artifact_refs from portfell_app, portfell_worker;
"""
