from __future__ import annotations

from pathlib import Path

import pytest

from portfell.hosted_database_connection import (
    HostedDatabaseConnectionError,
    database_password,
)


def test_database_password_is_optional_when_no_file_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PORTFELL_DATABASE_PASSWORD_FILE", raising=False)

    assert database_password() is None


def test_database_password_reads_a_nonempty_external_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    password_file = tmp_path / "postgres-password"
    password_file.write_text("database-password\n", encoding="utf-8")
    monkeypatch.setenv("PORTFELL_DATABASE_PASSWORD_FILE", str(password_file))

    assert database_password() == "database-password"


def test_database_password_redacts_missing_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PORTFELL_DATABASE_PASSWORD_FILE", str(tmp_path / "missing-password"))

    with pytest.raises(HostedDatabaseConnectionError, match="database_password_file_unavailable"):
        database_password()
