"""Fail-closed hosted PostgreSQL catalog migration entry point."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from typing import Protocol, cast

from portfell.hosted_catalog import apply_hosted_catalog_migrations, migration_plan
from portfell.hosted_database_connection import connect as connect_database


class HostedCatalogMigrationError(RuntimeError):
    """Raised when a hosted catalog migration cannot run safely."""


class MigrationConnection(Protocol):
    """Minimal owned connection boundary for catalog migration execution."""

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> object:
        """Execute one migration statement."""

    def close(self) -> None:
        """Close the database connection."""


MigrationConnector = Callable[[str], MigrationConnection]


def _connect(database_url: str) -> MigrationConnection:
    return cast(MigrationConnection, connect_database(database_url, autocommit=True))


def apply_runtime_migrations(
    database_url: str | None = None,
    *,
    connect: MigrationConnector | None = None,
) -> int:
    """Apply the catalog plan through an explicit external database URL."""

    resolved_url = database_url or os.environ.get("PORTFELL_DATABASE_URL")
    if not resolved_url:
        raise HostedCatalogMigrationError("database_url_required")
    connection = (connect or _connect)(resolved_url)
    try:
        apply_hosted_catalog_migrations(connection)
    finally:
        connection.close()
    return len(migration_plan())


def build_parser() -> argparse.ArgumentParser:
    """Build the hosted catalog migration parser."""

    return argparse.ArgumentParser(description="Apply Portfell hosted catalog migrations.")


def main(argv: Sequence[str] | None = None) -> int:
    """Apply catalog migrations without disclosing connection configuration."""

    build_parser().parse_args(argv)
    try:
        migrations_applied = apply_runtime_migrations()
    except HostedCatalogMigrationError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print("catalog_migration_failed", file=sys.stderr)
        return 1
    print(json.dumps({"migrations_applied": migrations_applied}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
