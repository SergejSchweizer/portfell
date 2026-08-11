"""Hosted PostgreSQL catalog contracts and deterministic migrations."""

# ruff: noqa: E501

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from portfell.hosted_download_run_schema import DOWNLOAD_RUN_PARTIAL_STATUS_SQL
from portfell.legacy_import_schema import LEGACY_IMPORT_LEDGER_SQL
from portfell.metadata_lifecycle_schema import METADATA_LIFECYCLE_SCHEMA_SQL
from portfell.project_settings_schema import PROJECT_SETTINGS_SCHEMA_SQL
from portfell.research_lifecycle_schema import RESEARCH_LIFECYCLE_SCHEMA_SQL
from portfell.tenant_control_schema import (
    D017_DURABLE_JOB_SCHEMA_SQL,
    D017_ROLE_SPECS,
    D017_TABLE_SPECS,
    D017_TENANT_CONTROL_SCHEMA_SQL,
)


class CatalogConnection(Protocol):
    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> CatalogResult: ...


class CatalogResult(Protocol):
    def fetchone(self) -> tuple[str] | None: ...


@dataclass(frozen=True)
class HostedRole:
    """PostgreSQL role contract for hosted mode.

    Args:
        name: Stable PostgreSQL role name.
        purpose: Human-readable ownership boundary.
        owns_tables: Whether this role owns catalog objects.
        can_bypass_rls: Whether PostgreSQL BYPASSRLS is allowed.
    """

    name: str
    purpose: str
    owns_tables: bool
    can_bypass_rls: bool


@dataclass(frozen=True)
class HostedTable:
    """Hosted catalog table contract.

    Args:
        name: Fully qualified logical table name.
        user_scoped: Whether rows are owned by exactly one Portfell user.
        immutable: Whether rows are append-only after publication.
        purpose: Short ownership description.
    """

    name: str
    user_scoped: bool
    immutable: bool
    purpose: str


@dataclass(frozen=True)
class HostedMigration:
    """Versioned hosted catalog migration.

    Args:
        version: Monotonic integer migration version.
        name: Stable migration name.
        sql: SQL body to execute.
    """

    version: int
    name: str
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()


HOSTED_ROLES: tuple[HostedRole, ...] = (
    HostedRole(
        name="portfell_owner",
        purpose="Owns database objects only; never used by the application runtime.",
        owns_tables=True,
        can_bypass_rls=False,
    ),
    HostedRole(
        name="portfell_migrator",
        purpose="Applies migrations without bypassing user-row policies.",
        owns_tables=False,
        can_bypass_rls=False,
    ),
    HostedRole(
        name="portfell_app",
        purpose="Runtime application role with transaction-local authenticated user context.",
        owns_tables=False,
        can_bypass_rls=False,
    ),
    *(HostedRole(*spec) for spec in D017_ROLE_SPECS),
    HostedRole(
        name="portfell_readonly",
        purpose="Operational read-only role for safe inspection.",
        owns_tables=False,
        can_bypass_rls=False,
    ),
)

HOSTED_TABLES: tuple[HostedTable, ...] = (
    HostedTable("portfell_app.users", True, False, "Internal user identities."),
    HostedTable("portfell_app.provider_credentials", True, False, "Encrypted EODHD credentials."),
    HostedTable("portfell_app.projects", True, False, "User research projects."),
    HostedTable(
        "portfell_app.current_project_preferences",
        True,
        False,
        "One current-project pointer per user.",
    ),
    HostedTable("portfell_app.download_runs", True, True, "User-key-backed provider requests."),
    HostedTable(
        "portfell_app.market_objects", False, True, "Shared immutable market object catalog."
    ),
    HostedTable(
        "portfell_app.dataset_snapshots",
        True,
        True,
        "Immutable user-visible observation snapshots.",
    ),
    HostedTable(
        "portfell_app.user_grants", True, True, "User entitlements to shared observations."
    ),
    HostedTable("portfell_app.selections", True, True, "Persisted user selection definitions."),
    HostedTable("portfell_app.analysis_runs", True, True, "User-owned analysis run references."),
    HostedTable("portfell_app.research_runs", True, False, "Durable research run lifecycle."),
    HostedTable(
        "portfell_app.univariate_selections", True, True, "Persisted univariate result selections."
    ),
    *(HostedTable(*spec) for spec in D017_TABLE_SPECS),
    HostedTable(
        "portfell_app.artifacts", False, True, "Shared immutable derived artifact catalog."
    ),
    HostedTable("portfell_app.artifact_inputs", False, True, "Artifact dependency closure."),
    HostedTable(
        "portfell_app.audit_events", True, True, "User-scoped security and lifecycle audit trail."
    ),
)

