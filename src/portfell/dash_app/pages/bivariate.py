"""Bivariate Dash page over the persisted Univariate selection and pair artifacts."""

# Plotly's dynamic trace/layout API is validated by figure contract tests.
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportArgumentType=false, reportUnusedFunction=false

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, cast

import plotly.graph_objects as go  # pyright: ignore[reportMissingTypeStubs]
from dash import html
from dash.development.base_component import Component

from portfell.dash_app.components import (
    ChartCard,
    ErrorState,
    KpiCard,
    PageHeader,
    StatusBanner,
)
from portfell.dash_app.figures import apply_portfell_template


class BivariateService(Protocol):
    def workflow_state(self) -> dict[str, object]: ...

    def bivariate_summary(self, run_id: str) -> dict[str, object]: ...

    def bivariate_page(
        self, run_id: str, *, offset: int = 0, limit: int = 100
    ) -> dict[str, object]: ...

    def bivariate_chart_sample(self, run_id: str, *, limit: int = 1000) -> dict[str, object]: ...

    def run_bivariate(self, selection_id: str) -> dict[str, object]: ...

    def run_detail(self, run_id: str) -> dict[str, object]: ...


def bivariate_page_data(service: BivariateService) -> dict[str, object]:
    workflow = service.workflow_state()
    selection = _mapping(workflow.get("univariate_selection"))
    active_job = _mapping(workflow.get("active_job"))
    stages = _mapping(workflow.get("stages")) or {}
    stage = _mapping(stages.get("bivariate"))
    detail = stage
    chart_rows: tuple[dict[str, object], ...] = ()
    if stage and stage.get("run_id") and stage.get("status") == "succeeded":
        run_id = str(stage["run_id"])
        if hasattr(service, "bivariate_summary"):
            summary = service.bivariate_summary(run_id)
            page = service.bivariate_page(run_id, limit=100)
            chart = service.bivariate_chart_sample(run_id, limit=1000)
            detail = _mapping(summary.get("run")) or stage
            rows = _mappings(page.get("rows"))
            chart_rows = _mappings(chart.get("rows"))
            summary_values = _mapping(summary.get("summary")) or {}
        else:
            detail = service.run_detail(run_id)
            artifact = (
                _mapping((_mapping(detail.get("artifacts")) or {}).get("bivariate_rows")) or {}
            )
            rows = _mappings(artifact.get("items"))
            chart_rows = rows[:1000]
            summary_values = {}
    else:
        rows = ()
        summary_values = {}
    input_count = None if selection is None else _integer(selection.get("member_count"))
    candidate_count = None if input_count is None else input_count * (input_count - 1) // 2
    candidate_count = _integer(summary_values.get("candidate_pair_count")) or candidate_count
    eligible_count = _integer(summary_values.get("eligible_count"))
    unavailable = _integer(summary_values.get("unavailable_count"))
    if unavailable is None and candidate_count is not None:
        unavailable = max(
            0, candidate_count - (eligible_count if eligible_count is not None else len(rows))
        )
    return {
        "selection": selection,
        "active_job": active_job,
        "run": detail,
        "rows": rows,
        "chart_rows": chart_rows,
        "input_count": input_count,
        "candidate_count": candidate_count,
        "eligible_count": len(rows) if eligible_count is None else eligible_count,
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
    selection = _mapping(model.get("selection"))
    active_job = _mapping(model.get("active_job"))
    # Depending on when the workflow is read, the durable job may be exposed
    # either as ``active_job`` or as the current bivariate stage. Treat both
    # records as authoritative so a page reload cannot re-enable computation
    # while the background bivariate run is still in progress.
    stage = _mapping(model.get("run"))
    job_running = any(
        record.get("status") in {"queued", "running"} for record in (active_job, stage) if record
    )
    children: list[Component] = [
        html.Div(
            [
                PageHeader(
                    "Bivariate",
                    "Inspect pairwise diversification evidence for the persisted "
                    "Univariate selection.",
                ),
                html.Div(
                    [
                        html.Button(
                            children="Compute bivariate statistics",
                            id="bivariate-compute",
                            className="pf-button pf-button-primary",
                            disabled=selection is None or job_running,
                        ),
                        html.Div(
                            id="bivariate-result-controls",
                            className="pf-context-label",
                        ),
                    ],
                    className="pf-page-header-actions",
                ),
            ],
            className="pf-page-header-row",
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
                    KpiCard(
                        "Multivariate Selected ISINs",
                        _display(model.get("input_count")),
                    ),
                    KpiCard("Candidate pairs", _display(model.get("candidate_count"))),
                    KpiCard("Eligible pairs", _display(model.get("eligible_count"))),
                ],
                className="pf-kpi-grid",
                id="bivariate-kpi-grid",
            ),
            ChartCard(
                "Bivariate Return / Diversification Universe",
                _scatter(_mappings(model.get("chart_rows"))) if model.get("chart_rows") else None,
                graph_id="bivariate-diversification-chart",
            ),
        ]
    )
    return html.Div(children, className="pf-page", id="bivariate-page")


