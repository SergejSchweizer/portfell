import pytest

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


def test_income_normalization_applies_latest_correction_deletion_and_split_factor() -> None:
    listing = MultivariateListingKey("IE1", "X", "A")
    events = normalize_distribution_events(
        [
            {
                "isin": "IE1",
                "exchange": "X",
                "code": "A",
                "event_id": "old",
                "logical_event_id": "jan",
                "revision": "1",
                "payment_date": "2025-01-01",
                "amount": 2.0,
                "currency": "EUR",
            },
            {
                "isin": "IE1",
                "exchange": "X",
                "code": "A",
                "event_id": "new",
                "logical_event_id": "jan",
                "revision": "2",
                "payment_date": "2025-01-01",
                "amount": 1.0,
                "split_factor": 2.0,
                "currency": "EUR",
            },
            {
                "isin": "IE1",
                "exchange": "X",
                "code": "A",
                "event_id": "gone",
                "payment_date": "2025-02-01",
                "amount": 3.0,
                "currency": "EUR",
                "deleted": True,
            },
        ],
        listing=listing,
    )
    assert len(events) == 1
    assert events[0].amount == 2.0
    assert events[0].source_id == "new"
    evidence = build_income_evidence(
        listing=listing, events=events, period_end="2025-12-31", denominator_price=100.0
    )
    assert evidence.monthly_distributions[0].amount == 2.0
    assert "split_adjusted_events_used" in evidence.warnings


def test_income_evidence_uses_only_comparable_months_for_cuts_and_reconciles_return() -> None:
    listing = MultivariateListingKey("IE1", "X", "A")
    events = normalize_distribution_events(
        [
            {
                "isin": "IE1",
                "exchange": "X",
                "code": "A",
                "event_id": "jan",
                "payment_date": "2025-01-01",
                "amount": 10.0,
                "currency": "EUR",
            },
            {
                "isin": "IE1",
                "exchange": "X",
                "code": "A",
                "event_id": "mar-a",
                "payment_date": "2025-03-01",
                "amount": 3.0,
                "currency": "EUR",
            },
            {
                "isin": "IE1",
                "exchange": "X",
                "code": "A",
                "event_id": "mar-b",
                "payment_date": "2025-03-15",
                "amount": 2.0,
                "currency": "EUR",
            },
        ],
        listing=listing,
    )
    evidence = build_income_evidence(
        listing=listing,
        events=events,
        period_start="2025-01-01",
        period_end="2025-12-31",
        denominator_price=110.0,
        start_price=100.0,
    )
    assert evidence.observed_month_count == 2
    assert evidence.observed_payment_coverage == 2 / 12
    assert evidence.cut_count is None  # insufficient history never promotes an income signal
    # The formula is gross price return + gross distributions / starting price.
    assert evidence.price_return is None
    assert evidence.total_return is None
    assert len(evidence.monthly_distributions) == 2


def test_genuine_nav_is_the_only_nav_input_and_currency_mismatch_is_unavailable() -> None:
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
        listing=listing,
        events=events,
        period_start="2025-01-01",
        period_end="2025-12-31",
        denominator_price=110.0,
        start_price=100.0,
        genuine_nav_start=100.0,
        genuine_nav_end=98.0,
    )
    assert evidence.nav_erosion == pytest.approx(-0.02)
    assert evidence.total_return == pytest.approx(0.22)
    assert evidence.distribution_to_total_return_gap == pytest.approx(-0.1)
    mismatched = normalize_distribution_events(
        [
            *[
                {
                    "isin": "IE1",
                    "exchange": "X",
                    "code": "A",
                    "event_id": f"x{month}",
                    "payment_date": f"2025-{month:02d}-02",
                    "amount": 1.0,
                    "currency": "USD",
                }
                for month in range(1, 13)
            ]
        ],
        listing=listing,
    )
    assert (
        "currency_mismatch"
        in build_income_evidence(
            listing=listing,
            events=(*events, *mismatched),
            period_end="2025-12-31",
            denominator_price=100.0,
        ).availability_reasons
    )
