from __future__ import annotations

import pytest

from portfell.hosted_postgres_active_inventory import PostgresActiveProjectInventory
from portfell.shared_market_data import SharedListingKey


class _Cursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows


class _Connection:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self.rows = rows
        self.sql = ""

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        assert parameters == ()
        self.sql = sql
        return _Cursor(self.rows)


def test_reads_distinct_active_full_listing_inventory() -> None:
    connection = _Connection([("eodhd", "LSE", "ONE", "IE1"), ("eodhd", "XETRA", "TWO", "IE2")])

    assert PostgresActiveProjectInventory(connection).listings() == (
        SharedListingKey("eodhd", "LSE", "ONE", "IE1"),
        SharedListingKey("eodhd", "XETRA", "TWO", "IE2"),
    )
    assert "project.status = 'active'" in connection.sql
    assert "distinct" in connection.sql


def test_rejects_invalid_worker_inventory_projection() -> None:
    with pytest.raises(ValueError, match="active_inventory_projection_invalid"):
        PostgresActiveProjectInventory(_Connection([("eodhd", "XETRA", "ONE")])).listings()
