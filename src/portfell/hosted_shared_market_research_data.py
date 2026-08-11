"""Research-data port backed by immutable shared market revisions."""

from __future__ import annotations

import os

from portfell.hosted_research_ports import ResearchDataset, UnivariateProgress
from portfell.shared_market_data import SharedListingKey, SharedMarketDataStore
from portfell.table_io import JsonRow
from portfell.univariate_statistics import build_univariate_statistics


class SharedMarketResearchData:
    """Load exactly selected full listings from the shared revision catalog."""

    def __init__(self, store: SharedMarketDataStore) -> None:
        self._store = store

    def selected_rows(
        self, member_ids: tuple[str, ...], *, dataset: ResearchDataset
    ) -> tuple[JsonRow, ...]:
        return tuple(
            row
            for member_id in member_ids
            for row in self._store.read(dataset, SharedListingKey.from_member_id(member_id))
        )

    def build_univariate_rows(
        self,
        member_ids: tuple[str, ...],
        *,
        on_progress: UnivariateProgress | None = None,
    ) -> tuple[JsonRow, ...]:
        rows = tuple(
            build_univariate_statistics(
                self.selected_rows(member_ids, dataset="quotes"),
                dividend_rows=self.selected_rows(member_ids, dataset="dividends"),
                concurrency=max(1, os.process_cpu_count() or 1),
            )
        )
        if on_progress is not None:
            for completed in range(1, len(member_ids) + 1):
                on_progress(completed)
        return rows
