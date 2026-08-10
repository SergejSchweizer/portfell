from __future__ import annotations

from datetime import date

import pytest

from portfell.market_revision_delta import (
    CoverageRange,
    InMemoryMarketRevisionCatalog,
    MarketRevision,
    MarketRevisionPlanError,
    plan_missing_windows,
)


def test_delta_planner_skips_covered_history_and_plans_only_gaps_overlap_and_tail() -> None:
    windows = plan_missing_windows(
        requested_start=date(2026, 1, 1),
        requested_end=date(2026, 1, 10),
        coverage=(
            CoverageRange(date(2026, 1, 1), date(2026, 1, 3)),
            CoverageRange(date(2026, 1, 6), date(2026, 1, 8)),
        ),
        correction_overlap_days=1,
    )

    assert [(window.start, window.end) for window in windows] == [
        (date(2026, 1, 3), date(2026, 1, 5)),
        (date(2026, 1, 8), date(2026, 1, 10)),
    ]


def test_delta_planner_uses_one_full_window_for_uncovered_listing() -> None:
    windows = plan_missing_windows(
        requested_start=date(2026, 1, 1),
        requested_end=date(2026, 1, 10),
        coverage=(),
        correction_overlap_days=2,
    )

    assert windows == (CoverageRange(date(2026, 1, 1), date(2026, 1, 10)),)


def test_immutable_revision_publication_is_idempotent_and_retains_corrections() -> None:
    catalog = InMemoryMarketRevisionCatalog()
    first = MarketRevision("revision-a", "quotes", "listing-a", "content-a")
    corrected = MarketRevision("revision-b", "quotes", "listing-a", "content-b")

    assert catalog.publish(first) == first
    assert catalog.publish(first) == first
    assert catalog.publish(corrected) == corrected

    assert catalog.current("quotes", "listing-a") == corrected
    assert catalog.read("revision-a") == first


def test_market_revision_contract_rejects_invalid_inputs_and_conflicts() -> None:
    with pytest.raises(MarketRevisionPlanError, match="coverage_range_invalid"):
        CoverageRange(date(2026, 1, 2), date(2026, 1, 1))
    with pytest.raises(MarketRevisionPlanError, match="market_revision_identity_required"):
        MarketRevision("", "quotes", "listing-1", "hash")
    with pytest.raises(MarketRevisionPlanError, match="requested_range_invalid"):
        plan_missing_windows(
            requested_start=date(2026, 1, 2),
            requested_end=date(2026, 1, 1),
            coverage=(),
            correction_overlap_days=0,
        )
    with pytest.raises(MarketRevisionPlanError, match="correction_overlap_invalid"):
        plan_missing_windows(
            requested_start=date(2026, 1, 1),
            requested_end=date(2026, 1, 2),
            coverage=(),
            correction_overlap_days=-1,
        )
    catalog = InMemoryMarketRevisionCatalog()
    assert catalog.current("quotes", "missing") is None
    assert catalog.read("missing") is None
    catalog.publish(MarketRevision("revision-1", "quotes", "listing-1", "hash-a"))
    with pytest.raises(MarketRevisionPlanError, match="market_revision_id_conflict"):
        catalog.publish(MarketRevision("revision-1", "quotes", "listing-1", "hash-b"))
