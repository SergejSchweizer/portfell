"""Publish worker quote rows to immutable shared market revisions."""

from __future__ import annotations

from collections.abc import Iterable

from portfell.shared_market_data import SharedListingKey, SharedMarketDataStore
from portfell.table_io import JsonRow


class SharedQuotePublisher:
    """Group full listing rows before publishing immutable quote revisions."""

    def __init__(self, store: SharedMarketDataStore) -> None:
        self._store = store

    def publish(self, rows: Iterable[JsonRow]) -> None:
        grouped: dict[SharedListingKey, list[JsonRow]] = {}
        for row in rows:
            grouped.setdefault(SharedListingKey.from_row(row), []).append(row)
        for listing, values in grouped.items():
            self._store.upsert("quotes", listing, values)
