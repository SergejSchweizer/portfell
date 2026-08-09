from portfell.income import build_income_evidence, normalize_distribution_events
from portfell.multivariate_inputs import MultivariateListingKey


def test_income_evidence_uses_trailing_events_not_latest_payment_annualization() -> None:
    listing = MultivariateListingKey("IE1", "X", "A")
    events = normalize_distribution_events(
        [
            {
                "isin": "IE1",
                "exchange": "X",
                "code": "A",
                "event_id": str(month),
                "payment_date": f"2025-{month:02d}-01",
                "amount": 1.0,
                "currency": "EUR",
            }
            for month in range(1, 13)
        ],
        listing=listing,
    )
    evidence = build_income_evidence(
        listing=listing, events=events, period_end="2025-12-31", denominator_price=100.0
    )
    assert evidence.gross_ttm_distribution_amount == 12.0
    assert evidence.gross_ttm_distribution_yield == 0.12
    assert evidence.nav_erosion is None


def test_income_evidence_keeps_missing_months_unknown_and_rejects_insufficient_history() -> None:
    listing = MultivariateListingKey("IE1", "X", "A")
    events = normalize_distribution_events(
        [
            {
                "isin": "IE1",
                "exchange": "X",
                "code": "A",
                "event_id": "1",
                "date": "2025-01-01",
                "amount": 1.0,
                "currency": "EUR",
            },
            {
                "isin": "IE1",
                "exchange": "X",
                "code": "A",
                "event_id": "2",
                "date": "2025-03-01",
                "amount": 1.0,
                "currency": "EUR",
            },
        ],
        listing=listing,
    )
    evidence = build_income_evidence(
        listing=listing, events=events, period_end="2025-12-31", denominator_price=100.0
    )
    assert evidence.observed_month_count == 2
    assert "insufficient_observed_months" in evidence.availability_reasons
    assert evidence.gross_ttm_distribution_amount is None
