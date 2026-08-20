from __future__ import annotations

import json

from portfell import multivariate_decision_migration as migration
from portfell.multivariate_decision_schema import (
    MULTIVARIATE_DECISION_SCHEMA_NAME,
    MULTIVARIATE_DECISION_SCHEMA_SQL,
    MULTIVARIATE_DECISION_SCHEMA_VERSION,
    apply_multivariate_decision_schema,
)


class _Result:
    def fetchone(self):
        return None


class _Connection:
    def __init__(self) -> None:
        self.statements: list[tuple[str, tuple[object, ...]]] = []
        self.closed = False

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Result:
        self.statements.append((sql, parameters))
        return _Result()

    def close(self) -> None:
        self.closed = True


def test_pr273_schema_contract_is_versioned_rls_scoped_and_complete() -> None:
    assert MULTIVARIATE_DECISION_SCHEMA_VERSION == 25
    assert MULTIVARIATE_DECISION_SCHEMA_NAME == "multivariate_decision_history_evidence"
    for table in (
        "portfell_app.multivariate_decisions",
        "portfell_app.research_universe_snapshots",
        "portfell_app.multivariate_current_selections",
    ):
        assert f"create table if not exists {table}" in MULTIVARIATE_DECISION_SCHEMA_SQL
        assert f"alter table {table} enable row level security" in MULTIVARIATE_DECISION_SCHEMA_SQL
        assert f"alter table {table} force row level security" in MULTIVARIATE_DECISION_SCHEMA_SQL


def test_pr273_schema_application_is_one_idempotent_sql_batch() -> None:
    connection = _Connection()
    apply_multivariate_decision_schema(connection)
    assert connection.statements == [(MULTIVARIATE_DECISION_SCHEMA_SQL, ())]


def test_pr273_runtime_migration_closes_connection_and_reports_ready(
    monkeypatch, capsys
) -> None:
    connection = _Connection()
    monkeypatch.setenv("PORTFELL_DATABASE_URL", "postgresql://example/portfell")
    monkeypatch.setattr(migration, "connect_database", lambda *_args, **_kwargs: connection)

    assert migration.main() == 0
    assert connection.closed is True
    assert json.loads(capsys.readouterr().out) == {"multivariate_decision_schema": "ready"}
