"""Univariate Dash page over immutable backend run/selection artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, cast

import plotly.graph_objects as go
from dash import dcc, html
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
    UnavailableData,
)
from portfell.dash_app.figures import apply_portfell_template


class UnivariateService(Protocol):
    def workflow_state(self) -> dict[str, object]: ...

    def run_univariate(self, universe_id: str) -> dict[str, object]: ...

    def run_detail(self, run_id: str) -> dict[str, object]: ...

    def create_univariate_selection(
        self, run_id: str, *, predicates: Sequence[Mapping[str, object]] | None = None
    ) -> object: ...


def univariate_page_data(service: UnivariateService) -> dict[str, object]:
    workflow = service.workflow_state()
    universe = _mapping(workflow.get("metadata_universe"))
    stages = _mapping(workflow.get("stages"))
    stage = _mapping(stages.get("univariate"))
    selection = _mapping(workflow.get("univariate_selection"))
    detail = service.run_detail(str(stage["run_id"])) if stage and stage.get("run_id") else stage
    artifacts = _mapping(detail.get("artifacts")) if detail else {}
    artifact = _mapping(artifacts.get("univariate_rows"))
    raw_rows = artifact.get("items") if artifact else []
    rows = tuple(cast(dict[str, object], row) for row in raw_rows if isinstance(row, dict))
    selected = {
        _member_id(member)
        for member in (selection.get("members", []) if selection else [])
        if isinstance(member, dict)
    }
    available = tuple(row for row in rows if row.get("availability_reason") == "ok")
    unavailable = tuple(row for row in rows if row.get("availability_reason") != "ok")
    return {
        "universe": universe,
        "run": detail,
        "selection": selection,
        "rows": rows,
        "selected": selected,
        "input_count": None if universe is None else universe.get("member_count"),
        "available_count": len(available),
        "selected_count": None if selection is None else selection.get("member_count"),
        "unavailable_count": len(unavailable),
        "ready": selection is not None,
    }


def compute_univariate(service: UnivariateService, universe_id: str) -> dict[str, object]:
    """Explicit compute action; rendering never starts analytical work."""
    return service.run_univariate(universe_id)


def save_selection(
    service: UnivariateService,
    run_id: str,
    predicates: Sequence[Mapping[str, object]] | None = None,
) -> object:
    return service.create_univariate_selection(run_id, predicates=predicates)


def build_page(services: object | None = None) -> Component:
    if services is None:
        return _layout(_empty_model(), message="Application service is unavailable.")
    try:
        model = univariate_page_data(cast(UnivariateService, services))
    except Exception as error:
        return _layout(_empty_model(), error=_error_code(error))
    return _layout(model)


def _layout(
    model: Mapping[str, object], *, message: str | None = None, error: str | None = None
) -> Component:
    rows = tuple(row for row in model.get("rows", ()) if isinstance(row, dict))
    selected = model.get("selected") if isinstance(model.get("selected"), set) else set()
    run = _mapping(model.get("run"))
    universe = _mapping(model.get("universe"))
    selection = _mapping(model.get("selection"))
    ready = model.get("ready") is True
    children: list[Component] = [
        PageHeader(
            "Univariate",
            "Inspect single-instrument return and risk statistics, then persist the downstream selection.",
        ),
        ControlBar(
            [
                html.Button(
                    "Compute univariate statistics",
                    id="univariate-compute",
                    className="pf-button pf-button-primary",
                    disabled=universe is None,
                ),
                html.Div(
                    "Result filters use only persisted backend metrics.",
                    id="univariate-filter-summary",
                    className="pf-context-label",
                ),
            ],
            component_id="univariate-controls",
        ),
    ]
    if error:
        children.append(ErrorState(f"Univariate unavailable: {error}"))
    elif message:
        children.append(StatusBanner(message))
    children.extend(
        [
            html.Div(
                [
                    KpiCard("Input instruments", _display(model.get("input_count"))),
                    KpiCard("Available results", _display(model.get("available_count"))),
                    KpiCard("Selected instruments", _display(model.get("selected_count"))),
                    KpiCard("Unavailable results", _display(model.get("unavailable_count"))),
                ],
                className="pf-kpi-grid",
            ),
            ChartCard(
                "Univariate Return / Risk Universe",
                _scatter(rows) if rows else None,
                graph_id="univariate-return-risk-chart",
            ),
            TableCard(
                "Univariate Statistics",
                [_statistics_table(rows, cast(set[str], selected))]
                if rows
                else [EmptyState("Compute Univariate statistics to populate this table.")],
                component_id="univariate-statistics-table",
            ),
            HistoryCard([_history(universe, run, selection)]),
            StageFooter(
                [
                    html.Button(
                        "Save selection",
                        id="univariate-save-selection",
                        className="pf-button",
                        disabled=run is None or run.get("status") != "succeeded",
                    ),
                    dcc.Link(
                        "Continue to Bivariate",
                        href="/bivariate" if ready else "#",
                        id="univariate-continue-bivariate",
                        className="pf-button pf-button-primary" if ready else "pf-button",
                        **{"aria-disabled": "false" if ready else "true"},
                    ),
                ]
            ),
        ]
    )
    return html.Div(children, className="pf-page", id="univariate-page")


def _scatter(rows: Sequence[Mapping[str, object]]) -> go.Figure:
    available = [
        row
        for row in rows
        if isinstance(row.get("annualized_volatility"), int | float)
        and isinstance(row.get("annualized_return"), int | float)
        and row.get("availability_reason") == "ok"
    ]
    figure = go.Figure(
        go.Scatter(
            x=[row["annualized_volatility"] for row in available],
            y=[row["annualized_return"] for row in available],
            mode="markers",
            customdata=[
                [row.get("isin"), row.get("exchange"), row.get("code")] for row in available
            ],
            hovertemplate=(
                "ISIN %{customdata[0]}<br>Exchange %{customdata[1]}<br>Code %{customdata[2]}"
                "<br>Annualized risk %{x}<br>Annualized return %{y}<extra></extra>"
            ),
            name="Available",
        )
    )
    return apply_portfell_template(
        figure, x_title="Annualized volatility", y_title="Annualized return"
    )


def _statistics_table(rows: Sequence[Mapping[str, object]], selected: set[str]) -> Component:
    columns = (
        "isin",
        "exchange",
        "code",
        "annualized_return",
        "annualized_volatility",
        "max_drawdown",
        "sharpe_ratio",
        "sortino_ratio",
        "annual_dividend_yield",
        "availability_reason",
    )
    return html.Table(
        [
            html.Thead(html.Tr([html.Th("Selected"), *[html.Th(name) for name in columns]])),
            html.Tbody(
                [
                    html.Tr(
                        [
                            html.Td(
                                html.Input(
                                    type="checkbox",
                                    checked=_row_member_id(row) in selected,
                                    disabled=row.get("availability_reason") != "ok",
                                    **{"aria-label": f"Select {_row_member_id(row)}"},
                                )
                            ),
                            *[html.Td(_display(row.get(name))) for name in columns],
                        ]
                    )
                    for row in rows
                ]
            ),
        ],
        className="pf-table",
    )


def _history(
    universe: Mapping[str, object] | None,
    run: Mapping[str, object] | None,
    selection: Mapping[str, object] | None,
) -> Component:
    if universe is None and run is None:
        return EmptyState("No persisted Univariate history yet.")
    values = (
        ("Metadata universe", None if universe is None else universe.get("version")),
        ("Run", None if run is None else run.get("run_id")),
        ("Status", None if run is None else run.get("status")),
        ("Source snapshot", None if run is None else _short(run.get("input_snapshot_id"))),
        ("Algorithm", None if run is None else run.get("algorithm_version")),
        ("Selection version", None if selection is None else selection.get("version")),
        ("Selection count", None if selection is None else selection.get("member_count")),
    )
    return html.Dl(
        [item for label, value in values for item in (html.Dt(label), html.Dd(_display(value)))],
        className="pf-evidence-list",
    )


def _empty_model() -> dict[str, object]:
    return {
        "universe": None,
        "run": None,
        "selection": None,
        "rows": (),
        "selected": set(),
        "input_count": None,
        "available_count": None,
        "selected_count": None,
        "unavailable_count": None,
        "ready": False,
    }


def _mapping(value: object) -> dict[str, object] | None:
    return cast(dict[str, object], value) if isinstance(value, dict) else None


def _member_id(value: Mapping[str, object]) -> str:
    return f"{value.get('isin', '')}:{value.get('exchange', '')}:{value.get('code', '')}"


def _row_member_id(row: Mapping[str, object]) -> str:
    return _member_id(row)


def _short(value: object) -> str:
    text = "" if value is None else str(value)
    return text[:12] if text else "—"


def _display(value: object) -> str:
    return "—" if value is None else str(value)


def _error_code(error: Exception) -> str:
    code = getattr(error, "code", None)
    return str(code) if isinstance(code, str) else "unavailable"


__all__ = ["build_page", "compute_univariate", "save_selection", "univariate_page_data"]
