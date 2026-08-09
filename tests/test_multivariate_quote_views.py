from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_quote_views import common_dates, first_price, last_price


def test_quote_views_use_only_the_pinned_listing_and_return_missing_explicitly() -> None:
    key = MultivariateListingKey("IE1", "X", "A")
    other = MultivariateListingKey("IE2", "X", "B")
    rows = (
        {"isin": "IE1", "exchange": "X", "code": "A", "date": "2025-01-02", "adjusted_close": 12.0},
        {"isin": "IE1", "exchange": "X", "code": "A", "date": "2025-01-01", "adjusted_close": 10.0},
        {"isin": "IE2", "exchange": "X", "code": "B", "date": "2025-01-01", "adjusted_close": 20.0},
    )
    assert common_dates(rows, (key, other)) == ("2025-01-01",)
    assert first_price(rows, key) == 10.0
    assert last_price(rows, key) == 12.0
    assert first_price(rows, MultivariateListingKey("missing", "X", "M")) is None
