"""Pinned quote-input helpers for the Multivariate service."""

from __future__ import annotations

from collections.abc import Sequence

from portfell.multivariate_inputs import MultivariateListingKey
from portfell.table_io import JsonRow


def common_dates(
    rows: Sequence[JsonRow], keys: tuple[MultivariateListingKey, ...]
) -> tuple[str, ...]:
    by_key: dict[tuple[str, str, str], set[str]] = {}
    for row in rows:
        key = (str(row.get("isin", "")), str(row.get("exchange", "")), str(row.get("code", "")))
        by_key.setdefault(key, set()).add(str(row.get("date", "")))
    dates: set[str] = set(by_key.get(keys[0].as_tuple(), set())) if keys else set()
    for key in keys[1:]:
        dates &= by_key.get(key.as_tuple(), set())
    return tuple(sorted(date for date in dates if date))


def first_price(rows: Sequence[JsonRow], key: MultivariateListingKey) -> float | None:
    return _edge_price(rows, key, first=True)


def last_price(rows: Sequence[JsonRow], key: MultivariateListingKey) -> float | None:
    return _edge_price(rows, key, first=False)


def _edge_price(
    rows: Sequence[JsonRow], key: MultivariateListingKey, *, first: bool
) -> float | None:
    matching = [row for row in rows if MultivariateListingKey.from_row(row) == key]
    if not matching:
        return None
    ordered = sorted(matching, key=lambda row: str(row.get("date", "")))
    value = (ordered[0] if first else ordered[-1]).get("adjusted_close")
    return float(value) if isinstance(value, int | float) and value > 0 else None
