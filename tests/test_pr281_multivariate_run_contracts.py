from __future__ import annotations

from dataclasses import fields

import pytest

from portfell.multivariate.contracts.objectives import (
    DEFAULT_OBJECTIVE,
    OBJECTIVES,
    OptimizationObjective,
)
from portfell.multivariate.contracts.runs import (
    PROGRESS_PHASE_ORDER,
    MultivariateProgressPhase,
    MultivariateRunIdentity,
)
from portfell.multivariate.contracts.settings import MultivariateOptimizationSettings


def test_pr281_objective_registry_is_exact_with_return_risk_default() -> None:
    assert tuple(OptimizationObjective) == (
        OptimizationObjective.RETURN_RISK,
        OptimizationObjective.RETURN_DRAWDOWN,
        OptimizationObjective.MINIMUM_RISK,
    )
    assert DEFAULT_OBJECTIVE is OptimizationObjective.RETURN_RISK
    assert [OBJECTIVES[item].label for item in OptimizationObjective] == [
        "Return / Risk",
        "Return / Drawdown",
        "Minimum Risk",
    ]


def test_pr281_progress_phase_registry_is_exact() -> None:
    assert PROGRESS_PHASE_ORDER == (
        MultivariateProgressPhase.SELECT_UNIVERSE,
        MultivariateProgressPhase.ESTIMATE_RISK_MODELS,
        MultivariateProgressPhase.BUILD_CANDIDATES,
        MultivariateProgressPhase.WALK_FORWARD,
        MultivariateProgressPhase.SELECT_WINNER,
        MultivariateProgressPhase.FINAL_REFIT,
        MultivariateProgressPhase.PUBLISH_DECISIONS,
    )


def test_pr281_settings_expose_constraints_but_no_manual_isin_or_method_selector() -> None:
    names = {item.name for item in fields(MultivariateOptimizationSettings)}
    assert "objective" in names
    assert "min_weight" in names
    assert "max_weight" in names
    assert "max_holdings" in names
    assert not any("isin" in name or "method" in name for name in names)
    with pytest.raises(ValueError):
        MultivariateOptimizationSettings(min_weight=0.8, max_weight=0.2)


def test_pr281_logical_run_identity_is_deterministic_and_objective_sensitive() -> None:
    base = dict(
        project_slug="alpha",
        bivariate_revision="bi-1",
        settings_version="settings-v1",
        algorithm_version="algo-v1",
    )
    first = MultivariateRunIdentity(
        settings=MultivariateOptimizationSettings(objective=OptimizationObjective.RETURN_RISK),
        **base,
    )
    same = MultivariateRunIdentity(
        settings=MultivariateOptimizationSettings(objective=OptimizationObjective.RETURN_RISK),
        **base,
    )
    other = MultivariateRunIdentity(
        settings=MultivariateOptimizationSettings(objective=OptimizationObjective.MINIMUM_RISK),
        **base,
    )
    assert first.logical_run_id == same.logical_run_id
    assert first.logical_run_id != other.logical_run_id


def test_pr281_unknown_objective_id_fails_closed() -> None:
    with pytest.raises(ValueError):
        OptimizationObjective("unknown")
