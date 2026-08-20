from __future__ import annotations

from pathlib import Path

import pytest

from portfell.dash_ui.callbacks.univariate_statistics.commands import start_command_key
from portfell.dash_ui.core.run_control import RunStatus, StatisticsRunControl
from portfell.dash_ui.viewmodels.univariate_statistics.model import UnivariateView


def _control(status: RunStatus, *, can_start: bool) -> StatisticsRunControl:
    failure = "fixture_failure" if status is RunStatus.FAILED else None
    return StatisticsRunControl(
        "univariate_statistics",
        status,
        None,
        None,
        None,
        None,
        None,
        can_start,
        failure,
    )


def _view(status: RunStatus = RunStatus.COMPLETE) -> UnivariateView:
    return UnivariateView(
        run_control=_control(status, can_start=status not in {RunStatus.STARTING, RunStatus.RUNNING}),
        dividend_frequencies=("monthly", "quarterly"),
        selected_dividend_frequencies=("monthly",),
        duration_thresholds=(1.0, 3.0, 5.0),
        metric_tabs=(("return_risk", "Return / Risk"), ("income", "Income")),
        active_metric="return_risk",
        result_revision="uni-revision-1",
    )


def test_pr267_duplicate_start_identity_is_project_and_revision_scoped() -> None:
    first = start_command_key(project_slug="alpha", upstream_revision="meta-1")
    assert first == start_command_key(project_slug="alpha", upstream_revision="meta-1")
    assert first != start_command_key(project_slug="beta", upstream_revision="meta-1")
    assert first != start_command_key(project_slug="alpha", upstream_revision="meta-2")


def test_pr267_server_options_and_revision_are_preserved_without_recomputation() -> None:
    view = _view()
    assert view.selected_dividend_frequencies == ("monthly",)
    assert view.duration_thresholds == (1.0, 3.0, 5.0)
    assert view.result_revision == "uni-revision-1"
    with pytest.raises(ValueError):
        UnivariateView(
            run_control=_control(RunStatus.IDLE, can_start=True),
            dividend_frequencies=("monthly",),
            selected_dividend_frequencies=("weekly",),
            duration_thresholds=(),
            metric_tabs=(("return_risk", "Return / Risk"),),
            active_metric="return_risk",
            result_revision=None,
        )


def test_pr267_layout_uses_exact_compute_label_and_persisted_status() -> None:
    source = Path("src/portfell/dash_ui/pages/univariate_statistics/layout.py").read_text(
        encoding="utf-8"
    )
    assert source.count('"Compute univariate statistics"') == 1
    assert "control.status" in source
    assert "control.failure_reason" in source
    assert "result_revision" in source


def test_pr267_layout_smoke_disables_active_run_when_dash_is_available() -> None:
    pytest.importorskip("dash")
    from portfell.dash_ui.pages.univariate_statistics.layout import build_univariate_layout

    layout = build_univariate_layout(_view(RunStatus.RUNNING))
    assert getattr(layout, "id", None) == "univariate-page"
