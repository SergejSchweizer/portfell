from dataclasses import replace
from math import log
from types import SimpleNamespace
from typing import Any

import pytest

from portfell.multivariate_candidates import (
    METHODS,
    MonthlyDistributionEtfPortfolioPolicy,
    _aligned_matrix,  # pyright: ignore[reportPrivateUsage]
    _average_calendar_returns,  # pyright: ignore[reportPrivateUsage]
    _diversification_ratio,  # pyright: ignore[reportPrivateUsage]
    _highest_monthly_return_weights,  # pyright: ignore[reportPrivateUsage]
    _return_and_drawdown,  # pyright: ignore[reportPrivateUsage]
    _weights,  # pyright: ignore[reportPrivateUsage]
    build_candidate_set,
)
from portfell.multivariate_inputs import (
    MultivariateInputDependencies,
    MultivariateListingKey,
    build_multivariate_input_snapshot,
)
from portfell.multivariate_performance import build_multivariate_performance
from portfell.multivariate_risk_model import (
    RISK_MODEL_ARTIFACT_CONTRACT,
    MultivariateRiskModelArtifact,
)


def _keys() -> tuple[MultivariateListingKey, ...]:
    return tuple(MultivariateListingKey(f"IE{index}", "X", f"ETF{index}") for index in range(5))


def _snapshot():  # type: ignore[no-untyped-def]
    keys = _keys()
    dependencies = MultivariateInputDependencies(
        project_id="project-a",
        project_snapshot_id="snapshot-a",
        metadata_selection_id="metadata-a",
        univariate_run_id="univariate-a",
        univariate_selection_id="selection-a",
        bivariate_run_id="bivariate-a",
        bivariate_status="complete",
        bivariate_listing_keys=keys,
        aligned_calendar_id="calendar-a",
        bivariate_aligned_calendar_id="calendar-a",
        date_start="2024-01-01",
        date_end="2025-12-31",
        observation_count=504,
        quote_artifact_ids={key: f"q{index}" for index, key in enumerate(keys)},
        dividend_artifact_ids={key: f"d{index}" for index, key in enumerate(keys)},
    )
    return build_multivariate_input_snapshot(
        dependencies=dependencies,
        univariate_rows=[
            {
                "isin": key.isin,
                "exchange": key.exchange,
                "code": key.code,
                "instrument_type": "ETF",
                "distribution_frequency": "monthly",
            }
            for key in keys
        ],
    )


def _risk_model() -> MultivariateRiskModelArtifact:
    keys = _keys()
    return MultivariateRiskModelArtifact(
        risk_model_id="risk-a",
        input_snapshot_id="snapshot-a",
        contract_version=RISK_MODEL_ARTIFACT_CONTRACT,
        estimator="ledoit_wolf",
        return_type="log",
        window_policy="full",
        estimator_parameters=(),
        listings=keys,
        aligned_calendar_id="calendar-a",
        date_start="2024-01-01",
        date_end="2025-12-31",
        observation_count=504,
        covariance=tuple(
            tuple(0.01 if left == right else 0.001 for right in range(5)) for left in range(5)
        ),
        shrinkage_intensity=0.1,
        minimum_eigenvalue=0.009,
        condition_number=2.0,
        is_positive_semidefinite=True,
        availability_reasons=(),
        algorithm_version=1,
    )


def _returns() -> list[dict[str, object]]:
    return [
        {
            "isin": key.isin,
            "exchange": key.exchange,
            "code": key.code,
            "date": f"2025-01-{day:02d}",
            "return": 0.001 * (index + 1) * (-1 if day % 2 else 1),
        }
        for index, key in enumerate(_keys())
        for day in range(1, 25)
    ]


def test_candidate_set_has_stable_methods_and_no_silent_fallbacks() -> None:
    candidates = build_candidate_set(
        snapshot=_snapshot(), risk_model=_risk_model(), return_rows=_returns(), income={}
    )
    assert tuple(candidate.method for candidate in candidates) == METHODS
    assert candidates[0].baseline and candidates[1].baseline
    assert all(candidate.status in {"feasible", "unavailable"} for candidate in candidates)
    for candidate in candidates:
        if candidate.status == "feasible":
            assert abs(sum(weight for _, weight in candidate.weights) - 1) < 1e-9
            assert all(0 <= weight <= 0.2 for _, weight in candidate.weights)
            assert candidate.total_return is not None
            assert candidate.average_monthly_return is not None
            assert candidate.average_annual_return is not None
            assert candidate.max_drawdown is not None
            assert candidate.diversification_ratio is not None
            assert len(candidate.risk_contributions) == len(candidate.weights)
            assert (
                abs(
                    sum(item.percent_risk_contribution for item in candidate.risk_contributions) - 1
                )
                < 1e-9
            )
            assert all(
                item.listing == listing and item.weight == weight
                for item, (listing, weight) in zip(
                    candidate.risk_contributions, candidate.weights, strict=True
                )
            )


