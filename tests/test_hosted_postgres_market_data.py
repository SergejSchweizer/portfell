from __future__ import annotations

from portfell.hosted_postgres_market_data import PostgresSharedMarketData


class _Cursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows


class _Connection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        self.calls.append((sql, parameters))
        if "shared_market_metadata" in sql:
            return _Cursor([({"isin": "US1", "exchange": "US", "code": "ONE"},)])
        return _Cursor([({"isin": "US1", "exchange": "US", "code": "ONE", "date": "2026-01-01"},)])


def test_reads_tenant_neutral_metadata_and_selected_listing_rows() -> None:
    connection = _Connection()
    data = PostgresSharedMarketData(connection)

    assert data.all_isins_rows() == ({"isin": "US1", "exchange": "US", "code": "ONE"},)
    assert data.selected_rows(("US1:US:ONE",), dataset="quotes") == (
        {"isin": "US1", "exchange": "US", "code": "ONE", "date": "2026-01-01"},
    )
    assert connection.calls[1][1] == ("quotes", "eodhd", "US", "ONE", "US1")
