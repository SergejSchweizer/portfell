from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import cast

import pytest

from portfell.app_state import (
    ANALYSIS_STAGES,
    APP_DATABASE_NAME,
    APP_SCHEMA_NAME,
    APP_STATE_TABLES,
    MULTIVARIATE_OBJECTIVES,
    catalog_fingerprint,
    migrate_to_head,
    rollback_to_zero,
    validate_app_state_config,
)
from portfell.app_state.migration import AppStateMigrationError, grant_runtime_privileges
from portfell.app_state.migrations import MIGRATION_V001
from portfell.app_state.schema import V1_SCHEMA_SQL
from portfell.market_source.errors import MarketSourceError


class FakeCursor:
    def __init__(self, rows: list[Sequence[object]] | None = None) -> None:
        self._rows = rows or []

    def fetchall(self) -> list[Sequence[object]]:
        return list(self._rows)


class FakeConnection:
    def __init__(self) -> None:
        self.applied: dict[int, tuple[str, str]] = {}
        self.executed: list[tuple[str, Sequence[object] | None]] = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, query: str, params: Sequence[object] | None = None) -> FakeCursor:
        self.executed.append((query, params))
        if query.startswith("select version, name, checksum"):
            rows: list[Sequence[object]] = [
                (version, name, checksum)
                for version, (name, checksum) in sorted(self.applied.items())
            ]
            return FakeCursor(rows)
        if query.startswith("insert into portfell.schema_migrations"):
            assert params is not None
            version, name, checksum = params
            self.applied[int(cast(int, version))] = (str(name), str(checksum))
        if query.startswith("delete from portfell.schema_migrations"):
            assert params is not None
            self.applied.pop(int(cast(int, params[0])), None)
        if query == "drop schema if exists portfell cascade;":
            self.applied.clear()
        return FakeCursor()

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_catalog_is_clean_single_workspace_contract() -> None:
    assert APP_DATABASE_NAME == "portfell_dash"
    assert APP_SCHEMA_NAME == "portfell"
    assert APP_STATE_TABLES == (
        "schema_migrations",
        "workspaces",
        "market_source_snapshots",
        "metadata_universes",
        "metadata_universe_members",
        "analysis_runs",
        "analysis_artifacts",
        "analysis_artifact_items",
        "analysis_jobs",
        "univariate_selections",
        "univariate_selection_members",
        "decision_artifacts",
        "ui_preferences",
    )
    assert ANALYSIS_STAGES == ("metadata", "univariate", "bivariate", "multivariate")
    assert MULTIVARIATE_OBJECTIVES == ("return_risk", "return_drawdown", "minimum_risk")
    assert "workspace_id = 'default'" in V1_SCHEMA_SQL
    assert "isin text not null" in V1_SCHEMA_SQL
    assert "exchange text not null" in V1_SCHEMA_SQL
    assert "code text not null" in V1_SCHEMA_SQL
    for forbidden in (
        "portfell_app.",
        "portfell_private.",
        "user_id",
        "project_id",
        "provider_credential",
        "navigation_projection",
        "xetra_loader",
    ):
        assert forbidden not in V1_SCHEMA_SQL


def test_migration_is_repeat_safe_and_checksum_locked() -> None:
    connection = FakeConnection()
    assert migrate_to_head(connection) == (1, 2, 3, 4, 5, 6)
    assert connection.applied[1] == (MIGRATION_V001.name, MIGRATION_V001.checksum)
    assert tuple(connection.applied) == (1, 2, 3, 4, 5, 6)
    assert migrate_to_head(connection) == ()
    assert connection.commits == 2
    assert connection.rollbacks == 0

    connection.applied[1] = (MIGRATION_V001.name, "different")
    with pytest.raises(AppStateMigrationError, match="checksum_mismatch"):
        migrate_to_head(connection)
    assert connection.rollbacks == 1


def test_destructive_rollback_requires_explicit_operator_opt_in() -> None:
    connection = FakeConnection()
    migrate_to_head(connection)
    with pytest.raises(AppStateMigrationError, match="destructive_rollback_required"):
        rollback_to_zero(connection)
    assert rollback_to_zero(connection, allow_destructive=True) == (6,)
    assert tuple(connection.applied) == (1, 2, 3, 4, 5)


def test_runtime_privileges_are_bounded_and_role_name_is_validated() -> None:
    connection = FakeConnection()
    grant_runtime_privileges(connection, "portfell_app")
    sql = "\n".join(query for query, _ in connection.executed)
    assert "grant connect on database portfell_dash" in sql
    assert "grant usage on schema portfell" in sql
    assert "grant select, insert, update on all tables in schema portfell" in sql
    assert "superuser" not in sql.casefold()
    assert "delete" not in sql.casefold()
    with pytest.raises(AppStateMigrationError, match="role_invalid"):
        grant_runtime_privileges(connection, 'portfell_app"; drop schema portfell; --')


def test_catalog_fingerprint_is_stable_sha256() -> None:
    first = catalog_fingerprint()
    second = catalog_fingerprint()
    assert first == second
    assert len(first) == 64
    assert all(character in "0123456789abcdef" for character in first)


def test_app_database_config_requires_portfell_dash_and_matching_dsn(tmp_path: Path) -> None:
    config = tmp_path / "config.yaml"
    config.write_text(
        """postgres:
  app:
    host: app-db
    port: 5432
    database: portfell_dash
    schema: portfell
    role: portfell_app
    password_secret: PORTFELL_DATABASE_PASSWORD_FILE
""",
        encoding="utf-8",
    )
    loaded, dsn = validate_app_state_config(
        config, database_url="postgresql://portfell_app@app-db:5432/portfell_dash"
    )
    assert loaded.database == "portfell_dash"
    assert loaded.schema == "portfell"
    assert dsn.endswith("/portfell_dash")

    config.write_text(
        config.read_text(encoding="utf-8").replace("portfell_dash", "portfell"),
        encoding="utf-8",
    )
    with pytest.raises(MarketSourceError):
        validate_app_state_config(
            config, database_url="postgresql://portfell_app@app-db:5432/portfell"
        )