AUTHENTICATED_USER_SETTING = "portfell.current_user_id"

_BASE_SCHEMA_SQL = """
create schema if not exists portfell_private;
create schema if not exists portfell_app;

create table if not exists portfell_private.schema_migrations (
    version integer primary key,
    name text not null unique,
    checksum text not null,
    applied_at timestamptz not null default now()
);

create table if not exists portfell_app.users (
    user_id uuid primary key,
    status text not null check (status in ('active', 'disabled', 'deleted')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    deleted_at timestamptz,
    check ((status = 'deleted') = (deleted_at is not null))
);

create table if not exists portfell_app.external_identities (
    identity_id uuid primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    provider text not null check (provider = 'google'),
    provider_subject text not null,
    email text,
    display_name text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (provider, provider_subject)
);

create table if not exists portfell_app.sessions (
    session_id uuid primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    session_hash text not null unique,
    csrf_hash text not null,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null,
    revoked_at timestamptz,
    check (expires_at > created_at)
);

create table if not exists portfell_app.provider_credentials (
    credential_id uuid primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    provider text not null check (provider = 'eodhd'),
    status text not null check (status in ('active', 'revoked', 'deleted')),
    ciphertext bytea not null,
    nonce bytea not null,
    wrapped_data_key bytea not null,
    key_version text not null,
    associated_data jsonb not null,
    fingerprint_hmac text not null,
    masked_label text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    revoked_at timestamptz,
    deleted_at timestamptz,
    unique (user_id, provider, status) deferrable initially immediate
);

create table if not exists portfell_app.projects (
    project_id uuid primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    name text not null,
    current_snapshot_id uuid,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, name)
);

create table if not exists portfell_app.download_runs (
    download_run_id uuid primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    credential_id uuid not null references portfell_app.provider_credentials(credential_id),
    provider text not null check (provider = 'eodhd'),
    request_hash text not null,
    status text not null check (status in ('planned', 'running', 'succeeded', 'failed')),
    requested_scope jsonb not null,
    response_manifest jsonb not null default '{}'::jsonb,
    error_summary text,
    started_at timestamptz not null default now(),
    finished_at timestamptz,
    unique (user_id, request_hash)
);

create table if not exists portfell_app.market_objects (
    market_object_id text primary key,
    provider text not null check (provider = 'eodhd'),
    dataset_type text not null,
    listing_identity text not null,
    business_key text not null,
    payload_hash text not null,
    schema_version integer not null check (schema_version > 0),
    storage_uri text not null,
    created_at timestamptz not null default now(),
    unique (provider, dataset_type, listing_identity, business_key, payload_hash, schema_version)
);

create table if not exists portfell_app.dataset_snapshots (
    snapshot_id uuid primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    project_id uuid references portfell_app.projects(project_id) on delete set null,
    parent_snapshot_id uuid references portfell_app.dataset_snapshots(snapshot_id),
    snapshot_hash text not null,
    manifest_uri text not null,
    observation_count bigint not null check (observation_count >= 0),
    created_at timestamptz not null default now(),
    unique (user_id, snapshot_hash)
);

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conname = 'projects_current_snapshot_fk'
    ) then
        alter table portfell_app.projects
            add constraint projects_current_snapshot_fk
            foreign key (current_snapshot_id)
            references portfell_app.dataset_snapshots(snapshot_id)
            deferrable initially deferred;
    end if;
end $$;

create table if not exists portfell_app.user_grants (
    grant_id uuid primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    download_run_id uuid not null references portfell_app.download_runs(download_run_id),
    market_object_id text not null references portfell_app.market_objects(market_object_id),
    snapshot_id uuid not null references portfell_app.dataset_snapshots(snapshot_id),
    revision_policy text not null,
    granted_at timestamptz not null default now(),
    unique (user_id, market_object_id, snapshot_id)
);

create table if not exists portfell_app.selections (
    selection_id uuid primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    project_id uuid references portfell_app.projects(project_id) on delete set null,
    snapshot_id uuid not null references portfell_app.dataset_snapshots(snapshot_id),
    selection_hash text not null,
    name text not null,
    predicate jsonb not null,
    membership_manifest_uri text not null,
    created_at timestamptz not null default now(),
    unique (user_id, selection_hash)
);

create table if not exists portfell_app.artifacts (
    artifact_id text primary key,
    artifact_type text not null,
    input_hash text not null,
    algorithm_version text not null,
    schema_version integer not null check (schema_version > 0),
    storage_uri text not null,
    created_at timestamptz not null default now(),
    unique (artifact_type, input_hash, algorithm_version, schema_version)
);

create table if not exists portfell_app.artifact_inputs (
    artifact_id text not null references portfell_app.artifacts(artifact_id) on delete cascade,
    input_kind text not null,
    input_ref text not null,
    input_hash text not null,
    primary key (artifact_id, input_kind, input_ref)
);

create table if not exists portfell_app.analysis_runs (
    analysis_run_id uuid primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    project_id uuid references portfell_app.projects(project_id) on delete set null,
    selection_id uuid references portfell_app.selections(selection_id),
    snapshot_id uuid not null references portfell_app.dataset_snapshots(snapshot_id),
    artifact_id text references portfell_app.artifacts(artifact_id),
    run_hash text not null,
    status text not null check (status in ('planned', 'running', 'succeeded', 'failed')),
    settings jsonb not null,
    created_at timestamptz not null default now(),
    finished_at timestamptz,
    unique (user_id, run_hash)
);

create table if not exists portfell_app.audit_events (
    audit_event_id uuid primary key,
    user_id uuid not null references portfell_app.users(user_id) on delete cascade,
    event_type text not null,
    subject_ref text not null,
    metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists external_identities_user_id_idx on portfell_app.external_identities(user_id);
create index if not exists sessions_user_id_idx on portfell_app.sessions(user_id);
create index if not exists provider_credentials_user_id_idx on portfell_app.provider_credentials(user_id);
create index if not exists projects_user_id_idx on portfell_app.projects(user_id);
create index if not exists download_runs_user_id_idx on portfell_app.download_runs(user_id);
create index if not exists dataset_snapshots_user_id_idx on portfell_app.dataset_snapshots(user_id);
create index if not exists user_grants_user_id_idx on portfell_app.user_grants(user_id);
create index if not exists selections_user_id_idx on portfell_app.selections(user_id);
create index if not exists analysis_runs_user_id_idx on portfell_app.analysis_runs(user_id);
create index if not exists audit_events_user_id_idx on portfell_app.audit_events(user_id);
create index if not exists artifact_inputs_input_idx on portfell_app.artifact_inputs(input_kind, input_ref);

alter table portfell_app.users enable row level security;
alter table portfell_app.external_identities enable row level security;
alter table portfell_app.sessions enable row level security;
alter table portfell_app.provider_credentials enable row level security;
alter table portfell_app.projects enable row level security;
alter table portfell_app.download_runs enable row level security;
alter table portfell_app.dataset_snapshots enable row level security;
alter table portfell_app.user_grants enable row level security;
alter table portfell_app.selections enable row level security;
alter table portfell_app.analysis_runs enable row level security;
alter table portfell_app.audit_events enable row level security;

alter table portfell_app.users force row level security;
alter table portfell_app.external_identities force row level security;
alter table portfell_app.sessions force row level security;
alter table portfell_app.provider_credentials force row level security;
alter table portfell_app.projects force row level security;
alter table portfell_app.download_runs force row level security;
alter table portfell_app.dataset_snapshots force row level security;
alter table portfell_app.user_grants force row level security;
alter table portfell_app.selections force row level security;
alter table portfell_app.analysis_runs force row level security;
alter table portfell_app.audit_events force row level security;
"""

