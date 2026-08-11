"""PostgreSQL-backed shared market-data and research-data adapters."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from hashlib import sha256
from typing import Any, Literal, Protocol, cast

from portfell.hosted_research_ports import ResearchDataset, UnivariateProgress
from portfell.shared_market_data import SharedListingKey
from portfell.table_io import JsonRow
from portfell.univariate_statistics import build_univariate_statistics

SharedDataset = Literal["quotes", "dividends", "splits"]


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

    def upsert_metadata(self, rows: tuple[JsonRow, ...]) -> None:
        """Publish canonical metadata without any tenant fields."""

        for row in rows:
            listing = SharedListingKey.from_row(row)
            self._assert_shared(row, listing)
            self._connection.execute(
                """
insert into portfell_app.shared_market_metadata (provider, exchange, code, isin, document)
values (%s, %s, %s, %s, %s::jsonb)
on conflict (provider, exchange, code, isin) do update
set document = excluded.document, updated_at = now()
""",
                (*_listing_values(listing), _json(row)),
            )

    def selected_rows(
        self, member_ids: tuple[str, ...], *, dataset: ResearchDataset
    ) -> tuple[JsonRow, ...]:
        values: list[JsonRow] = []
        for member_id in member_ids:
            listing = SharedListingKey.from_member_id(member_id)
            values.extend(self._rows_for_listing(dataset, listing))
        return tuple(values)

    def quote_rows(self, member_ids: tuple[str, ...]) -> tuple[JsonRow, ...]:
        return self.selected_rows(member_ids, dataset="quotes")

    def upsert_rows(
        self, dataset_type: SharedDataset, listing: SharedListingKey, rows: tuple[JsonRow, ...]
    ) -> None:
        """Publish rows by canonical business key and refresh coverage atomically."""

        canonical: dict[str, JsonRow] = {}
        for row in rows:
            self._assert_shared(row, listing)
            canonical[_business_key(dataset_type, row)] = dict(row)
        for business_key, row in sorted(canonical.items()):
            self._connection.execute(
                """
insert into portfell_app.shared_market_rows (
    dataset_type, provider, exchange, code, isin, business_key, document
) values (%s, %s, %s, %s, %s, %s, %s::jsonb)
on conflict (dataset_type, provider, exchange, code, isin, business_key) do update
set document = excluded.document, updated_at = now()
""",
                (dataset_type, *_listing_values(listing), business_key, _json(row)),
            )
        published = self._rows_for_listing(dataset_type, listing)
        dates = sorted(str(row["date"]) for row in published if row.get("date"))
        digest = sha256(_json(published).encode()).hexdigest()
        self._connection.execute(
            """
insert into portfell_app.shared_market_coverage (
    dataset_type, provider, exchange, code, isin, first_business_date, last_business_date,
    row_count, content_hash
) values (%s, %s, %s, %s, %s, %s::date, %s::date, %s, %s)
on conflict (dataset_type, provider, exchange, code, isin) do update
set first_business_date = excluded.first_business_date,
    last_business_date = excluded.last_business_date, row_count = excluded.row_count,
    content_hash = excluded.content_hash, updated_at = now()
""",
            (
                dataset_type,
                *_listing_values(listing),
                dates[0] if dates else None,
                dates[-1] if dates else None,
                len(published),
                digest,
            ),
        )

    @staticmethod
    def _assert_shared(row: Mapping[str, Any], listing: SharedListingKey) -> None:
        if {"user_id", "project_id", "credential_id", "run_id"}.intersection(row):
            raise ValueError("shared_market_tenant_field_forbidden")
        if SharedListingKey.from_row(row) != listing:
            raise ValueError("shared_market_listing_identity_mismatch")

    def _rows_for_listing(
        self, dataset: SharedDataset, listing: SharedListingKey
    ) -> tuple[JsonRow, ...]:
        rows = self._connection.execute(
            """
select document from portfell_app.shared_market_rows
where dataset_type = %s and provider = %s and exchange = %s and code = %s and isin = %s
order by business_key
""",
            (dataset, *_listing_values(listing)),
        ).fetchall()
        return tuple(_document(row) for row in rows)


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


def _listing_values(listing: SharedListingKey) -> tuple[str, str, str, str]:
    return listing.provider, listing.exchange, listing.code, listing.isin


def _business_key(dataset: SharedDataset, row: Mapping[str, Any]) -> str:
    if dataset == "quotes":
        value = row.get("date")
    else:
        value = row.get("date", row.get("payment_date", row.get("ex_date")))
    if not isinstance(value, str) or not value:
        raise ValueError("shared_market_business_key_invalid")
    return value


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))
