from __future__ import annotations

import pytest

import portfell.hosted_catalog_migration as catalog_migration
from portfell.hosted_catalog import migration_plan
from portfell.hosted_catalog_migration import HostedCatalogMigrationError, apply_runtime_migrations


class FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple[object, ...]]] = []
        self.closed = False

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> object:
        self.executed.append((sql, parameters))
        return None

    def close(self) -> None:
        self.closed = True


def test_runtime_migrations_require_an_explicit_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PORTFELL_DATABASE_URL", raising=False)

    with pytest.raises(HostedCatalogMigrationError, match="database_url_required"):
        apply_runtime_migrations()


def test_runtime_migrations_apply_the_catalog_plan_and_close_connection() -> None:
    connection = FakeConnection()
    received_urls: list[str] = []

    def connect(database_url: str) -> FakeConnection:
        received_urls.append(database_url)
        return connection

    applied = apply_runtime_migrations(
        "postgresql://migration-user@database/portfell", connect=connect
    )

    assert applied == len(migration_plan())
    assert received_urls == ["postgresql://migration-user@database/portfell"]
    assert connection.closed
    assert connection.executed


def test_runtime_migration_cli_redacts_connection_failures(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("PORTFELL_DATABASE_URL", "postgresql://user:secret@database/portfell")

    def fail_connect(_: str) -> FakeConnection:
        raise RuntimeError("connection failed for postgresql://user:secret@database/portfell")

    monkeypatch.setattr(catalog_migration, "_connect", fail_connect)

    assert catalog_migration.main([]) == 1
    captured = capsys.readouterr()

    assert captured.err == "catalog_migration_failed\n"
    assert "secret" not in captured.err


def test_runtime_migration_cli_reports_applied_count(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    connection = FakeConnection()
    monkeypatch.setenv("PORTFELL_DATABASE_URL", "postgresql://migration-user@database/portfell")
    monkeypatch.setattr(catalog_migration, "_connect", lambda _: connection)

    assert catalog_migration.main([]) == 0

    assert capsys.readouterr().out == f'{{"migrations_applied": {len(migration_plan())}}}\n'
    assert connection.closed