_RLS_POLICY_SQL = """
do $$
declare
    table_name text;
begin
    foreach table_name in array array[
        'users',
        'external_identities',
        'sessions',
        'provider_credentials',
        'projects',
        'download_runs',
        'dataset_snapshots',
        'user_grants',
        'selections',
        'analysis_runs',
        'audit_events'
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

revoke all on schema portfell_app from public;
revoke all on schema portfell_private from public;
grant usage on schema portfell_app to portfell_app, portfell_readonly;
grant select, insert, update on all tables in schema portfell_app to portfell_app;
grant select on all tables in schema portfell_app to portfell_readonly;
revoke delete on all tables in schema portfell_app from portfell_app;
revoke all on all tables in schema portfell_private from portfell_app, portfell_readonly;
"""

_REMOVE_GOOGLE_AUTH_SQL = """
drop table if exists portfell_app.sessions;
drop table if exists portfell_app.external_identities;
"""

_CURRENT_PROJECT_PREFERENCE_SQL = """
create table if not exists portfell_app.current_project_preferences (
    user_id uuid primary key references portfell_app.users(user_id) on delete cascade,
    project_id uuid references portfell_app.projects(project_id) on delete set null,
    updated_at timestamptz not null default now()
);

alter table portfell_app.current_project_preferences enable row level security;
alter table portfell_app.current_project_preferences force row level security;
drop policy if exists user_isolation on portfell_app.current_project_preferences;
create policy user_isolation on portfell_app.current_project_preferences
    using (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid)
    with check (user_id = nullif(current_setting('portfell.current_user_id', true), '')::uuid);
grant select, insert, update on portfell_app.current_project_preferences to portfell_app;
grant select on portfell_app.current_project_preferences to portfell_readonly;
"""

