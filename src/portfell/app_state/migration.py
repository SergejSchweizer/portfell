"""Deterministic migration runner for the clean ``portfell_dash`` database."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from typing import Protocol, cast

from portfell.app_state.migrations import (
    MIGRATION_V001,
    MIGRATION_V002,
    MIGRATION_V003,
    MIGRATION_V004,
    MIGRATION_V005,
)
from portfell.app_state.migrations.v001_initial import AppStateMigration
from portfell.app_state.schema import APP_STATE_TABLES

APP_STATE_MIGRATIONS: tuple[AppStateMigration, ...] = (
    MIGRATION_V001,
    MIGRATION_V002,
    MIGRATION_V003,
    MIGRATION_V004,
    MIGRATION_V005,
)
_ROLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_BOOTSTRAP_SQL = """
create schema if not exists portfell;
create table if not exists portfell.schema_migrations (
    version integer primary key check (version > 0),
    name text not null unique check (btrim(name) <> ''),
    checksum text not null check (btrim(checksum) <> ''),
    applied_at timestamptz not null default now()
);
""".strip()


class MigrationCursor(Protocol):
    def fetchall(self) -> list[Sequence[object]]: ...


class MigrationConnection(Protocol):
    def execute(self, query: str, params: Sequence[object] | None = None) -> MigrationCursor: ...

    def commit(self) -> None: ...

    def rollback(self) -> None: ...


class AppStateMigrationError(RuntimeError):
    """Typed migration failure without connection or credential detail."""


def catalog_fingerprint() -> str:
    """Return a stable fingerprint for the frozen migration head and table contract."""

    material = "\n".join(
        [
            *(
                f"{migration.version}:{migration.name}:{migration.checksum}"
                for migration in APP_STATE_MIGRATIONS
            ),
            *APP_STATE_TABLES,
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _applied(connection: MigrationConnection) -> dict[int, tuple[str, str]]:
    rows = connection.execute(
        "select version, name, checksum from portfell.schema_migrations order by version"
    ).fetchall()
    result: dict[int, tuple[str, str]] = {}
    for row in rows:
        version, name, checksum = row
        result[int(cast(int, version))] = (str(name), str(checksum))
    return result


def migrate_to_head(connection: MigrationConnection) -> tuple[int, ...]:
    """Apply every unapplied migration transactionally and verify recorded checksums."""

    applied_now: list[int] = []
    try:
        connection.execute(_BOOTSTRAP_SQL)
        existing = _applied(connection)
        for migration in APP_STATE_MIGRATIONS:
            recorded = existing.get(migration.version)
            if recorded is not None:
                if recorded != (migration.name, migration.checksum):
                    raise AppStateMigrationError("app_state_migration_checksum_mismatch")
                continue
            connection.execute(migration.sql)
            connection.execute(
                (
                    "insert into portfell.schema_migrations (version, name, checksum) "
                    "values (%s, %s, %s)"
                ),
                (migration.version, migration.name, migration.checksum),
            )
            applied_now.append(migration.version)
        connection.commit()
    except Exception as error:
        connection.rollback()
        if isinstance(error, AppStateMigrationError):
            raise
        raise AppStateMigrationError("app_state_migration_failed") from error
    return tuple(applied_now)


def rollback_to_zero(
    connection: MigrationConnection, *, allow_destructive: bool = False
) -> tuple[int, ...]:
    """Roll back one migration step when explicitly authorized."""

    if not allow_destructive:
        raise AppStateMigrationError("app_state_destructive_rollback_required")
    try:
        connection.execute(_BOOTSTRAP_SQL)
        existing = _applied(connection)
        rolled_back: list[int] = []
        for migration in reversed(APP_STATE_MIGRATIONS):
            if migration.version not in existing:
                continue
            connection.execute(migration.destructive_down_sql)
            connection.execute(
                "delete from portfell.schema_migrations where version = %s",
                (migration.version,),
            )
            rolled_back.append(migration.version)
            break
        connection.commit()
    except Exception as error:
        connection.rollback()
        if isinstance(error, AppStateMigrationError):
            raise
        raise AppStateMigrationError("app_state_rollback_failed") from error
    return tuple(rolled_back)


def grant_runtime_privileges(connection: MigrationConnection, role: str) -> None:
    """Grant only runtime DML privileges to the configured non-superuser login role."""

    if not _ROLE.fullmatch(role):
        raise AppStateMigrationError("app_state_role_invalid")
    quoted = f'"{role}"'
    statements = (
        f"grant connect on database portfell_dash to {quoted}",
        f"grant usage on schema portfell to {quoted}",
        f"grant select, insert, update on all tables in schema portfell to {quoted}",
    )
    try:
        for statement in statements:
            connection.execute(statement)
        connection.commit()
    except Exception as error:
        connection.rollback()
        raise AppStateMigrationError("app_state_privilege_grant_failed") from error
