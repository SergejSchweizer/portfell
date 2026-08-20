# pyright: reportMissingImports=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Dash callback registration for Univariate Statistics."""

from __future__ import annotations

import re
from collections.abc import Mapping

from dash import Dash, Input, Output, State, ctx

from portfell.dash_ui.callbacks.univariate_statistics.commands import start_command_key
from portfell.dash_ui.core.gateway import DashResearchGateway
from portfell.dash_ui.core.ids import UNIVARIATE_NAMESPACE, component_id
from portfell.dash_ui.core.routes import WorkflowId
from portfell.dash_ui.core.run_control import RunStatus, StatisticsRunControl, normalize_progress

_PROJECT_PATH = re.compile(r"^/projects/([^/]+)/")


def _project_slug(pathname: str | None) -> str | None:
    match = _PROJECT_PATH.match(pathname or "")
    return None if match is None else match.group(1)


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _control(row: Mapping[str, object]) -> StatisticsRunControl:
    raw_status = str(row.get("status") or "idle")
    status = {
        "ready": RunStatus.IDLE,
        "locked": RunStatus.IDLE,
        "idle": RunStatus.IDLE,
        "starting": RunStatus.STARTING,
        "running": RunStatus.RUNNING,
        "complete": RunStatus.COMPLETE,
        "succeeded": RunStatus.COMPLETE,
        "failed": RunStatus.FAILED,
        "stale": RunStatus.STALE,
    }.get(raw_status, RunStatus.IDLE)
    completed = row.get("completed_units", row.get("completed"))
    total = row.get("total_units", row.get("total"))
    completed_units = completed if isinstance(completed, int) else None
    total_units = total if isinstance(total, int) else None
    raw_percent = row.get("percent")
    percent = (
        float(raw_percent)
        if isinstance(raw_percent, (int, float))
        else normalize_progress(completed_units, total_units)
    )
    raw_failure = row.get("failure_reason") or row.get("error_code")
    failure_reason = str(raw_failure) if raw_failure is not None else None
    if status is RunStatus.FAILED and failure_reason is None:
        failure_reason = "calculation_failed"
    return StatisticsRunControl(
        stage_id=WorkflowId.UNIVARIATE_STATISTICS.value,
        status=status,
        phase=str(row.get("phase")) if row.get("phase") is not None else None,
        completed_units=completed_units,
        total_units=total_units,
        percent=percent,
        message=str(row.get("message")) if row.get("message") is not None else None,
        can_start=raw_status not in {"locked", "starting", "running"},
        failure_reason=failure_reason,
    )


def _outputs(control: StatisticsRunControl) -> tuple[float | None, str, str, bool]:
    return (
        control.percent,
        control.phase or control.status.value,
        control.failure_reason or "",
        control.status in {RunStatus.STARTING, RunStatus.RUNNING} or not control.can_start,
    )


def register_univariate_callbacks(app: Dash, gateway: DashResearchGateway) -> None:
    """Register explicit start/poll behavior with duplicate-start convergence."""

    @app.callback(
        Output(component_id(UNIVARIATE_NAMESPACE, "progress"), "value"),
        Output(component_id(UNIVARIATE_NAMESPACE, "status"), "children"),
        Output(component_id(UNIVARIATE_NAMESPACE, "failure"), "children"),
        Output(component_id(UNIVARIATE_NAMESPACE, "compute"), "disabled"),
        Input(component_id(UNIVARIATE_NAMESPACE, "compute"), "n_clicks"),
        Input("univariate-status-poll", "n_intervals"),
        State(component_id(UNIVARIATE_NAMESPACE, "dividend-frequency"), "value"),
        State("portfell-location", "pathname"),
    )
    def update_univariate(
        n_clicks: int | None,
        _: int,
        dividend_frequencies: list[str] | None,
        pathname: str | None,
    ) -> tuple[float | None, str, str, bool]:
        project_slug = _project_slug(pathname)
        if project_slug is None:
            return None, "unavailable", "project_unavailable", True

        status_row: Mapping[str, object]
        if ctx.triggered_id == component_id(UNIVARIATE_NAMESPACE, "compute") and n_clicks:
            page = _mapping(
                gateway.page_view(
                    project_slug=project_slug,
                    workflow=WorkflowId.UNIVARIATE_STATISTICS,
                )
            )
            upstream = _mapping(page.get("input")).get("metadata_selection_id")
            if not isinstance(upstream, str) or not upstream:
                return None, "unavailable", "metadata_selection_unavailable", True
            status_row = gateway.start_run(
                project_slug=project_slug,
                stage_id=WorkflowId.UNIVARIATE_STATISTICS,
                command_key=start_command_key(
                    project_slug=project_slug,
                    upstream_revision=upstream,
                ),
                settings={"dividend_frequencies": tuple(dividend_frequencies or ())},
            )
        else:
            status_row = gateway.run_status(
                project_slug=project_slug,
                stage_id=WorkflowId.UNIVARIATE_STATISTICS,
            )
        return _outputs(_control(status_row))
