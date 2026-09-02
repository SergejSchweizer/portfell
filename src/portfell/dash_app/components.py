"""Shared presentation primitives for every Portfell Dash page."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from dash import dcc, html
from dash.development.base_component import Component

from portfell.dash_app.state import JobPresentation

Content = Component | str | int | float


def PageHeader(title: str, subtitle: str) -> Component:
    return html.Header(
        [html.H1(title, className="pf-page-title"), html.P(subtitle, className="pf-page-subtitle")],
        className="pf-page-header",
    )


def ControlBar(children: Sequence[Content], *, component_id: str | None = None) -> Component:
    return html.Div(list(children), id=component_id, className="pf-control-bar")


def KpiCard(label: str, value: Content = "—", *, evidence: str | None = None) -> Component:
    children: list[Content] = [
        html.Div(label, className="pf-kpi-label"),
        html.Div(value, className="pf-kpi-value"),
    ]
    if evidence:
        children.append(html.Div(evidence, className="pf-kpi-evidence"))
    return html.Section(children, className="pf-kpi-card")


def _Card(title: str, body: Sequence[Content], *, class_name: str) -> Component:
    return html.Section(
        [html.H2(title, className="pf-card-title"), html.Div(list(body), className="pf-card-body")],
        className=f"pf-card {class_name}",
    )


def ChartCard(title: str, figure: Any | None = None, *, graph_id: str | None = None) -> Component:
    content: Component
    if figure is None:
        content = UnavailableData("Chart data is not available yet.")
    else:
        content = dcc.Graph(
            id=graph_id,
            figure=figure,
            config={"responsive": True, "displaylogo": False},
            className="pf-chart",
        )
    return _Card(title, [content], class_name="pf-chart-card")


def TableCard(title: str, body: Sequence[Content], *, component_id: str | None = None) -> Component:
    return html.Section(
        [
            html.H2(title, className="pf-card-title"),
            html.Div(list(body), id=component_id, className="pf-table-scroll"),
        ],
        className="pf-card pf-table-card",
    )


def StatusBanner(message: str, *, tone: str = "info") -> Component:
    allowed = {"info", "success", "danger"}
    normalized = tone if tone in allowed else "info"
    return html.Div(
        message,
        className=f"pf-status-banner pf-status-{normalized}",
        role="status" if normalized != "danger" else "alert",
    )


def HistoryCard(body: Sequence[Content], *, title: str = "Universe & History") -> Component:
    return _Card(title, body, class_name="pf-history-card")


def StageFooter(children: Sequence[Content]) -> Component:
    return html.Footer(list(children), className="pf-stage-footer")


def LoadingState(message: str = "Loading…") -> Component:
    return html.Div(message, className="pf-state pf-state-loading", role="status")


def EmptyState(message: str) -> Component:
    return html.Div(message, className="pf-state pf-state-empty")


def UnavailableData(message: str) -> Component:
    return html.Div(message, className="pf-state pf-state-unavailable")


def ErrorState(message: str) -> Component:
    return html.Div(message, className="pf-state pf-state-error", role="alert")


def JobProgress(job: JobPresentation) -> Component:
    """Accessible shared job-progress presentation backed only by persisted job state."""
    # Completed jobs are terminal evidence, not an active notification.  Keeping
    # the old progress card visible made a finished run look like ``0 / N`` and
    # caused a stale success toast to remain in the lower-right corner.
    if job.status in {None, "succeeded"}:
        return html.Div()
    stage = (job.stage or "Analysis").replace("_", " ").title()
    status = (job.status or "idle").replace("_", " ")
    phase = job.progress_phase.replace("_", " ") if job.progress_phase else None
    if job.status == "failed":
        detail = f"Failure: {job.failure_code or 'analysis_compute_failed'}"
    elif job.status == "cancelled":
        detail = "Cancelled"
    elif job.progress_total is not None and job.progress_current is not None:
        percentage = job.percentage or 0
        detail = f"{job.progress_current} / {job.progress_total} ({percentage:.0f}%)"
    else:
        detail = "Progress total is not available yet."
    progress: Component
    if job.progress_total is not None and job.progress_current is not None:
        progress = html.Div(
            html.Div(className="pf-job-progress-meter-fill"),
            className="pf-job-progress-meter",
            style={"--pf-progress": f"{job.percentage or 0:.3f}%"},
            **cast(
                Any,
                {
                    "role": "progressbar",
                    "aria-label": f"{stage} progress: {detail}",
                    "aria-valuenow": job.progress_current,
                    "aria-valuemax": job.progress_total,
                },
            ),
        )
    else:
        progress = html.Div(
            className="pf-job-progress-indeterminate",
            **cast(Any, {"aria-label": f"{stage} progress is indeterminate"}),
        )
    return html.Section(
        [
            html.Div(f"{stage}: {status}", className="pf-job-progress-title"),
            html.Div(
                phase or "Waiting for a persisted job phase.",
                className="pf-job-progress-phase",
            ),
            progress,
            html.Div(detail, className="pf-job-progress-detail"),
        ],
        id="pf-job-progress",
        className="pf-job-progress",
        role="status" if job.status not in {"failed", "cancelled"} else "alert",
        **cast(Any, {"aria-live": "polite"}),
    )


__all__ = [
    "ChartCard",
    "ControlBar",
    "EmptyState",
    "ErrorState",
    "HistoryCard",
    "JobProgress",
    "KpiCard",
    "LoadingState",
    "PageHeader",
    "StageFooter",
    "StatusBanner",
    "TableCard",
    "UnavailableData",
]
