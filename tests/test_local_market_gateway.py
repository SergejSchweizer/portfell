from datetime import date
from decimal import Decimal

from portfell.market_source.contracts import ListingKey
from portfell.market_source.local_gateway import LocalMarketDataGateway


def test_local_gateway_reads_published_snapshot_without_database(tmp_path):
    (tmp_path / "listings.jsonl").write_text(
        '{"code":"AAA","country":"DE","currency":"EUR","exchange":"XETR",'
        '"instrument_type":"ETF","isin":"DE000AAA","is_active":true,"name":"A"}\n',
        encoding="utf-8",
    )
    (tmp_path / "quotes.jsonl").write_text(
        '{"adjusted_close":"10.5","close":"10.0","code":"AAA",'
        '"exchange":"XETR","isin":"DE000AAA","trade_date":"2025-01-02",'
        '"volume":"3"}\n',
        encoding="utf-8",
    )
    for name in ("dividends", "splits"):
        (tmp_path / f"{name}.jsonl").write_text("", encoding="utf-8")

    key = ListingKey("DE000AAA", "XETR", "AAA")
    snapshot = LocalMarketDataGateway(tmp_path).read_snapshot(
        [key], start=date(2025, 1, 1), end=date(2025, 1, 3)
    )
    assert snapshot.listings[0].key == key
    assert snapshot.quotes[0].adjusted_close == Decimal("10.5")