_CREDENTIAL_WRAP_NONCE_SQL = """
alter table portfell_app.provider_credentials
    add column if not exists wrap_nonce bytea;

do $$
begin
    if exists (
        select 1
        from portfell_app.provider_credentials
        where wrap_nonce is null
    ) then
        raise exception 'provider credential rows require a wrap nonce migration';
    end if;
end $$;

alter table portfell_app.provider_credentials
    alter column wrap_nonce set not null;

alter table portfell_app.provider_credentials
    drop constraint if exists provider_credentials_user_id_provider_status_key;

create unique index if not exists provider_credentials_one_active_user_provider_idx
    on portfell_app.provider_credentials (user_id, provider)
    where status = 'active';
"""

MIGRATIONS: tuple[HostedMigration, ...] = (
    HostedMigration(1, "hosted_catalog_base_schema", _BASE_SCHEMA_SQL),
    HostedMigration(2, "hosted_catalog_rls_and_grants", _RLS_POLICY_SQL),
    HostedMigration(3, "remove_google_authentication", _REMOVE_GOOGLE_AUTH_SQL),
    HostedMigration(4, "current_project_preference", _CURRENT_PROJECT_PREFERENCE_SQL),
    HostedMigration(5, "provider_credential_wrap_nonce", _CREDENTIAL_WRAP_NONCE_SQL),
    HostedMigration(6, "d017_tenant_control_schema", D017_TENANT_CONTROL_SCHEMA_SQL),
    HostedMigration(7, "d017_durable_job_queue", D017_DURABLE_JOB_SCHEMA_SQL),
    HostedMigration(8, "legacy_import_ledger", LEGACY_IMPORT_LEDGER_SQL),
    HostedMigration(9, "download_run_partial_status", DOWNLOAD_RUN_PARTIAL_STATUS_SQL),
    HostedMigration(10, "durable_metadata_lifecycle", METADATA_LIFECYCLE_SCHEMA_SQL),
    HostedMigration(11, "durable_research_lifecycle", RESEARCH_LIFECYCLE_SCHEMA_SQL),
    HostedMigration(12, "durable_project_settings", PROJECT_SETTINGS_SCHEMA_SQL),
)


