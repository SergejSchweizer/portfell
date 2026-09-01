from portfell.univariate_distributions import build_metric_distributions


def test_metric_distributions_are_bounded_and_reconcile_counts() -> None:
    rows = [
        {"history_years": 1.0, "distribution_frequency": "monthly"},
        {"history_years": 2.0, "distribution_frequency": "quarterly"},
        {"history_years": None, "distribution_frequency": "monthly"},
    ]
    result = build_metric_distributions(rows)
    history = result["metrics"]["history_years"]
    assert history["available"] == 2
    assert history["unavailable"] == 1
    assert len(history["ecdf"]) <= 500
    frequency = result["metrics"]["distribution_frequency"]
    assert sum(item["count"] for item in frequency["categories"]) == 3
