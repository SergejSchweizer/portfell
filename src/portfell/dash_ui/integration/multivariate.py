"""Integration gate for the auditable Multivariate Statistics optimizer UI."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from portfell.dash_ui.figures.multivariate_statistics.audit import decision_audit_figure
from portfell.dash_ui.figures.multivariate_statistics.candidates import candidate_return_risk_figure
from portfell.dash_ui.figures.multivariate_statistics.history import walk_forward_history_figure
from portfell.dash_ui.figures.multivariate_statistics.models import (
    DecisionStageView,
    PortfolioCandidatePoint,
    WalkForwardView,
)
from portfell.dash_ui.pages.multivariate_statistics.layout import OBJECTIVE_OPTIONS, TAB_ORDER, build_multivariate_layout
from portfell.multivariate.contracts.common import DECISION_STAGE_ORDER


@dataclass(frozen=True, slots=True)
class MultivariatePageBundle:
    layout: object
    candidate_figure: dict[str, object]
    decision_audit_figure: dict[str, object]
    walk_forward_figure: dict[str, object]


def assert_multivariate_registry() -> None:
    """Fail fast when independent siblings drift from frozen product contracts."""

    if tuple(value for value, _ in OBJECTIVE_OPTIONS) != (
        "return_risk",
        "return_drawdown",
        "minimum_risk",
    ):
        raise ValueError("Multivariate objective registry drift")
    if tuple(value for value, _ in TAB_ORDER) != (
        "universe",
        "risk_model",
        "optimization",
        "validation",
        "final_portfolio",
    ):
        raise ValueError("Multivariate tab registry drift")
    if len(DECISION_STAGE_ORDER) != 8:
        raise ValueError("Decision Audit must expose exactly eight stages")


def build_multivariate_page_bundle(
    *,
    candidates: Iterable[PortfolioCandidatePoint],
    decisions: Iterable[DecisionStageView],
    walk_forward: Iterable[WalkForwardView],
) -> MultivariatePageBundle:
    """Compose child layout/figures without altering their calculations or semantics."""

    assert_multivariate_registry()
    return MultivariatePageBundle(
        layout=build_multivariate_layout(),
        candidate_figure=candidate_return_risk_figure(candidates),
        decision_audit_figure=decision_audit_figure(decisions),
        walk_forward_figure=walk_forward_history_figure(walk_forward),
    )
