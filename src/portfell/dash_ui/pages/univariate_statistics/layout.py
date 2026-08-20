# pyright: reportMissingImports=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Univariate calculation surface and result-tab layout."""

from __future__ import annotations

from dash import dcc, html

from portfell.dash_ui.core.ids import UNIVARIATE_NAMESPACE, component_id
from portfell.dash_ui.core.run_control import RunStatus
from portfell.dash_ui.viewmodels.univariate_statistics.model import UnivariateView


def build_univariate_layout(view: UnivariateView) -> object:
    """Render server-owned Univariate state without financial recomputation."""

    control = view.run_control
    active = control.status in {RunStatus.STARTING, RunStatus.RUNNING}
    return html.Section(
        [
            html.H2("Univariate Statistics"),
            html.Div(
                [
                    html.Progress(
                        id=component_id(UNIVARIATE_NAMESPACE, "progress"),
                        value=control.percent,
                        max=100,
                    ),
                    html.Span(
                        control.phase or control.status.value,
                        id=component_id(UNIVARIATE_NAMESPACE, "status"),
                    ),
                    html.Span(
                        control.failure_reason or "",
                        id=component_id(UNIVARIATE_NAMESPACE, "failure"),
                    ),
                    html.Button(
                        "Compute univariate statistics",
                        id=component_id(UNIVARIATE_NAMESPACE, "compute"),
                        disabled=active or not control.can_start,
                    ),
                ],
                id=component_id(UNIVARIATE_NAMESPACE, "run-control"),
            ),
            dcc.Dropdown(
                id=component_id(UNIVARIATE_NAMESPACE, "dividend-frequency"),
                options=[{"label": value, "value": value} for value in view.dividend_frequencies],
                value=list(view.selected_dividend_frequencies),
                multi=True,
            ),
            html.Div(
                [html.Span(f"Result revision: {view.result_revision or 'unavailable'}")],
                id=component_id(UNIVARIATE_NAMESPACE, "result-revision"),
            ),
            dcc.Tabs(
                id=component_id(UNIVARIATE_NAMESPACE, "metric-tabs"),
                value=view.active_metric,
                children=[dcc.Tab(label=label, value=metric) for metric, label in view.metric_tabs],
            ),
            html.Div(id=component_id(UNIVARIATE_NAMESPACE, "figure-region")),
        ],
        id=component_id(UNIVARIATE_NAMESPACE, "page"),
    )
