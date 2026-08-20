from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from portfell.dash_ui.callbacks.multivariate_statistics.commands import optimizer_command_key
from portfell.dash_ui.callbacks.multivariate_statistics.projections import (
    lazy_section_payload,
    replace_project_state,
)
from portfell.dash_ui.core.run_control import RunStatus, StatisticsRunControl
from portfell.dash_ui.viewmodels.multivariate_statistics.model import MultivariateView
from portfell.multivariate.contracts.objectives import OptimizationObjective
from portfell.multivariate.contracts.settings import MultivariateOptimizationSettings


def _control() -> StatisticsRunControl:
    return StatisticsRunControl(
        "multivariate_statistics",
        RunStatus.COMPLETE,
        "publish_decisions",
        7,
        7,
        100.0,
        "Complete",
        True,
    )


def _fresh_view() -> MultivariateView:
    draft = MultivariateView(
        run_control=_control(),
        objective=OptimizationObjective.RETURN_RISK,
        min_weight=0.0,
        max_weight=0.6,
        max_holdings=20,
        transaction_cost_rate=0.001,
    )
    return replace(
        draft,
        result_revision="multi-1",
        result_objective=draft.objective,
        result_settings_signature=draft.settings_signature,
    )


def test_pr289_exposes_exactly_three_objectives_with_return_risk_default() -> None:
    view = MultivariateView(run_control=_control())
    assert view.objective is OptimizationObjective.RETURN_RISK
    assert view.objective_options == (
        ("return_risk", "Return / Risk"),
        ("return_drawdown", "Return / Drawdown"),
        ("minimum_risk", "Minimum Risk"),
    )


def test_pr289_objective_and_any_constraint_change_marks_result_stale_without_start() -> None:
    fresh = _fresh_view()
    assert fresh.result_is_stale is False
    assert replace(fresh, objective=OptimizationObjective.MINIMUM_RISK).result_is_stale is True
    for changes in (
        {"min_weight": 0.05},
        {"max_weight": 0.5},
        {"max_holdings": 10},
        {"transaction_cost_rate": 0.002},
    ):
        assert replace(fresh, **changes).result_is_stale is True
    source = Path(
        "src/portfell/dash_ui/viewmodels/multivariate_statistics/model.py"
    ).read_text(encoding="utf-8")
    assert "start_run" not in source


def test_pr289_duplicate_activation_converges_on_one_project_revision_settings_key() -> None:
    settings = MultivariateOptimizationSettings(
        objective=OptimizationObjective.RETURN_RISK,
        max_weight=0.6,
        max_holdings=20,
    )
    first = optimizer_command_key(
        project_slug="alpha",
        bivariate_revision="bi-1",
        settings=settings,
    )
    assert first == optimizer_command_key(
        project_slug="alpha",
        bivariate_revision="bi-1",
        settings=settings,
    )
    assert first != optimizer_command_key(
        project_slug="beta",
        bivariate_revision="bi-1",
        settings=settings,
    )


def test_pr289_project_switch_drops_late_old_project_payload_before_paint() -> None:
    payload = {"run_id": "old-run", "winner": "old-winner"}
    assert (
        replace_project_state(
            requested_project_slug="beta",
            received_project_slug="alpha",
            payload=payload,
        )
        is None
    )
    assert replace_project_state(
        requested_project_slug="beta",
        received_project_slug="beta",
        payload={"run_id": "new-run"},
    ) == {"run_id": "new-run"}


def test_pr289_lazy_section_uses_persisted_reason_or_typed_unavailable() -> None:
    sections = (
        {
            "stage": "winner_selection",
            "availability": "available",
            "reason": "objective_winner",
        },
    )
    assert lazy_section_payload(section_id="winner_selection", sections=sections) == sections[0]
    assert lazy_section_payload(section_id="risk_model_candidates", sections=sections) == {
        "availability": "unavailable",
        "reason": "section_not_persisted",
        "stage": "risk_model_candidates",
    }
