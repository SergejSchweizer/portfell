from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from dash.development.base_component import Component

from portfell.dash_app.app import create_dash_app
from portfell.dash_app.callbacks import CallbackService, refresh_job_presentation
from portfell.dash_app.components import JobProgress
from portfell.dash_app.shell import root_layout
from portfell.dash_app.state import (
    BrowserState,
    JobPresentation,
    browser_state_from_workflow,
    with_job_status,
)


class JobReadOnlyService:
    def __init__(self) -> None:
        self.job_reads = 0

    def workflow_state(self) -> dict[str, object]:
        raise AssertionError("job polling must not reconstruct workflow state")

    def analysis_job_status(self, job_id: str) -> dict[str, object]:
        self.job_reads += 1
        assert job_id == "job-a"
        return {
            "job_id": "job-a",
            "stage": "univariate",
            "status": "running",
            "run_id": None,
            "progress_current": 4,
            "progress_total": 10,
            "progress_phase": "members",
            "failure_code": None,
        }

    def active_analysis_job(self) -> dict[str, object] | None:
        raise AssertionError("known job IDs must use direct job reads")

    def create_metadata_universe(self, **filters: object) -> object:
        raise AssertionError("not part of job polling")

    def run_univariate(self, universe_id: str) -> dict[str, object]:
        raise AssertionError("not part of job polling")

    def create_univariate_selection(
        self, run_id: str, *, predicates: Mapping[str, object] | None = None
    ) -> object:
        raise AssertionError("not part of job polling")

    def run_bivariate(self, selection_id: str) -> dict[str, object]:
        raise AssertionError("not part of job polling")

    def run_multivariate(
        self, *, selection_id: str, bivariate_run_id: str, objective: str = "return_risk"
    ) -> dict[str, object]:
        raise AssertionError("not part of job polling")


def _tree(component: object) -> str:
    if isinstance(component, Component):
        return _tree(cast(Mapping[str, object], component.to_plotly_json()))
    if isinstance(component, Mapping):
        return " ".join(_tree(value) for value in cast(Mapping[str, object], component).values())
    if isinstance(component, list | tuple):
        values = cast(list[object] | tuple[object, ...], component)
        return " ".join(_tree(value) for value in values)
    return str(component)


def test_job_poll_reads_only_the_persisted_job_record() -> None:
    service = JobReadOnlyService()
    state = BrowserState(job=JobPresentation(job_id="job-a", status="running"))
    updated = refresh_job_presentation(cast(CallbackService, service), state)
    assert service.job_reads == 1
    assert updated.job.progress_current == 4
    assert updated.job.progress_total == 10
    assert updated.job.percentage == 40


def test_workflow_state_recovers_rich_job_presentation_after_reload() -> None:
    state = browser_state_from_workflow(
        {
            "workspace_id": "default",
            "metadata_universe": None,
            "univariate_selection": None,
            "stages": {},
            "active_job": {
                "job_id": "job-a",
                "stage": "bivariate",
                "status": "failed",
                "run_id": "run-a",
                "progress_current": 3,
                "progress_total": 10,
                "progress_phase": "pairs",
                "failure_code": "analysis_compute_failed",
            },
        }
    )
    assert state.job.job_id == "job-a"
    assert state.job.failure_code == "analysis_compute_failed"
    assert state.job.terminal


def test_job_state_fails_closed_for_missing_or_invalid_presentation_fields() -> None:
    state = BrowserState.from_store(None)
    assert state.job.percentage is None
    assert with_job_status(state, None) is state
    assert with_job_status(state, {"status": "unknown"}) is state


def test_shared_progress_is_accessible_for_known_and_indeterminate_progress() -> None:
    known = _tree(
        JobProgress(
            JobPresentation(
                stage="univariate",
                status="running",
                progress_current=5,
                progress_total=10,
                progress_phase="members",
            )
        )
    )
    assert "5 / 10 (50%)" in known
    assert "progressbar" in known
    unknown = _tree(JobProgress(JobPresentation(stage="bivariate", status="running")))
    assert "Progress total is not available yet." in unknown
    failed = _tree(
        JobProgress(
            JobPresentation(
                stage="multivariate", status="failed", failure_code="analysis_compute_failed"
            )
        )
    )
    assert "Failure: analysis_compute_failed" in failed


def test_route_rendering_has_only_navigation_input_and_polling_is_one_second() -> None:
    app = create_dash_app(services=cast(Any, JobReadOnlyService()))
    callback_map = cast(dict[str, Mapping[str, object]], cast(Any, app).callback_map)
    route = callback_map["pf-route-content.children"]
    assert route["inputs"] == [{"id": "pf-location", "property": "pathname"}]
    layout = _tree(root_layout())
    assert "pf-job-progress-region" in layout
    assert "1000" in layout
