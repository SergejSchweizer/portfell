from __future__ import annotations

import pytest

from portfell.dash_ui.callbacks.multivariate_statistics.projections import replace_project_state
from portfell.dash_ui.core.plot_contracts import PROFESSIONAL_PLOTS
from portfell.dash_ui.core.routes import WORKFLOW_ORDER, WorkflowId
from portfell.dash_ui.figures.multivariate_statistics.models import (
    DecisionStageView,
    PortfolioCandidatePoint,
    WalkForwardView,
)
from portfell.dash_ui.integration.multivariate import (
    assert_multivariate_registry,
    build_multivariate_page_bundle,
)
from portfell.multivariate.contracts.common import DECISION_STAGE_ORDER


def test_pr274_registry_has_exactly_four_pages_and_one_multivariate_optimizer_stage() -> None:
    assert WORKFLOW_ORDER == (
        WorkflowId.METADATA_BUILDER,
        WorkflowId.UNIVARIATE_STATISTICS,
        WorkflowId.BIVARIATE_STATISTICS,
        WorkflowId.MULTIVARIATE_STATISTICS,
    )
    assert len(WORKFLOW_ORDER) == 4
    assert sum("multivariate" in workflow.value for workflow in WORKFLOW_ORDER) == 1
    assert_multivariate_registry()


def test_pr274_every_required_top_level_figure_uses_professional_plot_contract() -> None:
    assert [contract.title for contract in PROFESSIONAL_PLOTS] == [
        "Univariate Return / Risk Universe",
        "Bivariate Return / Diversification Universe",
        "Portfolio Candidate OOS Return / Risk",
    ]
    assert all(contract.responsive for contract in PROFESSIONAL_PLOTS)
    assert all(contract.accessible_description for contract in PROFESSIONAL_PLOTS)


def test_pr274_bundle_composes_candidate_decision_and_walk_forward_evidence() -> None:
    pytest.importorskip("dash")
    candidates = (
        PortfolioCandidatePoint("cfg-a", 0.12, 0.10, 1.2, True, "equal_weight", "sample"),
    )
    decisions = tuple(
        DecisionStageView(stage.value, "available", "fixture", ("cfg-a",), 0, {})
        for stage in DECISION_STAGE_ORDER
    )
    splits = (
        WalkForwardView(
            "wf-01",
            "2024-01-02",
            "2024-06-28",
            "2024-07-01",
            "2024-07-31",
            120,
            21,
        ),
    )
    bundle = build_multivariate_page_bundle(
        candidates=candidates,
        decisions=decisions,
        walk_forward=splits,
    )
    assert getattr(bundle.layout, "id", None) == "multivariate-page"
    assert bundle.candidate_figure["layout"]["title"] == "Portfolio Candidate OOS Return / Risk"
    assert bundle.decision_audit_figure["data"][0]["y"] == [
        stage.value for stage in DECISION_STAGE_ORDER
    ]
    assert bundle.walk_forward_figure["layout"]["title"] == (
        "Walk-Forward Training / Test Coverage"
    )


def test_pr274_project_switch_drops_old_project_response_before_replacement_paint() -> None:
    old = {"project_slug": "alpha", "winner": "alpha-winner"}
    assert replace_project_state(
        requested_project_slug="beta",
        received_project_slug="alpha",
        payload=old,
    ) is None
    new = {"project_slug": "beta", "winner": "beta-winner"}
    assert replace_project_state(
        requested_project_slug="beta",
        received_project_slug="beta",
        payload=new,
    ) == new