def test_candidate_realized_returns_match_weighted_simple_return_performance() -> None:
    rows = [
        {
            "isin": key.isin,
            "exchange": key.exchange,
            "code": key.code,
            "date": date,
            "return": log(1.0 + simple_return),
            "simple_return": simple_return,
        }
        for date, first_return in (("2025-01-02", 1.0), ("2025-01-03", 0.0))
        for index, key in enumerate(_keys())
        for simple_return in (first_return if index == 0 else 0.0,)
    ]
    candidates = build_candidate_set(
        snapshot=_snapshot(), risk_model=_risk_model(), return_rows=rows, income={}
    )
    equal_weight = next(candidate for candidate in candidates if candidate.method == "equal_weight")
    performance = build_multivariate_performance(candidates=(equal_weight,), return_rows=rows)[
        "portfolio_series"
    ][0]["values"]

    assert equal_weight.total_return == pytest.approx(0.20)
    assert equal_weight.average_monthly_return == pytest.approx(0.20)
    assert equal_weight.total_return == pytest.approx(performance[-1]["return"])


def test_highest_monthly_return_weights_maximize_mean_compounded_monthly_return() -> None:
    keys = tuple(key.as_tuple() for key in _keys()[:2])
    rows = [
        {
            "isin": keys[0][0],
            "exchange": keys[0][1],
            "code": keys[0][2],
            "date": "2025-01-02",
            "return": 0.10,
        },
        {
            "isin": keys[0][0],
            "exchange": keys[0][1],
            "code": keys[0][2],
            "date": "2025-01-03",
            "return": 0.10,
        },
        {
            "isin": keys[1][0],
            "exchange": keys[1][1],
            "code": keys[1][2],
            "date": "2025-01-02",
            "return": 0.15,
        },
        {
            "isin": keys[1][0],
            "exchange": keys[1][1],
            "code": keys[1][2],
            "date": "2025-01-03",
            "return": 0.00,
        },
    ]

    weights = _highest_monthly_return_weights(
        keys, rows, MonthlyDistributionEtfPortfolioPolicy(max_weight=0.6)
    )

    assert weights == pytest.approx((0.6, 0.4))


def test_average_calendar_returns_compound_before_averaging() -> None:
    monthly, annual = _average_calendar_returns(
        ("2024-01-02", "2024-02-01", "2025-01-02"), (0.1, 0.2, 0.3)
    )

    assert monthly == pytest.approx((0.1 + 0.2 + 0.3) / 3)
    assert annual == pytest.approx(((1.1 * 1.2) - 1 + 0.3) / 2)


def test_infeasible_bounds_remain_explicit_for_every_candidate() -> None:
    candidates = build_candidate_set(
        snapshot=_snapshot(),
        risk_model=_risk_model(),
        return_rows=_returns(),
        income={},
        policy=MonthlyDistributionEtfPortfolioPolicy(max_weight=0.19),
    )
    assert all(candidate.status == "unavailable" for candidate in candidates)
    assert {candidate.reasons for candidate in candidates} == {("infeasible_weight_bounds",)}


def test_candidate_policy_and_input_failures_are_explicit() -> None:
    with pytest.raises(ValueError, match="weights must satisfy"):
        MonthlyDistributionEtfPortfolioPolicy(min_weight=-0.1)
    with pytest.raises(ValueError, match="minimum_holding_count"):
        MonthlyDistributionEtfPortfolioPolicy(minimum_holding_count=1)

    snapshot = _snapshot()
    unavailable_snapshot = replace(snapshot, availability_reasons=("missing_quote_artifact",))
    candidates = build_candidate_set(
        snapshot=unavailable_snapshot, risk_model=_risk_model(), return_rows=_returns(), income={}
    )
    assert {candidate.reasons for candidate in candidates} == {("input_snapshot_unavailable",)}

    unavailable_risk = replace(_risk_model(), availability_reasons=("not_psd",))
    candidates = build_candidate_set(
        snapshot=snapshot, risk_model=unavailable_risk, return_rows=_returns(), income={}
    )
    assert {candidate.reasons for candidate in candidates} == {("risk_model_unavailable",)}

    too_small = replace(snapshot, listing_keys=snapshot.listing_keys[:1])
    candidates = build_candidate_set(
        snapshot=too_small, risk_model=_risk_model(), return_rows=_returns(), income={}
    )
    assert {candidate.reasons for candidate in candidates} == {("minimum_holding_count_not_met",)}