def create_role_sql(role: HostedRole) -> str:
    """Return idempotent SQL for one hosted database role.

    Args:
        role: Hosted role contract to materialize.

    Returns:
        PostgreSQL DO block that creates the role without BYPASSRLS.
    """

    bypass_rls = "bypassrls" if role.can_bypass_rls else "nobypassrls"
    return f"""
do $$
begin
    if not exists (select 1 from pg_roles where rolname = '{role.name}') then
        create role {role.name} noinherit nologin {bypass_rls};
    end if;
end $$;
"""


def migration_plan() -> tuple[HostedMigration, ...]:
    return MIGRATIONS


def set_authenticated_user_sql(user_id: str) -> tuple[str, tuple[object, ...]]:
    """Return SQL that binds a transaction-local authenticated user id.

    Args:
        user_id: Authenticated internal Portfell user id.

    Returns:
        SQL and parameters suitable for a database driver's execute method.
    """

    return "select set_config(%s, %s, true)", (AUTHENTICATED_USER_SETTING, user_id)


def apply_hosted_catalog_migrations(connection: CatalogConnection) -> int:
    """Apply the hosted catalog role and schema migrations.

    Args:
        connection: Database connection implementing the minimal execution protocol.

    Side Effects:
        Executes deterministic idempotent role creation and schema migration SQL.

    Returns: Number of newly applied catalog migrations.
    """

    for role in HOSTED_ROLES:
        connection.execute(create_role_sql(role))
    applied = 0
    for migration in migration_plan():
        if migration.version == 1:
            connection.execute(migration.sql)
        existing = connection.execute(
            """
select checksum
from portfell_private.schema_migrations
where version = %s
""",
            (migration.version,),
        ).fetchone()
        if existing is not None:
            if existing[0] != migration.checksum:
                raise ValueError(f"hosted_migration_checksum_mismatch:{migration.version}")
            continue
        if migration.version != 1:
            connection.execute(migration.sql)
        connection.execute(
            """
insert into portfell_private.schema_migrations (version, name, checksum)
values (%s, %s, %s)
""",
            (migration.version, migration.name, migration.checksum),
        )
        applied += 1
    return applied


def validate_hosted_catalog_contracts() -> None:
    """Validate static hosted catalog invariants.

    Raises:
        ValueError: If a role, table, or migration contract violates hosted security rules.
    """

    if any(role.can_bypass_rls for role in HOSTED_ROLES):
        raise ValueError("hosted roles must not bypass RLS")
    runtime_roles = {"portfell_app", "portfell_worker", "portfell_readonly"}
    if any(role.owns_tables for role in HOSTED_ROLES if role.name in runtime_roles):
        raise ValueError("runtime roles must not own tables")
    versions = [migration.version for migration in MIGRATIONS]
    if versions != sorted(set(versions)):
        raise ValueError("migration versions must be unique and ordered")
    user_scoped = [table for table in HOSTED_TABLES if table.user_scoped]
    if not user_scoped:
        raise ValueError("at least one user-scoped table is required")
    sql = "\n".join(migration.sql.lower() for migration in MIGRATIONS)
    for forbidden in ("plaintext", "api_token", "eodhd_token", "bypassrls"):
        if forbidden in sql:
            raise ValueError(f"forbidden hosted catalog token present: {forbidden}")
