from __future__ import annotations

import pytest

from portfell.entitlements import ProviderDownloadRun
from portfell.hosted_api_state import HostedApiState, ProjectRecord, SelectionRecord
from portfell.hosted_research_repository import HostedResearchRepository
from portfell.shared_market_data import (
    SharedListingKey,
    SharedMarketDataError,
    SharedMarketDataStore,
    active_project_inventory,
    inventory_hash,
)


def _listing() -> SharedListingKey:
    return SharedListingKey("eodhd", "XETRA", "ABC", "IE0000000001")


def _row(date: str, close: float) -> dict[str, object]:
    return {
        "provider": "eodhd",
        "exchange": "XETRA",
        "code": "ABC",
        "isin": "IE0000000001",
        "date": date,
        "adjusted_close": close,
    }


def test_canonical_store_deduplicates_business_keys_and_replaces_corrections(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SharedMarketDataStore(tmp_path)
    listing = _listing()
    first = store.upsert("quotes", listing, [_row("2025-01-01", 10.0), _row("2025-01-01", 10.0)])
    corrected = store.upsert(
        "quotes", listing, [_row("2025-01-01", 11.0), _row("2025-01-02", 12.0)]
    )

    assert first.row_count == 1
    assert corrected.row_count == 2
    assert corrected.content_hash != first.content_hash
    assert [row["adjusted_close"] for row in store.read("quotes", listing)] == [11.0, 12.0]
    initial_rows = store.read_revision("quotes", listing, first.content_hash)
    assert [row["adjusted_close"] for row in initial_rows] == [10.0]
    assert store.revision_path("quotes", listing, corrected.content_hash).is_file()
    assert store.coverage() == (corrected,)
    assert store.rebuild_coverage() == (corrected,)


def test_shared_store_fails_closed_without_partial_publication(tmp_path) -> None:  # type: ignore[no-untyped-def]
    listing = _listing()
    initial = SharedMarketDataStore(tmp_path)
    initial.upsert("quotes", listing, [_row("2025-01-01", 10.0)])
    store = SharedMarketDataStore(
        tmp_path, before_replace=lambda _: (_ for _ in ()).throw(OSError("stop"))
    )

    with pytest.raises(OSError, match="stop"):
        store.upsert("quotes", listing, [_row("2025-01-01", 11.0)])
    assert initial.read("quotes", listing)[0]["adjusted_close"] == 10.0
    assert initial.coverage()[0].row_count == 1


def test_shared_store_rejects_scoped_rows_and_corrupt_catalog(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SharedMarketDataStore(tmp_path)
    with pytest.raises(SharedMarketDataError, match="forbidden"):
        store.upsert("quotes", _listing(), [{**_row("2025-01-01", 10.0), "project_id": "p"}])
    (tmp_path / "market-data").mkdir()
    (tmp_path / "market-data" / "coverage.json").write_text("bad", encoding="utf-8")
    with pytest.raises(SharedMarketDataError, match="catalog_corrupt"):
        store.coverage()


def test_active_project_inventory_is_a_deduplicated_full_listing_union() -> None:
    state = HostedApiState(
        projects_by_id={
            "one": ProjectRecord("one", "user", "One"),
            "two": ProjectRecord("two", "user", "Two"),
        },
        selections_by_id={
            "a": SelectionRecord("a", "user", "one", "A", ("IE1:XETRA:ABC", "IE2:LSE:XYZ")),
            "b": SelectionRecord("b", "user", "two", "B", ("IE1:XETRA:ABC",)),
        },
    )
    inventory = active_project_inventory(state)
    assert inventory == (
        SharedListingKey("eodhd", "LSE", "XYZ", "IE2"),
        SharedListingKey("eodhd", "XETRA", "ABC", "IE1"),
    )
    assert inventory_hash(inventory) == inventory_hash(reversed(inventory))
    state.selections_by_id["bad"] = SelectionRecord("bad", "user", "one", "bad", ("bad",))
    with pytest.raises(SharedMarketDataError, match="invalid_listing_member_id"):
        active_project_inventory(state)


def test_empty_workspace_and_project_without_selection_have_empty_inventory() -> None:
    assert active_project_inventory(HostedApiState()) == ()
    state = HostedApiState(
        projects_by_id={"one": ProjectRecord("one", "user", "One")},
    )
    assert active_project_inventory(state) == ()


def test_same_isin_on_different_listings_never_shares_a_file(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SharedMarketDataStore(tmp_path)
    primary = _listing()
    secondary = SharedListingKey("eodhd", "LSE", "ABC.L", primary.isin)
    store.upsert("quotes", primary, [_row("2025-01-01", 10.0)])
    store.upsert(
        "quotes",
        secondary,
        [{**_row("2025-01-01", 20.0), "exchange": "LSE", "code": "ABC.L"}],
    )
    revisions = {item.listing: item for item in store.coverage()}
    primary_revision = revisions[primary]
    secondary_revision = revisions[secondary]
    primary_path = store.revision_path("quotes", primary, primary_revision.content_hash)
    secondary_path = store.revision_path("quotes", secondary, secondary_revision.content_hash)
    assert primary_path != secondary_path
    assert store.read("quotes", primary)[0]["adjusted_close"] == 10.0
    assert store.read("quotes", secondary)[0]["adjusted_close"] == 20.0


def test_research_repository_reads_project_run_rows_from_canonical_store(tmp_path) -> None:  # type: ignore[no-untyped-def]
    state = HostedApiState(shared_market_data_store=SharedMarketDataStore(tmp_path))
    state.shared_market_data_store.upsert("quotes", _listing(), [_row("2025-01-01", 10.0)])
    state.downloads_by_id["run"] = ProviderDownloadRun(
        "run", "user", "credential", "eodhd", "succeeded", ("IE0000000001:XETRA:ABC",), "hash"
    )
    assert HostedResearchRepository(state).quote_rows("run") == (_row("2025-01-01", 10.0),)
