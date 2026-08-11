from __future__ import annotations

from datetime import date

from portfell.hosted_shared_coverage_bootstrap import plan_exact_selection_bootstrap
from portfell.project_selection_bootstrap import InMemoryBootstrapService
from portfell.shared_market_data import SharedListingKey, SharedMarketDataStore


def test_exact_project_bootstrap_skips_provider_when_shared_coverage_is_current(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SharedMarketDataStore(tmp_path)
    listing = SharedListingKey("eodhd", "XETRA", "ABC", "IE1")
    store.upsert(
        "quotes", listing, [{**listing.as_row(), "date": "2026-01-10", "adjusted_close": 1.0}]
    )
    bootstrap = InMemoryBootstrapService().start(
        user_id="user",
        project_id="project",
        selection_id="selection",
        member_ids=("IE1:XETRA:ABC",),
    )
    plan = plan_exact_selection_bootstrap(
        store=store, bootstrap=bootstrap, required_quote_end=date(2026, 1, 10)
    )
    assert plan.covered_listing_count == 1
    assert not plan.provider_call_required


def test_exact_project_bootstrap_only_exposes_its_missing_listing_keys(tmp_path) -> None:  # type: ignore[no-untyped-def]
    bootstrap = InMemoryBootstrapService().start(
        user_id="user",
        project_id="project",
        selection_id="selection",
        member_ids=("IE1:XETRA:ABC", "IE2:XETRA:DEF"),
    )
    plan = plan_exact_selection_bootstrap(
        store=SharedMarketDataStore(tmp_path),
        bootstrap=bootstrap,
        required_quote_end=date(2026, 1, 10),
    )
    assert plan.provider_call_required
    assert plan.missing_listing_keys == (
        SharedListingKey("eodhd", "XETRA", "ABC", "IE1"),
        SharedListingKey("eodhd", "XETRA", "DEF", "IE2"),
    )
