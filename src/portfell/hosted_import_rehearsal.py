"""Fail-closed operator rehearsal for importing local control-plane metadata."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from portfell.hosted_catalog import migration_plan
from portfell.hosted_database_connection import connect as connect_database
from portfell.hosted_repository_importer import (
    ImportReport,
    InMemoryTenantRepository,
    ParityMismatch,
    PostgresTenantProjectionRepository,
    PostgresTenantRepository,
    TenantImportConnection,
    TenantProject,
    compare_project_parity,
    expected_postgres_projects,
    import_local_workspace,
)
from portfell.hosted_workspace import LocalWorkspaceStore


class HostedImportRehearsalError(RuntimeError):
    """Raised when an import rehearsal cannot safely produce evidence."""


class ImportRehearsalConnection(TenantImportConnection, Protocol):
    """Owned PostgreSQL connection required by the operator command."""

    def close(self) -> None:
        """Close the connection after the rehearsal completes."""


ImportRehearsalConnector = Callable[[str], ImportRehearsalConnection]


@dataclass(frozen=True)
class ImportRehearsalReport:
    """Redacted result of one dry-run or applied import rehearsal."""

    import_report: ImportReport
    parity_mismatches: tuple[ParityMismatch, ...]


def _connect(database_url: str) -> ImportRehearsalConnection:
    return cast(ImportRehearsalConnection, connect_database(database_url, autocommit=False))


def rehearse_import(
    workspace_path: Path,
    *,
    apply: bool,
    database_url: str | None = None,
    connect: ImportRehearsalConnector | None = None,
) -> ImportRehearsalReport:
    """Plan or apply one validated control-plane import with count-only parity evidence."""

    if not workspace_path.is_file():
        raise HostedImportRehearsalError("workspace_file_required")
    try:
        payload = LocalWorkspaceStore(workspace_path).load()
        report = import_local_workspace(InMemoryTenantRepository(), payload, dry_run=True)
    except (OSError, ValueError) as error:
        raise HostedImportRehearsalError("workspace_import_invalid") from error
    if not apply:
        return ImportRehearsalReport(report, ())
    resolved_url = database_url or os.environ.get("PORTFELL_DATABASE_URL")
    if not resolved_url:
        raise HostedImportRehearsalError("database_url_required")
    connection = (connect or _connect)(resolved_url)
    try:
        _require_current_catalog(connection)
        report = import_local_workspace(
            PostgresTenantRepository(connection), payload, dry_run=False
        )
        mismatches = _project_parity_mismatches(connection, payload)
    finally:
        connection.close()
    return ImportRehearsalReport(report, mismatches)


def _require_current_catalog(connection: ImportRehearsalConnection) -> None:
    rows = connection.execute(
        "select version from portfell_private.schema_migrations order by version"
    ).fetchall()
    expected = tuple(migration.version for migration in migration_plan())
    if tuple(row[0] for row in rows) != expected:
        raise HostedImportRehearsalError("catalog_not_current")


def _project_parity_mismatches(
    connection: ImportRehearsalConnection,
    payload: dict[str, object],
) -> tuple[ParityMismatch, ...]:
    expected = expected_postgres_projects(payload)
    projections = PostgresTenantProjectionRepository(connection)
    actual: list[TenantProject] = []
    for user_id in sorted({project.user_id for project in expected}):
        actual.extend(projections.projects_for_user(user_id))
    return compare_project_parity(expected, tuple(sorted(actual)))


def build_parser() -> argparse.ArgumentParser:
    """Build the import rehearsal CLI parser."""

    parser = argparse.ArgumentParser(description="Rehearse a local control-plane import.")
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a dry-run by default; import only with explicit operator opt-in."""

    args = build_parser().parse_args(argv)
    try:
        result = rehearse_import(args.workspace, apply=args.apply)
    except HostedImportRehearsalError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print("hosted_import_rehearsal_failed", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "checksum": result.import_report.checksum,
                "dry_run": result.import_report.dry_run,
                "membership_count": result.import_report.membership_count,
                "parity_mismatch_count": len(result.parity_mismatches),
                "project_count": result.import_report.project_count,
                "selection_count": result.import_report.selection_count,
            },
            sort_keys=True,
        )
    )
    return 0 if not result.parity_mismatches else 1


if __name__ == "__main__":
    raise SystemExit(main())
