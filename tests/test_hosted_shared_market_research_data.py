from __future__ import annotations

from portfell.hosted_shared_market_research_data import SharedMarketResearchData
from portfell.shared_market_data import SharedListingKey, SharedMarketDataStore


def _quote(date: str, value: float) -> dict[str, object]:
    return {
        "provider": "eodhd",
        "exchange": "XETRA",
        "code": "ABC",
        "isin": "IE1",
        "date": date,
        "adjusted_close": value,
    }


def test_reads_only_exact_selected_listing_revisions(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SharedMarketDataStore(tmp_path)
    selected = SharedListingKey("eodhd", "XETRA", "ABC", "IE1")
    other = SharedListingKey("eodhd", "XETRA", "OTHER", "IE2")
    store.upsert("quotes", selected, [_quote("2026-01-01", 10.0)])
    store.upsert("quotes", other, [{**_quote("2026-01-01", 20.0), "code": "OTHER", "isin": "IE2"}])

    rows = SharedMarketResearchData(store).selected_rows(("IE1:XETRA:ABC",), dataset="quotes")

    assert rows == (_quote("2026-01-01", 10.0),)
