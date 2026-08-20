"""Shared active-project market refresh planned once per Sunday cycle."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from portfell.multivariate.contracts.common import ListingIdentity
from portfell.multivariate.contracts.serialization import canonical_json


@dataclass(frozen=True, slots=True)
class ActiveProjectUniverse:
    project_slug: str
    listings: tuple[ListingIdentity, ...]


@dataclass(frozen=True, slots=True)
class MarketRefreshSummary:
    cycle_key: str
    listing_count: int
    refreshed_business_keys: int
    revision: str


MarketRefreshCallable = Callable[[tuple[ListingIdentity, ...]], tuple[str, int]]


def active_union(projects: tuple[ActiveProjectUniverse, ...]) -> tuple[ListingIdentity, ...]:
    """Return one de-duplicated full-listing union in stable identity order."""

    return tuple(sorted({listing for project in projects for listing in project.listings}))


def market_cycle_key(*, projects: tuple[ActiveProjectUniverse, ...], cycle_date: str) -> str:
    """Stable logical identity used to resume one market refresh without duplicate keys."""

    union = active_union(projects)
    return hashlib.sha256(
        canonical_json({"cycle_date": cycle_date, "listings": union}).encode()
    ).hexdigest()


def refresh_active_union_once(
    *,
    projects: tuple[ActiveProjectUniverse, ...],
    cycle_date: str,
    refresh: MarketRefreshCallable,
) -> MarketRefreshSummary:
    """Invoke the existing quotes/dividends/splits refresh exactly once for the union."""

    union = active_union(projects)
    revision, refreshed_keys = refresh(union)
    if refreshed_keys < 0:
        raise ValueError("refreshed business-key count cannot be negative")
    return MarketRefreshSummary(
        cycle_key=market_cycle_key(projects=projects, cycle_date=cycle_date),
        listing_count=len(union),
        refreshed_business_keys=refreshed_keys,
        revision=revision,
    )
