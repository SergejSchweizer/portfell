# pyright: reportMissingImports=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Responsive Multivariate optimizer page shell with no calculation callbacks."""

from __future__ import annotations

from dash import dcc, html

from portfell.dash_ui.core.ids import MULTIVARIATE_NAMESPACE, OBJECTIVE_SELECTOR_ID, component_id
from portfell.multivariate.contracts.common import DECISION_STAGE_ORDER

OBJECTIVE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("return_risk", "Return / Risk"),
    ("return_drawdown", "Return / Drawdown"),
    ("minimum_risk", "Minimum Risk"),
)

TAB_ORDER: tuple[tuple[str, str], ...] = (
    ("universe", "Universe"),
    ("risk_model", "Risk Model"),
    ("optimization", "Optimization"),
    ("validation", "Validation"),
    ("final_portfolio", "Final Portfolio"),
)


def build_multivariate_layout() -> object:
    """Build frozen layout regions; callbacks and figures are sibling PRs."""

    return html.Section(
        [
            html.H2("Multivariate Statistics"),
            html.Label(
                [
                    html.Span("Optimization objective"),
                    dcc.Dropdown(
                        id=OBJECTIVE_SELECTOR_ID,
                        options=[{"label": label, "value": value} for value, label in OBJECTIVE_OPTIONS],
                        value="return_risk",
                        clearable=False,
                    ),
                ]
            ),
            html.Div(
                [
                    html.Progress(id=component_id(MULTIVARIATE_NAMESPACE, "progress"), max=100),
                    html.Span(id=component_id(MULTIVARIATE_NAMESPACE, "status")),
                    html.Span(id=component_id(MULTIVARIATE_NAMESPACE, "failure")),
                    html.Button("Optimize portfolio", id=component_id(MULTIVARIATE_NAMESPACE, "optimize")),
                ],
                id=component_id(MULTIVARIATE_NAMESPACE, "run-control"),
            ),
            html.Section(
                [
                    html.H3("Universe & History"),
                    html.Div(id=component_id(MULTIVARIATE_NAMESPACE, "universe-history-summary")),
                    dcc.Graph(id=component_id(MULTIVARIATE_NAMESPACE, "universe-history-pipeline")),
                ]
            ),
            dcc.Graph(id=component_id(MULTIVARIATE_NAMESPACE, "candidate-plot")),
            dcc.Tabs(
                id=component_id(MULTIVARIATE_NAMESPACE, "tabs"),
                value="universe",
                children=[dcc.Tab(label=label, value=value) for value, label in TAB_ORDER],
            ),
            html.Section(
                [
                    html.H3("Decision Audit"),
                    *[
                        html.Div(
                            id=component_id(MULTIVARIATE_NAMESPACE, f"decision-{stage.value}"),
                            children=[html.Strong(stage.value), html.Span(" unavailable")],
                        )
                        for stage in DECISION_STAGE_ORDER
                    ],
                ],
                id=component_id(MULTIVARIATE_NAMESPACE, "decision-audit"),
            ),
            html.Div(id=component_id(MULTIVARIATE_NAMESPACE, "tab-content")),
        ],
        id=component_id(MULTIVARIATE_NAMESPACE, "page"),
        className="multivariate-page",
    )
