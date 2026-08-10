from __future__ import annotations

from portfell.hosted_catalog import (
    HOSTED_ROLES,
    HOSTED_TABLES,
    apply_hosted_catalog_migrations,
    migration_plan,
    set_authenticated_user_sql,
    validate_hosted_catalog_contracts,
)


class FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> object:
        self.executed.append((sql, parameters))
        return None


def test_hosted_catalog_contracts_validate_security_invariants() -> None:
    validate_hosted_catalog_contracts()

    roles_by_name = {role.name: role for role in HOSTED_ROLES}
    assert set(roles_by_name) == {
        "portfell_owner",
        "portfell_migrator",
        "portfell_app",
        "portfell_worker",
        "portfell_readonly",
    }
    assert not roles_by_name["portfell_app"].owns_tables
    assert all(not role.can_bypass_rls for role in HOSTED_ROLES)

    table_names = {table.name for table in HOSTED_TABLES}
    for required_table in (
        "portfell_app.users",
        "portfell_app.provider_credentials",
        "portfell_app.projects",
        "portfell_app.current_project_preferences",
        "portfell_app.download_runs",
        "portfell_app.market_objects",
        "portfell_app.dataset_snapshots",
        "portfell_app.user_grants",
        "portfell_app.selections",
        "portfell_app.analysis_runs",
        "portfell_app.artifacts",
        "portfell_app.artifact_inputs",
        "portfell_app.audit_events",
        "portfell_app.project_selection_versions",
        "portfell_app.project_selection_members",
        "portfell_app.project_artifact_refs",
    ):
        assert required_table in table_names


def test_hosted_migration_sql_defines_rls_and_immutable_catalog_shape() -> None:
    migrations = migration_plan()
    sql = "\n".join(migration.sql.lower() for migration in migrations)

    assert [migration.version for migration in migrations] == [1, 2, 3, 4, 5, 6]
    assert len({migration.checksum for migration in migrations}) == len(migrations)
    assert "create table if not exists portfell_app.provider_credentials" in sql
    assert "ciphertext bytea not null" in sql
    assert "wrapped_data_key bytea not null" in sql
    assert "wrap_nonce bytea" in sql
    assert "provider_credentials_one_active_user_provider_idx" in sql
    assert "key_version text not null" in sql
    assert "create table if not exists portfell_app.market_objects" in sql
    assert "create table if not exists portfell_app.artifact_inputs" in sql
    assert "enable row level security" in sql
    assert "force row level security" in sql
    assert "portfell.current_user_id" in sql
    assert "revoke delete on all tables in schema portfell_app from portfell_app" in sql
    assert "drop table if exists portfell_app.sessions" in sql
    assert "drop table if exists portfell_app.external_identities" in sql
    assert "create table if not exists portfell_app.current_project_preferences" in sql
    assert "add column if not exists status text not null default 'active'" in sql
    assert "add column if not exists purpose text not null default 'user_metadata'" in sql
    assert "provider_credentials_one_active_user_provider_purpose_idx" in sql
    assert "create table if not exists portfell_app.project_selection_versions" in sql
    assert "create table if not exists portfell_app.project_selection_members" in sql
    assert "create table if not exists portfell_app.project_artifact_refs" in sql
    assert "references portfell_app.projects(project_id, user_id)" in sql
    assert "membership_sealed_at timestamptz" in sql
    assert "before insert or update or delete on portfell_app.project_selection_members" in sql
    assert "project_membership_immutable" in sql
    assert "force row level security" in sql
    assert "portfell_worker" in sql


def test_apply_hosted_catalog_migrations_is_deterministic_and_idempotent() -> None:
    connection = FakeConnection()

    apply_hosted_catalog_migrations(connection)

    role_statements = [
        statement for statement, _ in connection.executed if "create role" in statement
    ]
    migration_inserts = [
        parameters
        for statement, parameters in connection.executed
        if "insert into portfell_private.schema_migrations" in statement
    ]
    assert len(role_statements) == len(HOSTED_ROLES)
    assert len(migration_inserts) == len(migration_plan())
    assert migration_inserts == [
        (migration.version, migration.name, migration.checksum) for migration in migration_plan()
    ]


def test_authenticated_user_sql_uses_transaction_local_setting() -> None:
    sql, parameters = set_authenticated_user_sql("00000000-0000-0000-0000-000000000001")

    assert sql == "select set_config(%s, %s, true)"
    assert parameters == (
        "portfell.current_user_id",
        "00000000-0000-0000-0000-000000000001",
    )
