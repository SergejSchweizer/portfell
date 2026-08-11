"""PostgreSQL-backed shared market-data and research-data adapters."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any, Protocol, cast

from portfell.hosted_research_ports import ResearchDataset, UnivariateProgress
from portfell.shared_market_data import SharedListingKey
from portfell.table_io import JsonRow
from portfell.univariate_statistics import build_univariate_statistics


class MarketDataCursor(Protocol):
    def fetchall(self) -> list[tuple[object, ...]]: ...


class MarketDataConnection(Protocol):
    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> MarketDataCursor: ...


class PostgresSharedMarketData:
    """Read canonical tenant-neutral data from PostgreSQL only."""

    def __init__(self, connection: MarketDataConnection) -> None:
        self._connection = connection

    def all_isins_rows(self) -> tuple[JsonRow, ...]:
        rows = self._connection.execute(
            "select document from portfell_app.shared_market_metadata order by isin, exchange, code"
        ).fetchall()
        return tuple(_document(row) for row in rows)

    def selected_rows(
        self, member_ids: tuple[str, ...], *, dataset: ResearchDataset
    ) -> tuple[JsonRow, ...]:
        values: list[JsonRow] = []
        for member_id in member_ids:
            listing = SharedListingKey.from_member_id(member_id)
            rows = self._connection.execute(
                """
select document from portfell_app.shared_market_rows
where dataset_type = %s and provider = %s and exchange = %s and code = %s and isin = %s
order by business_key
""",
                (dataset, listing.provider, listing.exchange, listing.code, listing.isin),
            ).fetchall()
            values.extend(_document(row) for row in rows)
        return tuple(values)

    def quote_rows(self, member_ids: tuple[str, ...]) -> tuple[JsonRow, ...]:
        return self.selected_rows(member_ids, dataset="quotes")


class PostgresResearchData:
    """Build project-scoped research inputs from shared PostgreSQL artifacts."""

    def __init__(self, market_data: PostgresSharedMarketData) -> None:
        self._market_data = market_data

    def selected_rows(
        self, member_ids: tuple[str, ...], *, dataset: ResearchDataset
    ) -> tuple[JsonRow, ...]:
        return self._market_data.selected_rows(member_ids, dataset=dataset)

    def build_univariate_rows(
        self,
        member_ids: tuple[str, ...],
        *,
        on_progress: UnivariateProgress | None = None,
    ) -> tuple[JsonRow, ...]:
        quotes = self.selected_rows(member_ids, dataset="quotes")
        dividends = self.selected_rows(member_ids, dataset="dividends")
        rows = tuple(
            build_univariate_statistics(
                quotes,
                dividend_rows=dividends,
                concurrency=max(1, os.process_cpu_count() or 1),
            )
        )
        if on_progress is not None:
            for completed in range(1, len(member_ids) + 1):
                on_progress(completed)
        return rows


def _document(row: tuple[object, ...]) -> JsonRow:
    if len(row) != 1:
        raise ValueError("shared_market_document_invalid")
    value = row[0]
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, Mapping):
        raise ValueError("shared_market_document_invalid")
    return dict(cast(Mapping[str, Any], value))
