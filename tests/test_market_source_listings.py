from __future__ import annotations

from typing import cast

from portfell.market_source.contracts import ListingKey
from portfell.market_source.listings import ListingsRepository


class FakeCursor:
    def __init__(self, batches: list[list[tuple[object, ...]]]) -> None:
        self.batches = batches
        self.queries: list[tuple[str, tuple[str, ...] | None]] = []

    def execute(self, query: str, parameters: object = None) -> None:
        if parameters is None:
            typed_parameters = None
        elif isinstance(parameters, tuple):
            raw_parameters = cast(tuple[object, ...], parameters)
            if not all(isinstance(parameter, str) for parameter in raw_parameters):
                raise TypeError("expected string tuple parameters")
            typed_parameters = cast(tuple[str, ...], raw_parameters)
        else:
            raise TypeError("expected string tuple parameters")
        self.queries.append((query, typed_parameters))

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.batches.pop(0)


def _row(isin: str, exchange: str, code: str, active: bool = True) -> tuple[object, ...]:
    return (isin, exchange, code, f"{isin} name", "ETF", "DE", "EUR", active)


def test_listings_repository_reads_full_identity_and_preserves_duplicate_isins() -> None:
    cursor = FakeCursor([[_row("IE00DUP", "XETRA", "B"), _row("IE00DUP", "GETTEX", "A")]])

    listings = ListingsRepository().by_keys(
        cursor, (ListingKey("IE00DUP", "XETRA", "B"), ListingKey("IE00DUP", "GETTEX", "A"))
    )

    assert [listing.key for listing in listings] == [
        ListingKey("IE00DUP", "GETTEX", "A"),
        ListingKey("IE00DUP", "XETRA", "B"),
    ]
    query, parameters = cursor.queries[0]
    assert "xetra_loader.listings" in query
    assert "ILIKE" not in query
    assert parameters == ("IE00DUP", "XETRA", "B", "IE00DUP", "GETTEX", "A")


def test_listings_repository_batches_501_keys() -> None:
    keys = tuple(ListingKey(f"IE{index:010d}", "XETRA", "ETF") for index in range(501))
    cursor = FakeCursor(
        [[_row(keys[0].isin, "XETRA", "ETF")], [_row(keys[-1].isin, "XETRA", "ETF")]]
    )

    listings = ListingsRepository().by_keys(cursor, keys)

    assert len(cursor.queries) == 2
    first_parameters = cursor.queries[0][1]
    second_parameters = cursor.queries[1][1]
    assert first_parameters is not None
    assert second_parameters is not None
    assert len(first_parameters) == 1500
    assert len(second_parameters) == 3
    assert [listing.key.isin for listing in listings] == [keys[0].isin, keys[-1].isin]


def test_listings_repository_reads_only_active_rows() -> None:
    cursor = FakeCursor([[_row("IE00ACTIVE", "XETRA", "A")]])

    listings = ListingsRepository().active(cursor)

    assert listings[0].is_active is True
    assert "WHERE is_active = true" in cursor.queries[0][0]


def test_listings_repository_normalizes_nullable_optional_instrument_type() -> None:
    cursor = FakeCursor([[_row("IE00UNKNOWN", "XETRA", "U")]])

    ListingsRepository().active(cursor)

    assert "COALESCE(instrument_type, '') AS instrument_type" in cursor.queries[0][0]
