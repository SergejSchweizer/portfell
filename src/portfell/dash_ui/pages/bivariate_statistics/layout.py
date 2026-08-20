# pyright: reportMissingImports=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Bivariate calculation surface and detail-tab layout."""

from __future__ import annotations

from dash import dcc, html

from portfell.dash_ui.core.ids import BIVARIATE_NAMESPACE, component_id
from portfell.dash_ui.core.run_control import RunStatus
from portfell.dash_ui.viewmodels.bivariate_statistics.model import BivariateView


def build_bivariate_layout(view: BivariateView) -> object:
    """Render server-owned Bivariate state without pairwise recalculation in Dash."""

    control = view.run_control
    active = control.status in {RunStatus.STARTING, RunStatus.RUNNING}
    return html.Section(
        [
            html.H2("Bivariate Statistics"),
            html.Div(
                [
                    html.Progress(value=control.percent, max=100),
                    html.Span(control.phase or control.status.value),
                    html.Span(control.failure_reason or ""),
                    html.Button(
                        "Compute bivariate statistics",
                        id=component_id(BIVARIATE_NAMESPACE, "compute"),
                        disabled=active or not control.can_start,
                    ),
                ],
                id=component_id(BIVARIATE_NAMESPACE, "run-control"),
            ),
            dcc.Dropdown(
                id=component_id(BIVARIATE_NAMESPACE, "dependence-metric"),
                options=[{"label": label, "value": metric} for metric, label in view.dependence_metrics],
                value=view.selected_dependence_metric,
                clearable=False,
            ),
            dcc.Tabs(
                id=component_id(BIVARIATE_NAMESPACE, "detail-tabs"),
                value=view.active_view,
                children=[dcc.Tab(label=label, value=view_id) for view_id, label in view.detail_views],
            ),
            html.Div(id=component_id(BIVARIATE_NAMESPACE, "figure-region")),
        ],
        id=component_id(BIVARIATE_NAMESPACE, "page"),
    )
