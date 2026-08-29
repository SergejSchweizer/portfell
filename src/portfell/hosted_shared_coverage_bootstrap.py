"""Exact project bootstrap planning from tenant-neutral shared coverage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from portfell.project_selection_bootstrap import ProjectBootstrap
from portfell.shared_market_data import CoverageRecord, SharedListingKey, SharedMarketDataStore


@dataclass(frozen=True)
class CoverageBootstrapPlan:
    """A project-owned control result with no market payload or tenant leakage."""

    bootstrap: ProjectBootstrap
    covered_listing_count: int
    missing_listing_keys: tuple[SharedListingKey, ...]

    @property
    def provider_call_required(self) -> bool:
        return bool(self.missing_listing_keys)


def plan_exact_selection_bootstrap(
    *,
    store: SharedMarketDataStore,
    bootstrap: ProjectBootstrap,
    required_quote_end: date,
) -> CoverageBootstrapPlan:
    """Return zero-provider-call readiness only when every frozen member has current quotes."""

    coverage = {(record.dataset_type, record.listing): record for record in store.coverage()}
    listings = tuple(SharedListingKey.from_member_id(member) for member in bootstrap.member_ids)
    missing = tuple(
        listing
        for listing in listings
        if not _quote_current(coverage.get(("quotes", listing)), required_quote_end)
    )
    return CoverageBootstrapPlan(bootstrap, len(listings) - len(missing), missing)


def _quote_current(record: CoverageRecord | None, required_end: date) -> bool:
    if record is None or record.row_count == 0 or record.last_business_date is None:
        return False
    return date.fromisoformat(record.last_business_date) >= required_end
