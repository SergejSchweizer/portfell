from portfell.app_services.research_compute import ComputedRun, filtered_univariate_selection


def test_metric_filters_use_or_within_category_and_and_between_metrics() -> None:
    run = ComputedRun(
        run_id="run",
        source_id="source",
        algorithm_version="v3",
        rows=(
            {
                "isin": "A",
                "exchange": "X",
                "code": "A",
                "distribution_frequency": "monthly",
                "sharpe": 1.0,
            },
            {
                "isin": "B",
                "exchange": "X",
                "code": "B",
                "distribution_frequency": "quarterly",
                "sharpe": 0.5,
            },
            {
                "isin": "C",
                "exchange": "X",
                "code": "C",
                "distribution_frequency": "annual",
                "sharpe": 1.2,
            },
        ),
    )
    selection = filtered_univariate_selection(
        run,
        [
            {
                "metric": "distribution_frequency",
                "operator": "in",
                "allowed": ["monthly", "quarterly"],
            },
            {"metric": "sharpe", "operator": ">=", "value": 0.75},
        ],
    )
    assert selection.member_ids == ("A:X:A",)
