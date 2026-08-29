"""Pure analytical return-series construction independent of storage backends."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from math import log
from typing import Any

import polars as pl

from portfell.return_quality import filter_valid_price_points
from portfell.table_io import JsonRow


def build_returns(quote_rows: Sequence[Mapping[str, Any]]) -> list[JsonRow]:
    """Build per-listing log and simple returns from valid adjusted closes."""

    returns: list[JsonRow] = []
    frame = pl.DataFrame([dict(row) for row in quote_rows], infer_schema_length=None)
    if frame.is_empty():
        return returns
    for listing_rows in frame.sort(  # pyright: ignore[reportUnknownMemberType]
        "isin", "exchange", "code", "date"
    ).partition_by("isin", "exchange", "code", maintain_order=True):
        ordered = listing_rows.to_dicts()
        isin, exchange, code = (
            str(ordered[0][field]) for field in ("isin", "exchange", "code")
        )
        valid_quotes, _quarantined = filter_valid_price_points(ordered)
        for previous, current in zip(valid_quotes, valid_quotes[1:], strict=False):
            previous_close = float(previous["adjusted_close"])
            current_close = float(current["adjusted_close"])
            returns.append(
                {
                    "isin": isin,
                    "exchange": exchange,
                    "code": code,
                    "date": str(current["date"]),
                    "return": log(current_close / previous_close),
                    "simple_return": (current_close / previous_close) - 1.0,
                }
            )
    return returns


__all__ = ["build_returns"]
