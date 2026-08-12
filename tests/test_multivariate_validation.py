from collections.abc import Mapping, Sequence
from random import Random
from typing import Any

from portfell.multivariate_candidates import PortfolioCandidate
from portfell.multivariate_inputs import MultivariateListingKey
from portfell.multivariate_validation import (
    ValidationSplit,
    WalkForwardPolicy,
    _portfolio_returns_by_date,  # pyright: ignore[reportPrivateUsage]
    _seeded_block_bootstrap,  # pyright: ignore[reportPrivateUsage]
    _sortino,  # pyright: ignore[reportPrivateUsage]
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


def test_default_walk_forward_policy_starts_after_one_hundred_observations() -> None:
    rows = [
        {
            "isin": "IE1",
            "exchange": "X",
            "code": "A",
            "date": f"2025-{index // 28 + 1:02d}-{index % 28 + 1:02d}",
            "return": 0.01,
        }
        for index in range(121)
    ]

    splits = validate_candidates(candidates=[_candidate()], return_rows=rows)

    assert len(splits) == 1
    assert splits[0].status == "complete"
    assert splits[0].test_observation_count == 21


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


def test_walk_forward_uses_precomputed_refits_in_chronological_turnover_order() -> None:
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
    splits = validate_candidates(
        candidates=[_candidate()],
        return_rows=rows,
        policy=WalkForwardPolicy(minimum_training_observations=4, test_window_observations=2),
        precomputed_candidates=[[_candidate()], [_candidate()], [_candidate()]],
    )

    assert len(splits) == 3
    assert [split.turnover for split in splits] == [1.0, 0.0, 0.0]
    assert [split.transaction_cost for split in splits] == [0.0005, 0.0, 0.0]


def test_walk_forward_caps_refits_across_the_full_history() -> None:
    rows = [
        {
            "isin": "IE1",
            "exchange": "X",
            "code": "A",
            "date": f"2025-01-{day:02d}",
            "return": 0.01,
        }
        for day in range(1, 21)
    ]
    policy = WalkForwardPolicy(
        minimum_training_observations=4,
        test_window_observations=2,
        maximum_refit_count=3,
    )
    training_ends: list[str] = []

    def refit(training_rows: Sequence[Mapping[str, Any]]) -> list[PortfolioCandidate]:
        training_ends.append(str(training_rows[-1]["date"]))
        return [_candidate()]

    splits = validate_candidates(
        candidates=[_candidate()], return_rows=rows, policy=policy, candidate_factory=refit
    )

    assert len(splits) == 3
    assert training_ends == ["2025-01-04", "2025-01-10", "2025-01-18"]


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


def test_validation_keeps_unavailable_candidates_and_empty_scenarios_explicit() -> None:
    unavailable = PortfolioCandidate(
        "candidate-unavailable",
        "minimum_variance",
        False,
        "unavailable",
        ("risk_model_unavailable",),
        (),
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    policy = WalkForwardPolicy(minimum_training_observations=2, test_window_observations=2)
    rows = [
        {"isin": "IE1", "exchange": "X", "code": "A", "date": f"2025-01-{day:02d}", "return": 0.01}
        for day in range(1, 6)
    ]
    splits = validate_candidates(
        candidates=[_candidate()], return_rows=rows, policy=policy, candidate_factory=lambda _: []
    )
    assert splits and splits[0].reason == "candidate_unavailable"
    scenarios = validate_candidate_stress(candidates=[unavailable], return_rows=[], policy=policy)
    assert len(scenarios) == 5
    assert {scenario.status for scenario in scenarios} == {"unavailable"}


def test_validation_handles_empty_returns_and_single_observation_metrics() -> None:
    candidate = _candidate()
    policy = WalkForwardPolicy(minimum_training_observations=1, test_window_observations=1)
    rows = [
        {"isin": "IE1", "exchange": "X", "code": "A", "date": "2025-01-01", "return": 0.01},
        {"isin": "IE1", "exchange": "X", "code": "A", "date": "2025-01-02", "return": 0.01},
    ]
    splits = validate_candidates(candidates=[candidate], return_rows=rows, policy=policy)
    assert splits[0].volatility is None
    assert splits[0].sharpe_ratio is None
    assert splits[0].sortino_ratio is None
    scenarios = validate_candidate_stress(candidates=[candidate], return_rows=[], policy=policy)
    assert all(scenario.status == "available_with_warning" for scenario in scenarios)


def test_validation_helpers_preserve_unavailable_and_empty_boundaries() -> None:
    unavailable = PortfolioCandidate(
        "candidate-unavailable",
        "minimum_variance",
        False,
        "unavailable",
        ("risk_model_unavailable",),
        (),
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    assert _portfolio_returns_by_date((unavailable,), []) == {"minimum_variance": {}}
    assert _seeded_block_bootstrap((), 0, Random(1)) == ()
    assert _sortino(()) is None
