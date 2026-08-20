# pyright: reportMissingImports=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Dash callback registration for Multivariate Statistics."""

from __future__ import annotations

import re
from collections.abc import Mapping

from dash import Dash, Input, Output, State, ctx

from portfell.dash_ui.callbacks.multivariate_statistics.commands import optimizer_command_key
from portfell.dash_ui.core.gateway import DashResearchGateway
from portfell.dash_ui.core.ids import (
    MULTIVARIATE_NAMESPACE,
    OBJECTIVE_SELECTOR_ID,
    component_id,
)
from portfell.dash_ui.core.routes import WorkflowId
from portfell.dash_ui.core.run_control import (
    RunStatus,
    StatisticsRunControl,
    normalize_progress,
)
from portfell.multivariate.contracts.objectives import OptimizationObjective
from portfell.multivariate.contracts.settings import MultivariateOptimizationSettings

_PROJECT_PATH = re.compile(r"^/projects/([^/]+)/")


def _project_slug(pathname: str | None) -> str | None:
    match = _PROJECT_PATH.match(pathname or "")
    return None if match is None else match.group(1)


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _float_setting(row: Mapping[str, object], key: str, default: float) -> float:
    value = row.get(key)
    return float(value) if isinstance(value, (int, float)) else default


def _settings(
    persisted: Mapping[str, object],
    objective: str | None,
) -> MultivariateOptimizationSettings:
    selected = objective or str(
        persisted.get("objective") or OptimizationObjective.RETURN_RISK.value
    )
    frequencies_raw = persisted.get("allowed_distribution_frequencies")
    if isinstance(frequencies_raw, (list, tuple)):
        frequencies = tuple(str(value) for value in frequencies_raw)
    else:
        frequencies = ()
    holdings_raw = persisted.get("max_holdings")
    max_holdings = (
        holdings_raw
        if isinstance(holdings_raw, int) and not isinstance(holdings_raw, bool)
        else None
    )
    return MultivariateOptimizationSettings(
        objective=OptimizationObjective(selected),
        allowed_distribution_frequencies=frequencies,
        min_weight=_float_setting(persisted, "min_weight", 0.0),
        max_weight=_float_setting(persisted, "max_weight", 1.0),
        max_holdings=max_holdings,
        transaction_cost_rate=_float_setting(
            persisted,
            "transaction_cost_rate",
            0.0,
        ),
    )


def _settings_payload(
    settings: MultivariateOptimizationSettings,
) -> dict[str, object]:
    return {
        "objective": settings.objective.value,
        "allowed_distribution_frequencies": list(
            settings.allowed_distribution_frequencies
        ),
        "min_weight": settings.min_weight,
        "max_weight": settings.max_weight,
        "max_holdings": settings.max_holdings,
        "transaction_cost_rate": settings.transaction_cost_rate,
    }


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
        stage_id=WorkflowId.MULTIVARIATE_STATISTICS.value,
        status=status,
        phase=str(row.get("phase")) if row.get("phase") is not None else None,
        completed_units=completed_units,
        total_units=total_units,
        percent=percent,
        message=str(row.get("message")) if row.get("message") is not None else None,
        can_start=raw_status not in {"locked", "starting", "running"},
        failure_reason=failure_reason,
    )


def _outputs(
    control: StatisticsRunControl,
) -> tuple[float | None, str, str, bool]:
    return (
        control.percent,
        control.phase or control.status.value,
        control.failure_reason or "",
        control.status in {RunStatus.STARTING, RunStatus.RUNNING}
        or not control.can_start,
    )


def register_multivariate_callbacks(
    app: Dash,
    gateway: DashResearchGateway,
) -> None:
    """Register objective-aware start/poll behavior without browser-side analytics."""

    @app.callback(
        Output(component_id(MULTIVARIATE_NAMESPACE, "progress"), "value"),
        Output(component_id(MULTIVARIATE_NAMESPACE, "status"), "children"),
        Output(component_id(MULTIVARIATE_NAMESPACE, "failure"), "children"),
        Output(component_id(MULTIVARIATE_NAMESPACE, "optimize"), "disabled"),
        Input(component_id(MULTIVARIATE_NAMESPACE, "optimize"), "n_clicks"),
        Input("multivariate-status-poll", "n_intervals"),
        Input(OBJECTIVE_SELECTOR_ID, "value"),
        State("portfell-location", "pathname"),
    )
    def update_multivariate(
        n_clicks: int | None,
        _: int,
        objective: str | None,
        pathname: str | None,
    ) -> tuple[float | None, str, str, bool]:
        project_slug = _project_slug(pathname)
        if project_slug is None:
            return None, "unavailable", "project_unavailable", True

        persisted = _mapping(
            gateway.multivariate_settings(project_slug=project_slug)
        )
        settings = _settings(persisted, objective)
        persisted_objective = str(
            persisted.get("objective") or OptimizationObjective.RETURN_RISK.value
        )
        objective_changed = settings.objective.value != persisted_objective
        if ctx.triggered_id == OBJECTIVE_SELECTOR_ID and objective_changed:
            current = _control(
                gateway.run_status(
                    project_slug=project_slug,
                    stage_id=WorkflowId.MULTIVARIATE_STATISTICS,
                )
            )
            active = current.status in {RunStatus.STARTING, RunStatus.RUNNING}
            return current.percent, RunStatus.STALE.value, "", active

        status_row: Mapping[str, object]
        optimize_id = component_id(MULTIVARIATE_NAMESPACE, "optimize")
        if ctx.triggered_id == optimize_id and n_clicks:
            page = _mapping(
                gateway.page_view(
                    project_slug=project_slug,
                    workflow=WorkflowId.MULTIVARIATE_STATISTICS,
                )
            )
            input_row = _mapping(page.get("input"))
            upstream = input_row.get("bivariate_revision") or input_row.get(
                "bivariate_run_id"
            )
            if not isinstance(upstream, str) or not upstream:
                return None, "unavailable", "bivariate_revision_unavailable", True
            status_row = gateway.start_run(
                project_slug=project_slug,
                stage_id=WorkflowId.MULTIVARIATE_STATISTICS,
                command_key=optimizer_command_key(
                    project_slug=project_slug,
                    bivariate_revision=upstream,
                    settings=settings,
                ),
                settings=_settings_payload(settings),
            )
        else:
            status_row = gateway.run_status(
                project_slug=project_slug,
                stage_id=WorkflowId.MULTIVARIATE_STATISTICS,
            )
        return _outputs(_control(status_row))