def test_candidate_set_reports_incomplete_return_history_without_fallback() -> None:
    candidates = build_candidate_set(
        snapshot=_snapshot(), risk_model=_risk_model(), return_rows=_returns()[:1], income={}
    )
    assert all(candidate.status == "unavailable" for candidate in candidates)
    assert {candidate.reasons for candidate in candidates} == {
        ("incomplete_aligned_return_history",)
    }


def test_candidate_helpers_keep_zero_variance_and_empty_history_unavailable() -> None:
    key = _keys()[0].as_tuple()
    with pytest.raises(ValueError, match="insufficient_aligned_return_history"):
        _aligned_matrix(
            (key,),
            [
                {
                    "isin": key[0],
                    "exchange": key[1],
                    "code": key[2],
                    "date": "2025-01-01",
                    "return": 0.0,
                }
            ],
        )
    assert _diversification_ratio((key,), (1.0,), {(key, key): 0.0}, 0.0) is None
    assert _return_and_drawdown(()) == (None, None)


def test_candidate_solver_failures_and_unknown_method_are_explicit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import portfell.multivariate_candidates as candidates_module

    keys = tuple(key.as_tuple() for key in _keys())
    covariance = {
        (left, right): 0.01 if left == right else 0.001 for left in keys for right in keys
    }
    policy = MonthlyDistributionEtfPortfolioPolicy()
    failed = SimpleNamespace(converged=False, weights=())

    def failed_solver(*args: object, **kwargs: object) -> Any:
        del args, kwargs
        return failed

    monkeypatch.setattr(candidates_module, "solve_minimum_variance", failed_solver)
    with pytest.raises(ValueError, match="minimum_variance_solver_not_converged"):
        _weights("minimum_variance", _keys(), covariance, _returns(), policy)
    monkeypatch.setattr(candidates_module, "solve_equal_risk_contribution", failed_solver)
    with pytest.raises(ValueError, match="equal_risk_contribution_solver_not_converged"):
        _weights("equal_risk_contribution", _keys(), covariance, _returns(), policy)
    monkeypatch.setattr(candidates_module, "solve_minimum_cvar", failed_solver)
    with pytest.raises(ValueError, match="minimum_cvar_solver_not_converged"):
        _weights("minimum_cvar", _keys(), covariance, _returns(), policy)
    with pytest.raises(ValueError, match="unsupported_candidate_method"):
        _weights("unsupported", _keys(), covariance, _returns(), policy)


def test_minimum_cvar_optimizes_weighted_simple_return_scenarios(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import portfell.multivariate_candidates as candidates_module

    keys = tuple(key.as_tuple() for key in _keys())
    covariance = {
        (left, right): 0.01 if left == right else 0.001 for left in keys for right in keys
    }
    rows = [
        {
            "isin": key.isin,
            "exchange": key.exchange,
            "code": key.code,
            "date": date,
            "return": log(1.0 + simple_return),
            "simple_return": simple_return,
        }
        for date, values in (
            ("2025-01-02", (0.10, 0.00, -0.05, 0.02, 0.03)),
            ("2025-01-03", (-0.10, 0.04, 0.01, -0.02, 0.00)),
        )
        for key, simple_return in zip(_keys(), values, strict=True)
    ]
    received_matrix: list[list[float]] = []

    def solver(matrix: list[list[float]], **kwargs: object) -> Any:
        del kwargs
        received_matrix.extend(matrix)
        return SimpleNamespace(converged=True, weights=(0.2,) * len(keys))

    monkeypatch.setattr(candidates_module, "solve_minimum_cvar", solver)

    _weights("minimum_cvar", _keys(), covariance, rows, MonthlyDistributionEtfPortfolioPolicy())

    assert received_matrix[0] == pytest.approx([0.10, 0.00, -0.05, 0.02, 0.03])
    assert received_matrix[1] == pytest.approx([-0.10, 0.04, 0.01, -0.02, 0.00])


def test_minimum_variance_uses_the_solver_default_convergence_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import portfell.multivariate_candidates as candidates_module

    keys = tuple(key.as_tuple() for key in _keys())
    covariance = {
        (left, right): 0.01 if left == right else 0.001 for left in keys for right in keys
    }
    received_kwargs: dict[str, object] = {}
    outcome = SimpleNamespace(converged=True, weights=(0.2,) * len(keys))

    def solver(*args: object, **kwargs: object) -> Any:
        del args
        received_kwargs.update(kwargs)
        return outcome

    monkeypatch.setattr(candidates_module, "solve_minimum_variance", solver)

    assert (
        _weights(
            "minimum_variance",
            _keys(),
            covariance,
            _returns(),
            MonthlyDistributionEtfPortfolioPolicy(),
        )
        == outcome.weights
    )
    assert "max_iterations" not in received_kwargs
