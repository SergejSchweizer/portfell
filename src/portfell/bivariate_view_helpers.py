"""Shared row and label helpers for bivariate API view models."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from portfell.table_io import JsonRow


def pair_listings(rows: tuple[JsonRow, ...]) -> tuple[tuple[str, str, str], ...]:
    return tuple(sorted({listing(row, side) for row in rows for side in ("left", "right")}))


def listing(row: JsonRow, side: str) -> tuple[str, str, str]:
    return (str(row[side + "_isin"]), str(row[side + "_exchange"]), str(row[side + "_code"]))


def member_id(row: Mapping[str, Any]) -> str:
    return f"{row.get('isin', '')}:{row.get('exchange', '')}:{row.get('code', '')}"


def labels(listings: tuple[tuple[str, str, str], ...]) -> list[JsonRow]:
    return [
        {"isin": isin, "exchange": exchange, "code": code, "label": f"{code}.{exchange}"}
        for isin, exchange, code in listings
    ]
