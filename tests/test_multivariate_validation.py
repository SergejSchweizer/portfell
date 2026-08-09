from portfell.multivariate_candidates import PortfolioCandidate
from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_validation import WalkForwardPolicy, validate_candidates


def _candidate() -> PortfolioCandidate:
    return PortfolioCandidate(
        "candidate-a",
        "equal_weight",
        True,
        "feasible",
        (),
        ((MultivariateListingKey("IE1", "X", "A"), 1.0),),
        0.01,
        0.1,
        None,
        None,
        1.0,
        1.0,
        1.0,
        None,
        None,
    )


def test_walk_forward_uses_only_dates_before_each_test_window() -> None:
    rows = [
        {"isin": "IE1", "exchange": "X", "code": "A", "date": f"2025-01-{day:02d}", "return": 0.01}
        for day in range(1, 9)
    ]
    splits = validate_candidates(
        candidates=[_candidate()],
        return_rows=rows,
        policy=WalkForwardPolicy(minimum_training_observations=4, test_window_observations=2),
    )
    assert all(split.train_end < split.test_start for split in splits)
    assert all(split.post_cost_return < split.pre_cost_return for split in splits)


def test_walk_forward_reports_insufficient_history_explicitly() -> None:
    splits = validate_candidates(
        candidates=[_candidate()], return_rows=[], policy=WalkForwardPolicy()
    )
    assert splits[0].status == "unavailable"
    assert splits[0].reason == "insufficient_walk_forward_history"
