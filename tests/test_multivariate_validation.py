from collections.abc import Mapping, Sequence
from typing import Any

from portfell.multivariate_candidates import PortfolioCandidate
from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_validation import (
    ValidationSplit,
    WalkForwardPolicy,
    build_candidate_scorecards,
    validate_candidate_stress,
    validate_candidates,
)


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
    assert splits[0].pre_cost_return > 0.02  # canonical log returns compound into simple wealth
    assert splits[0].weights
    assert splits[0].conditional_value_at_risk is not None
    assert splits[0].test_observation_count == 2


def test_walk_forward_reports_insufficient_history_explicitly() -> None:
    splits = validate_candidates(
        candidates=[_candidate()], return_rows=[], policy=WalkForwardPolicy()
    )
    assert splits[0].status == "unavailable"
    assert splits[0].reason == "insufficient_walk_forward_history"


def test_walk_forward_refits_only_on_each_training_slice_and_persists_turnover() -> None:
    rows = [
        {
            "isin": "IE1",
            "exchange": "X",
            "code": "A",
            "date": f"2025-01-{day:02d}",
            "return": 0.01,
        }
        for day in range(1, 11)
    ]
    training_ends: list[str] = []

    def refit(training_rows: Sequence[Mapping[str, Any]]) -> list[PortfolioCandidate]:
        training_ends.append(str(training_rows[-1]["date"]))
        return [_candidate()]

    splits = validate_candidates(
        candidates=[_candidate()],
        return_rows=rows,
        policy=WalkForwardPolicy(minimum_training_observations=4, test_window_observations=2),
        candidate_factory=refit,
    )

    assert len(training_ends) == len(splits)
    assert all(end < split.test_start for end, split in zip(training_ends, splits, strict=True))
    assert splits[0].turnover == 1.0


def test_stress_and_scorecards_are_deterministic_and_do_not_select_a_winner() -> None:
    rows = [
        {
            "isin": "IE1",
            "exchange": "X",
            "code": "A",
            "date": f"2025-01-{day:02d}",
            "return": 0.01 if day % 2 else -0.02,
        }
        for day in range(1, 9)
    ]
    candidate = _candidate()
    policy = WalkForwardPolicy(minimum_training_observations=4, test_window_observations=2)
    splits = validate_candidates(candidates=[candidate], return_rows=rows, policy=policy)
    scenarios = validate_candidate_stress(candidates=[candidate], return_rows=rows, policy=policy)
    scorecards = build_candidate_scorecards(splits=splits, scenarios=scenarios)

    assert [item.scenario for item in scenarios] == [
        "historical",
        "seeded_block_bootstrap",
        "covariance_perturbation",
        "correlation_convergence",
        "distribution_cut",
    ]
    assert scenarios[-1].reason == "cash_flow_evidence_only"
    assert scorecards[0].candidate_id == candidate.candidate_id
    assert scorecards[0].scenario_count == len(scenarios)


def test_scorecard_keeps_split_only_candidate_visible() -> None:
    split = ValidationSplit(
        "split-a",
        "equal_weight",
        "2025-01-01",
        "2025-01-02",
        "2025-01-03",
        "2025-01-03",
        0.01,
        0.0,
        0.01,
        0.02,
        "complete",
        None,
        "candidate-a",
    )
    scorecards = build_candidate_scorecards(splits=[split], scenarios=[])
    assert scorecards[0].method == "equal_weight"
    assert scorecards[0].scenario_count == 0
