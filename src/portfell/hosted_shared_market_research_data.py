"""Research-data port backed by immutable shared market revisions."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from portfell.hosted_research_ports import ResearchDataset, UnivariateProgress
from portfell.shared_market_data import SharedListingKey, SharedMarketDataStore
from portfell.table_io import JsonRow
from portfell.univariate_statistics import build_univariate_statistics


class SharedMarketResearchData:
    """Load exactly selected full listings from the shared revision catalog."""

    def __init__(self, store: SharedMarketDataStore) -> None:
        self._store = store

    def has_selected_rows(self, member_ids: tuple[str, ...], *, dataset: ResearchDataset) -> bool:
        """Check catalog metadata without loading the selected Parquet revisions."""

        listings = {SharedListingKey.from_member_id(member_id) for member_id in member_ids}
        return any(
            record.dataset_type == dataset and record.listing in listings and record.row_count > 0
            for record in self._store.coverage()
        )

    def selected_rows(
        self, member_ids: tuple[str, ...], *, dataset: ResearchDataset
    ) -> tuple[JsonRow, ...]:
        return tuple(
            row
            for member_id in member_ids
            for row in self._store.read(dataset, SharedListingKey.from_member_id(member_id))
        )

    def quote_period(self, member_ids: tuple[str, ...]) -> tuple[str | None, str | None]:
        """Return the coverage bounds for the selected quote listings."""

        coverage = {
            record.listing: record
            for record in self._store.coverage()
            if record.dataset_type == "quotes"
        }
        records = [
            coverage.get(SharedListingKey.from_member_id(member_id)) for member_id in member_ids
        ]
        starts = [
            record.first_business_date
            for record in records
            if record is not None and record.first_business_date
        ]
        ends = [
            record.last_business_date
            for record in records
            if record is not None and record.last_business_date
        ]
        return (min(starts) if starts else None, max(ends) if ends else None)

    def build_univariate_rows(
        self,
        member_ids: tuple[str, ...],
        *,
        on_progress: UnivariateProgress | None = None,
    ) -> tuple[JsonRow, ...]:
        coverage = {
            (record.dataset_type, record.listing): record for record in self._store.coverage()
        }

        def rows_for(listing: SharedListingKey, dataset: ResearchDataset) -> tuple[JsonRow, ...]:
            record = coverage.get((dataset, listing))
            if record is None:
                return ()
            return tuple(self._store.read_revision(dataset, listing, record.content_hash))

        def build_listing(member_id: str) -> JsonRow | None:
            listing = SharedListingKey.from_member_id(member_id)
            quote_rows = rows_for(listing, "quotes")
            if not quote_rows:
                return None
            rows = build_univariate_statistics(
                quote_rows,
                dividend_rows=rows_for(listing, "dividends"),
                concurrency=None,
            )
            return rows[0] if rows else None

        rows: list[JsonRow] = []
        with ThreadPoolExecutor(max_workers=max(1, os.process_cpu_count() or 1)) as executor:
            futures = [executor.submit(build_listing, member_id) for member_id in member_ids]
            for completed, future in enumerate(as_completed(futures), start=1):
                row = future.result()
                if row is not None:
                    rows.append(row)
                if on_progress is not None:
                    on_progress(completed)
        return tuple(
            sorted(rows, key=lambda row: (str(row["isin"]), str(row["exchange"]), str(row["code"])))
        )
