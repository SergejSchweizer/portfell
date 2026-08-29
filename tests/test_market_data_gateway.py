from __future__ import annotations

from datetime import date
from decimal import Decimal

from portfell.market_source.contracts import ListingKey
from portfell.market_source.gateway import MarketDataGateway


class FakeCursor:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.results: list[list[tuple[object, ...]]] = [
            [("IE00TEST", "XETRA", "TEST", "Test ETF", "ETF", "DE", "EUR", True)],
            [
                (
                    "IE00TEST",
                    "XETRA",
                    "TEST",
                    date(2025, 1, 2),
                    Decimal("100"),
                    Decimal("100"),
                    Decimal("10"),
                )
            ],
            [("IE00TEST", "XETRA", "TEST", date(2025, 1, 2), "event-1", Decimal("1"), "EUR")],
            [("IE00TEST", "XETRA", "TEST", date(2025, 1, 2), "2:1", Decimal("2"))],
        ]

    def execute(self, query: str, parameters: object = None) -> None:
        self.queries.append(query)

    def fetchone(self) -> tuple[object, ...] | None:
        return (True, False, True)

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.results.pop(0)


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_value = FakeCursor()
        self.closed = False

    def cursor(self) -> FakeCursor:
        return self.cursor_value

    def close(self) -> None:
        self.closed = True


def test_gateway_materializes_all_tables_in_one_consistent_snapshot() -> None:
    connection = FakeConnection()
    gateway = MarketDataGateway(lambda: connection, role="portfell", member_of="portfell_app")

    snapshot = gateway.read_snapshot(
        [ListingKey("IE00TEST", "XETRA", "TEST")],
        start=date(2025, 1, 2),
        end=date(2025, 1, 2),
    )

    assert len(snapshot.listings) == len(snapshot.quotes) == len(snapshot.dividends) == 1
    assert len(snapshot.splits) == 1
    assert connection.closed
    assert (
        connection.cursor_value.queries.count(
            "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
        )
        == 1
    )
    assert connection.cursor_value.queries[-1] == "COMMIT"
    queries = "\n".join(connection.cursor_value.queries)
    assert all(table in queries for table in ("listings", "eod_quotes", "dividends", "splits"))
    assert "xetra_loader_sync" not in queries
