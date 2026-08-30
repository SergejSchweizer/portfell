"""Read-only catalog probes for the clean Portfell application database."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class AppStateReadCursor(Protocol):
    def fetchall(self) -> list[Sequence[object]]: ...


class AppStateReadConnection(Protocol):
    def execute(
        self, query: str, params: Sequence[object] | None = None
    ) -> AppStateReadCursor: ...


def read_applied_migration_versions(connection: AppStateReadConnection) -> tuple[int, ...]:
    """Return applied app-state migration versions in deterministic order."""

    rows = connection.execute(
        "select version from portfell.schema_migrations order by version"
    ).fetchall()
    return tuple(int(row[0]) for row in rows)


__all__ = ["AppStateReadConnection", "AppStateReadCursor", "read_applied_migration_versions"]
