"""Bivariate Dash page over the persisted Univariate selection and pair artifacts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, cast

import plotly.graph_objects as go  # pyright: ignore[reportMissingTypeStubs]
from dash import html
from dash.development.base_component import Component

from portfell.dash_app.components import (
    ChartCard,
    ControlBar,
    EmptyState,
    ErrorState,
    HistoryCard,
    KpiCard,
    PageHeader,
    StageFooter,
    StatusBanner,
    TableCard,
)
from portfell.dash_app.figures import apply_portfell_template


class BivariateService(Protocol):
    def workflow_state(self) -> dict[str, object]: ...

    def run_bivariate(self, selection_id: str) -> dict[str, object]: ...

    def run_detail(self, run_id: str) -> dict[str, object]: ...


def bivariate_page_data(service: BivariateService) -> dict[str, object]:
    workflow = service.workflow_state()
    selection = _mapping(workflow.get("univariate_selection"))
    stages = _mapping(workflow.get("stages")) or {}
    stage = _mapping(stages.get("bivariate"))
    detail = service.run_detail(str(stage["run_id"])) if stage and stage.get("run_id") else stage
    artifacts = (_mapping(detail.get("artifacts")) or {}) if detail else {}
    artifact = _mapping(artifacts.get("bivariate_rows")) or {}
    raw_rows = _rows(artifact.get("items"))
    rows = _mappings(raw_rows)
    input_count = None if selection is None else _integer(selection.get("member_count"))
    candidate_count = None if input_count is None else input_count * (input_count - 1) // 2
    unavailable = None if candidate_count is None else max(0, candidate_count - len(rows))
    return {
        "selection": selection,
        "run": detail,
        "rows": rows,
        "input_count": input_count,
        "candidate_count": candidate_count,
        "eligible_count": len(rows),
        "unavailable_count": unavailable,
        "ready": detail is not None and detail.get("status") == "succeeded" and bool(rows),
    }


def compute_bivariate(service: BivariateService, selection_id: str) -> dict[str, object]:
    return service.run_bivariate(selection_id)


def build_page(services: object | None = None) -> Component:
    if services is None:
        return _layout(_empty_model(), message="Application service is unavailable.")
    try:
        model = bivariate_page_data(cast(BivariateService, services))
    except Exception as error:
        return _layout(_empty_model(), error=_error_code(error))
    return _layout(model)


def _layout(
    model: Mapping[str, object], *, message: str | None = None, error: str | None = None
) -> Component:
    rows = _mappings(model.get("rows"))
    selection = _mapping(model.get("selection"))
    run = _mapping(model.get("run"))
    ready = model.get("ready") is True
    children: list[Component] = [
        PageHeader(
            "Bivariate",
            "Inspect pairwise diversification evidence for the persisted Univariate selection.",
        ),
        ControlBar(
            [
                html.Button(
                    children="Compute bivariate statistics",
                    id="bivariate-compute",
                    className="pf-button pf-button-primary",
                    disabled=selection is None,
                ),
                html.Div(
                    "Pair-result controls operate on persisted backend evidence only.",
                    id="bivariate-result-controls",
                    className="pf-context-label",
                ),
            ],
            component_id="bivariate-controls",
        ),
    ]
    if error:
        children.append(ErrorState(f"Bivariate unavailable: {error}"))
    elif message:
        children.append(StatusBanner(message))
    children.extend(
        [
            html.Div(
                [
                    KpiCard("Input instruments", _display(model.get("input_count"))),
                    KpiCard("Candidate pairs", _display(model.get("candidate_count"))),
                    KpiCard("Eligible pairs", _display(model.get("eligible_count"))),
                    KpiCard("Unavailable pairs", _display(model.get("unavailable_count"))),
                ],
                className="pf-kpi-grid",
            ),
            ChartCard(
                "Bivariate Return / Diversification Universe",
                _scatter(rows) if rows else None,
                graph_id="bivariate-diversification-chart",
            ),
            TableCard(
                "Bivariate Statistics",
                (
                    [_pair_table(rows)]
                    if rows
                    else [EmptyState("Compute Bivariate statistics to populate pair evidence.")]
                ),
                component_id="bivariate-statistics-table",
            ),
            HistoryCard([_history(selection, run, model)]),
            StageFooter(
                [
                    html.A(
                        children="Continue to Multivariate",
                        href="/multivariate" if ready else "#",
                        id="bivariate-continue-multivariate",
                        className="pf-button pf-button-primary" if ready else "pf-button",
                        **cast(Any, {"aria-disabled": "false" if ready else "true"}),
                    )
                ]
            ),
        ]
    )
    return html.Div(children, className="pf-page", id="bivariate-page")


def _scatter(rows: tuple[Mapping[str, object], ...]) -> go.Figure:
    available = [
        row
        for row in rows
        if isinstance(row.get("pearson_correlation"), int | float)
        and isinstance(row.get("covariance"), int | float)
    ]
    figure = go.Figure(
        go.Scatter(
            x=[row["pearson_correlation"] for row in available],
            y=[row["covariance"] for row in available],
            mode="markers",
            customdata=[
                [
                    row.get("left_isin"),
                    row.get("left_exchange"),
                    row.get("left_code"),
                    row.get("right_isin"),
                    row.get("right_exchange"),
                    row.get("right_code"),
                    row.get("n_observations"),
                ]
                for row in available
            ],
            hovertemplate=(
                "Left %{customdata[0]} / %{customdata[1]} / %{customdata[2]}"
                "<br>Right %{customdata[3]} / %{customdata[4]} / %{customdata[5]}"
                "<br>Observations %{customdata[6]}<br>Pearson %{x}"
                "<br>Covariance %{y}<extra></extra>"
            ),
            name="Eligible pairs",
        )
    )
    return apply_portfell_template(figure, x_title="Pearson correlation", y_title="Covariance")


def _pair_table(rows: tuple[Mapping[str, object], ...]) -> Component:
    columns = (
        "left_isin",
        "left_exchange",
        "left_code",
        "right_isin",
        "right_exchange",
        "right_code",
        "n_observations",
        "pearson_correlation",
        "spearman_correlation",
        "covariance",
        "downside_correlation",
        "lower_tail_dependence",
        "drawdown_overlap_rate",
    )
    return html.Table(
        [
            html.Thead(html.Tr([html.Th(name) for name in columns])),
            html.Tbody(
                [html.Tr([html.Td(_display(row.get(name))) for name in columns]) for row in rows]
            ),
        ],
        className="pf-table",
    )


def _history(
    selection: Mapping[str, object] | None,
    run: Mapping[str, object] | None,
    model: Mapping[str, object],
) -> Component:
    if selection is None and run is None:
        return EmptyState("No persisted Bivariate history yet.")
    values = (
        ("Selection version", None if selection is None else selection.get("version")),
        ("Selection count", None if selection is None else selection.get("member_count")),
        ("Run", None if run is None else run.get("run_id")),
        ("Status", None if run is None else run.get("status")),
        ("Source snapshot", None if run is None else _short(run.get("input_snapshot_id"))),
        ("Algorithm", None if run is None else run.get("algorithm_version")),
        ("Candidate pairs", model.get("candidate_count")),
        ("Eligible pairs", model.get("eligible_count")),
        ("Unavailable pairs", model.get("unavailable_count")),
    )
    return html.Dl(
        [item for label, value in values for item in (html.Dt(label), html.Dd(_display(value)))],
        className="pf-evidence-list",
    )


def _empty_model() -> dict[str, object]:
    return {
        "selection": None,
        "run": None,
        "rows": (),
        "input_count": None,
        "candidate_count": None,
        "eligible_count": None,
        "unavailable_count": None,
        "ready": False,
    }


def _mapping(value: object) -> dict[str, object] | None:
    return cast(dict[str, object], value) if isinstance(value, dict) else None


def _rows(value: object) -> tuple[object, ...]:
    rows = cast(list[object] | tuple[object, ...], value) if isinstance(value, list | tuple) else ()
    return tuple(rows)


def _mappings(value: object) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for item in _rows(value):
        row = _mapping(item)
        if row is not None:
            rows.append(row)
    return tuple(rows)


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _short(value: object) -> str:
    text = "" if value is None else str(value)
    return text[:12] if text else "—"


def _display(value: object) -> str:
    return "—" if value is None else str(value)


def _error_code(error: Exception) -> str:
    code = getattr(error, "code", None)
    return str(code) if isinstance(code, str) else "unavailable"


__all__ = ["bivariate_page_data", "build_page", "compute_bivariate"]
