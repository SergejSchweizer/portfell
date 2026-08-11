"""Worker-only PostgreSQL reader for the active shared-market inventory."""

from __future__ import annotations

from typing import Protocol

from portfell.shared_market_data import SharedListingKey


class ActiveInventoryCursor(Protocol):
    def fetchall(self) -> list[tuple[object, ...]]: ...


class ActiveInventoryConnection(Protocol):
    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> ActiveInventoryCursor: ...


class PostgresActiveProjectInventory:
    """Read the de-duplicated full-key union through the worker-only connection."""

    def __init__(self, connection: ActiveInventoryConnection) -> None:
        self._connection = connection

    def listings(self) -> tuple[SharedListingKey, ...]:
        rows = self._connection.execute(
            """
select distinct member.provider, member.exchange, member.code, member.isin
from portfell_app.project_selection_members as member
join portfell_app.projects as project on project.project_id = member.project_id
where project.status = 'active'
order by member.provider, member.exchange, member.code, member.isin
"""
        ).fetchall()
        return tuple(_listing(row) for row in rows)


def _listing(row: tuple[object, ...]) -> SharedListingKey:
    if len(row) != 4:
        raise ValueError("active_inventory_projection_invalid")
    provider, exchange, code, isin = row
    if (
        not isinstance(provider, str)
        or not isinstance(exchange, str)
        or not isinstance(code, str)
        or not isinstance(isin, str)
        or not all((provider, exchange, code, isin))
    ):
        raise ValueError("active_inventory_projection_invalid")
    return SharedListingKey(provider, exchange, code, isin)
