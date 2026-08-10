from __future__ import annotations

import json
from contextlib import nullcontext
from pathlib import Path

import pytest

from portfell.hosted_catalog import migration_plan
from portfell.hosted_import_rehearsal import (
    HostedImportRehearsalError,
    rehearse_import,
)


class _Cursor:
    def __init__(self, rows: list[tuple[object, ...]] | None = None) -> None:
        self.rows = rows or []

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows

    def fetchone(self) -> tuple[object, ...] | None:
        return ("checksum",)


class _Connection:
    def __init__(self, *, current_catalog: bool = True) -> None:
        self.current_catalog = current_catalog
        self.closed = False
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def transaction(self):  # type: ignore[no-untyped-def]
        return nullcontext()

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        self.calls.append((sql, parameters))
        if "schema_migrations" in sql:
            versions = (
                [migration.version for migration in migration_plan()]
                if self.current_catalog
                else [1]
            )
            return _Cursor([(version,) for version in versions])
        if "from portfell_app.projects" in sql:
            return _Cursor(
                [
                    (
                        "4ab6ea58-4c7e-5ca5-8236-fb0ed0cde6d8",
                        "51f92c4f-5544-536b-b81d-8014f9ef4178",
                        "Income",
                    )
                ]
            )
        return _Cursor()

    def close(self) -> None:
        self.closed = True


def _workspace(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "projects": [{"project_id": "project-1", "user_id": "user-a", "name": "Income"}],
                "selections": [],
                "current_project_id_by_user": {},
            }
        ),
        encoding="utf-8",
    )


def test_dry_run_validates_workspace_without_connecting(tmp_path: Path) -> None:
    workspace = tmp_path / "local-workspace.json"
    _workspace(workspace)

    result = rehearse_import(
        workspace,
        apply=False,
        connect=lambda _: (_ for _ in ()).throw(AssertionError("connected")),
    )

    assert result.import_report.dry_run
    assert result.import_report.project_count == 1
    assert result.parity_mismatches == ()


def test_apply_requires_current_catalog_and_closes_connection(tmp_path: Path) -> None:
    workspace = tmp_path / "local-workspace.json"
    _workspace(workspace)
    connection = _Connection(current_catalog=False)

    with pytest.raises(HostedImportRehearsalError, match="catalog_not_current"):
        rehearse_import(
            workspace,
            apply=True,
            database_url="postgresql://operator@database/portfell",
            connect=lambda _: connection,
        )

    assert connection.closed


def test_apply_imports_then_returns_redacted_parity_result(tmp_path: Path) -> None:
    workspace = tmp_path / "local-workspace.json"
    _workspace(workspace)
    connection = _Connection()

    result = rehearse_import(
        workspace,
        apply=True,
        database_url="postgresql://operator@database/portfell",
        connect=lambda _: connection,
    )

    assert result.import_report.dry_run is False
    assert len(result.parity_mismatches) == 1
    assert result.parity_mismatches[0].field == "projects"
    assert connection.closed
