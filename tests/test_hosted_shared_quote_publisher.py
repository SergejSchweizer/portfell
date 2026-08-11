from __future__ import annotations

from portfell.hosted_shared_quote_publisher import SharedQuotePublisher
from portfell.shared_market_data import SharedListingKey, SharedMarketDataStore


def test_publishes_each_full_listing_to_its_own_immutable_revision(tmp_path) -> None:  # type: ignore[no-untyped-def]
    store = SharedMarketDataStore(tmp_path)
    publisher = SharedQuotePublisher(store)
    publisher.publish(
        (
            {
                "provider": "eodhd",
                "exchange": "XETRA",
                "code": "ABC",
                "isin": "IE1",
                "date": "2026-01-01",
                "adjusted_close": 10.0,
            },
            {
                "provider": "eodhd",
                "exchange": "LSE",
                "code": "XYZ",
                "isin": "IE2",
                "date": "2026-01-01",
                "adjusted_close": 20.0,
            },
        )
    )

    assert len(store.coverage()) == 2
    assert (
        store.read("quotes", SharedListingKey("eodhd", "XETRA", "ABC", "IE1"))[0]["adjusted_close"]
        == 10.0
    )