def _scatter(rows: tuple[Mapping[str, object], ...]) -> go.Figure:
    available = [
        row
        for row in rows
        if isinstance(row.get("spearman_correlation"), int | float)
        and isinstance(row.get("downside_correlation"), int | float)
    ]
    figure = go.Figure(
        go.Scatter(
            x=[row["spearman_correlation"] for row in available],
            y=[row["downside_correlation"] for row in available],
            mode="markers",
            marker={
                # Invert co-exceedance: frequent joint extremes stay small,
                # while rare joint extremes receive more visual emphasis.
                "size": _coexceedance_sizes(available),
                "sizemode": "diameter",
                "color": [
                    float(row["lower_tail_dependence"])
                    if isinstance(row.get("lower_tail_dependence"), int | float)
                    else 0.0
                    for row in available
                ],
                "colorscale": [
                    [0.0, "#dc2626"],
                    [0.5, "#f59e0b"],
                    [1.0, "#6b7280"],
                ],
                "cmin": 0.0,
                "cmax": 1.0,
                "colorbar": {"title": "Lower-tail dependence"},
            },
            customdata=[
                [
                    row.get("left_isin"),
                    row.get("left_exchange"),
                    row.get("left_code"),
                    row.get("right_isin"),
                    row.get("right_exchange"),
                    row.get("right_code"),
                    row.get("n_observations"),
                    row.get("lower_tail_dependence"),
                    row.get("tail_coexceedance_rate"),
                ]
                for row in available
            ],
            hovertemplate=(
                "Left %{customdata[0]} / %{customdata[1]} / %{customdata[2]}"
                "<br>Right %{customdata[3]} / %{customdata[4]} / %{customdata[5]}"
                "<br>Observations %{customdata[6]}<br>Spearman %{x}"
                "<br>Downside correlation %{y}<br>Lower-tail dependence %{customdata[7]}"
                "<br>Co-exceedance rate %{customdata[8]}"
                "<extra></extra>"
            ),
            name="Eligible pairs",
        )
    )
    # Plotly does not create a legend for continuous marker sizes. Add three
    # reference traces so the inverse co-exceedance encoding is explicit.
    for size, label in (
        (8.0, "High rate — frequent joint extremes"),
        (19.0, "Medium rate"),
        (30.0, "Low rate — rare joint extremes"),
    ):
        figure.add_trace(
            go.Scatter(
                x=[None],
                y=[None],
                mode="markers",
                marker={"size": size, "color": "#6b7280"},
                name=label,
                hoverinfo="skip",
                showlegend=True,
            )
        )
    figure.update_layout(legend_title_text="Marker size: co-exceedance rate")
    return apply_portfell_template(
        figure, x_title="Spearman correlation", y_title="Downside correlation"
    )


def _coexceedance_sizes(rows: Sequence[Mapping[str, object]]) -> list[float]:
    """Scale inverse co-exceedance across the visible sample for contrast."""
    rates = [
        max(0.0, min(1.0, float(row["tail_coexceedance_rate"])))
        if isinstance(row.get("tail_coexceedance_rate"), int | float)
        else 0.5
        for row in rows
    ]
    minimum, maximum = min(rates, default=0.5), max(rates, default=0.5)
    span = maximum - minimum
    if span <= 0.0:
        return [19.0 for _ in rates]
    return [8.0 + 22.0 * (maximum - rate) / span for rate in rates]


def _empty_model() -> dict[str, object]:
    return {
        "selection": None,
        "active_job": None,
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
