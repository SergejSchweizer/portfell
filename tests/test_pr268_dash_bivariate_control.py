from __future__ import annotations

from pathlib import Path

import pytest

from portfell.dash_ui.callbacks.bivariate_statistics.commands import start_command_key
from portfell.dash_ui.core.run_control import RunStatus, StatisticsRunControl
from portfell.dash_ui.viewmodels.bivariate_statistics.model import BivariateView, DETAIL_VIEWS


def _control(status: RunStatus, *, can_start: bool) -> StatisticsRunControl:
    failure = "fixture_failure" if status is RunStatus.FAILED else None
    return StatisticsRunControl(
        "bivariate_statistics",
        status,
        None,
        None,
        None,
        None,
        None,
        can_start,
        failure,
    )


def test_pr268_detail_view_registry_is_exact_and_frozen() -> None:
    assert [view_id for view_id, _ in DETAIL_VIEWS] == [
        "covariance",
        "pearson",
        "spearman",
        "downside",
        "tail_dependence",
        "co_exceedance",
        "rolling_correlation",
        "drawdown_overlap",
        "tail_risk_scatter",
    ]
    assert len(DETAIL_VIEWS) == 9
    with pytest.raises(ValueError, match="registry is frozen"):
        BivariateView(
            run_control=_control(RunStatus.IDLE, can_start=True),
            upstream_revision="uni-1",
            detail_views=DETAIL_VIEWS[:-1],
        )


def test_pr268_duplicate_start_identity_is_project_and_revision_scoped() -> None:
    first = start_command_key(project_slug="alpha", univariate_revision="uni-1")
    assert first == start_command_key(project_slug="alpha", univariate_revision="uni-1")
    assert first != start_command_key(project_slug="beta", univariate_revision="uni-1")
    assert first != start_command_key(project_slug="alpha", univariate_revision="uni-2")


def test_pr268_layout_uses_exact_compute_label_and_no_pairwise_formula() -> None:
    source = Path("src/portfell/dash_ui/pages/bivariate_statistics/layout.py").read_text(
        encoding="utf-8"
    )
    assert source.count('"Compute bivariate statistics"') == 1
    assert "control.status" in source
    assert "control.failure_reason" in source
    forbidden = ("covariance(", "pearsonr(", "spearmanr(", "corrcoef(")
    assert not any(token in source for token in forbidden)


def test_pr268_layout_smoke_when_dash_dependency_is_available() -> None:
    pytest.importorskip("dash")
    from portfell.dash_ui.pages.bivariate_statistics.layout import build_bivariate_layout

    view = BivariateView(
        run_control=_control(RunStatus.COMPLETE, can_start=True),
        upstream_revision="uni-1",
    )
    layout = build_bivariate_layout(view)
    assert getattr(layout, "id", None) == "bivariate-page"
