from typing import cast

from portfell.dash_app.metadata_distributions import universe_distributions


def test_distributions_are_complete_deterministic_and_unknown_safe() -> None:
    rows = [
        {"instrument_type": "ETF", "country": "Germany", "currency": "EUR"},
        {"instrument_type": "ETF", "country": "", "currency": None},
        {"instrument_type": "Fund", "country": "Germany", "currency": "USD"},
    ]
    result = universe_distributions(reversed(rows))
    assert result["instrument_type"] == [
        {"category": "ETF", "count": 2},
        {"category": "Fund", "count": 1},
    ]
    assert result["country"][-1] == {"category": "Unknown", "count": 1}
    assert sum(cast(int, item["count"]) for item in result["currency"]) == 3
