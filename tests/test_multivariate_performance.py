import pytest

from portfell.multivariate_candidates import PortfolioCandidate
from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_performance import build_multivariate_performance


def test_performance_compounds_instrument_and_portfolio_calendar_returns() -> None:
    alpha = MultivariateListingKey("IE00ALPHA", "XETRA", "ALPHA")
    beta = MultivariateListingKey("IE00BETA", "XETRA", "BETA")
    candidate = PortfolioCandidate(
        candidate_id="equal",
        method="equal_weight",
        baseline=True,
        status="feasible",
        reasons=(),
        weights=((alpha, 0.5), (beta, 0.5)),
        variance=0.0,
        volatility=0.0,
        var=0.0,
        cvar=0.0,
        maximum_weight=0.5,
        herfindahl_index=0.5,
        effective_holding_count=2.0,
        gross_ttm_distribution_yield=None,
        gross_monthly_distribution=None,
        total_return=0.0,
        max_drawdown=0.0,
        diversification_ratio=1.0,
        risk_contributions=(),
    )
    rows = (
        {
            "isin": "IE00ALPHA",
            "exchange": "XETRA",
            "code": "ALPHA",
            "date": "2024-01-02",
            "simple_return": 0.10,
        },
        {
            "isin": "IE00ALPHA",
            "exchange": "XETRA",
            "code": "ALPHA",
            "date": "2024-01-03",
            "simple_return": -0.10,
        },
        {
            "isin": "IE00ALPHA",
            "exchange": "XETRA",
            "code": "ALPHA",
            "date": "2024-02-01",
            "simple_return": 0.10,
        },
        {
            "isin": "IE00BETA",
            "exchange": "XETRA",
            "code": "BETA",
            "date": "2024-01-02",
            "simple_return": 0.00,
        },
        {
            "isin": "IE00BETA",
            "exchange": "XETRA",
            "code": "BETA",
            "date": "2024-01-03",
            "simple_return": 0.20,
        },
        {
            "isin": "IE00BETA",
            "exchange": "XETRA",
            "code": "BETA",
            "date": "2024-02-01",
            "simple_return": 0.00,
        },
    )

    performance = build_multivariate_performance(candidates=(candidate,), return_rows=rows)

    assert performance["instrument_series"][0]["values"] == [
        {"date": "2024-01-03", "return": pytest.approx(-0.01)},
        {"date": "2024-02-01", "return": pytest.approx(0.089)},
    ]
    assert performance["portfolio_series"][0]["values"] == [
        {"date": "2024-01-03", "return": pytest.approx(0.1025)},
        {"date": "2024-02-01", "return": pytest.approx(0.157625)},
    ]
    assert performance["period_returns"] == [
        {
            "candidate_id": "equal",
            "method": "equal_weight",
            "period": "monthly",
            "label": "2024-01",
            "return": pytest.approx(0.1025),
        },
        {
            "candidate_id": "equal",
            "method": "equal_weight",
            "period": "monthly",
            "label": "2024-02",
            "return": pytest.approx(0.05),
        },
        {
            "candidate_id": "equal",
            "method": "equal_weight",
            "period": "annual",
            "label": "2024",
            "return": pytest.approx(0.157625),
        },
    ]
