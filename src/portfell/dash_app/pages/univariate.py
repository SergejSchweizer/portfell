"""Univariate Dash page over immutable backend run/selection artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Protocol, cast

import plotly.graph_objects as go  # pyright: ignore[reportMissingTypeStubs]
from dash import dcc, html
from dash.development.base_component import Component

from portfell.dash_app.components import (
    ChartCard,
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
from portfell.dash_app.metric_cards import metric_card_models

_CHART_PREVIEW_LIMIT = 500
_TABLE_PREVIEW_LIMIT = 100
class UnivariateService(Protocol):
    def workflow_state(self) -> dict[str, object]: ...

    def univariate_summary(self, run_id: str) -> dict[str, object]: ...

    def univariate_page(
        self, run_id: str, *, offset: int = 0, limit: int = 100
    ) -> dict[str, object]: ...

    def univariate_chart_sample(self, run_id: str, *, limit: int = 500) -> dict[str, object]: ...

    def univariate_result_preview(self, run_id: str, *, limit: int = 500) -> dict[str, object]: ...

    def univariate_metric_distributions(self, run_id: str) -> dict[str, object]: ...

    def create_univariate_selection(
        self, run_id: str, *, predicates: Sequence[Mapping[str, object]] | None = None
    ) -> object: ...


def univariate_page_data(service: UnivariateService) -> dict[str, object]:
    workflow = service.workflow_state()
    universe = _mapping(workflow.get("metadata_universe"))
    stages = _mapping(workflow.get("stages")) or {}
    stage = _mapping(stages.get("univariate"))
    selection = _mapping(workflow.get("univariate_selection"))
    preview = None
    if stage and stage.get("status") == "succeeded" and stage.get("run_id"):
        run_id = str(stage["run_id"])
        if hasattr(service, "univariate_summary"):
            summary_read = service.univariate_summary(run_id)
            page_read = service.univariate_page(run_id, limit=_TABLE_PREVIEW_LIMIT)
            chart_read = service.univariate_chart_sample(run_id, limit=_CHART_PREVIEW_LIMIT)
            preview = {
                "run": summary_read.get("run"),
                "item_count": summary_read.get("item_count"),
                "summary": summary_read.get("summary"),
                "rows": page_read.get("rows", []),
                "chart_rows": chart_read.get("rows", []),
            }
        else:
            # Compatibility adapter for pre-PR389 fixture services only; production
            # services expose the explicit bounded read contracts above.
            preview = service.univariate_result_preview(run_id, limit=_CHART_PREVIEW_LIMIT)
    detail = _mapping(preview.get("run")) if preview else stage
    rows = _mappings(preview.get("rows")) if preview else ()
    chart_rows = _mappings(preview.get("chart_rows")) if preview else rows
    # A Univariate result is always scoped to the current Metadata universe. The
    # explicit guard also protects the UI from stale/broader persisted artifacts.
    metadata_isins = {
        str(member.get("isin"))
        for member in _mappings(universe.get("members") if universe else None)
        if member.get("isin") not in {None, ""}
    }
    if metadata_isins:
        rows = tuple(row for row in rows if str(row.get("isin")) in metadata_isins)
        chart_rows = tuple(row for row in chart_rows if str(row.get("isin")) in metadata_isins)
    summary = _mapping(preview.get("summary")) if preview else None
    distributions = None
    if preview and hasattr(service, "univariate_metric_distributions"):
        try:
            distributions = service.univariate_metric_distributions(
                str((detail or {}).get("run_id"))
            )
        except Exception:
            distributions = None
    selected = {
        _member_id(member) for member in _mappings(selection.get("members") if selection else None)
    }
    selected_isin_count = (
        len({member.split(":", 1)[0] for member in selected}) if selected else None
    )
    available = tuple(row for row in rows if row.get("availability_reason") == "ok")
    unavailable = tuple(row for row in rows if row.get("availability_reason") != "ok")
    return {
        "universe": universe,
        "run": detail,
        "selection": selection,
        "rows": rows,
        "chart_rows": chart_rows,
        "selected": selected,
        "input_count": (
            len(metadata_isins)
            if metadata_isins
            else (None if universe is None else universe.get("member_count"))
        ),
        "available_count": (
            len(available) if summary is None else summary.get("available_count", len(available))
        ),
        "selected_count": selected_isin_count,
        "unavailable_count": len(unavailable),
        "ready": selection is not None,
        "matching_count": None if preview is None else preview.get("item_count"),
        "metric_distributions": distributions,
    }


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
    children: list[Component] = [
        PageHeader(
            "Univariate",
            "Inspect single-instrument return and risk statistics, then persist the "
            "downstream selection.",
        ),
    ]
    if error:
        children.append(ErrorState(f"Univariate unavailable: {error}"))
    elif message:
        children.append(StatusBanner(message))
    children.append(html.Div(_data_regions(model), id="univariate-data-regions"))
    return html.Div(children, className="pf-page", id="univariate-page")


def data_regions(services: object | None = None) -> list[Component]:
    """Refresh only persisted Univariate result content after job-status changes."""
    if services is None:
        return _data_regions(_empty_model())
    try:
        return _data_regions(univariate_page_data(cast(UnivariateService, services)))
    except Exception as error:
        return [ErrorState(f"Univariate unavailable: {_error_code(error)}")]


def _data_regions(model: Mapping[str, object]) -> list[Component]:
    rows = _mappings(model.get("rows"))
    selected = _string_set(model.get("selected"))
    run = _mapping(model.get("run"))
    universe = _mapping(model.get("universe"))
    selection = _mapping(model.get("selection"))
    distributions = _mapping(model.get("metric_distributions"))
    ready = model.get("ready") is True
    return [
        html.Div(
            [
                KpiCard("Metadata Selected ISINs", _display(model.get("input_count"))),
                KpiCard("Univariate Selected ISINs", _display(model.get("selected_count"))),
            ],
            className="pf-kpi-grid",
        ),
        ChartCard(
            "Univariate Return / Risk Universe",
            _scatter(_mappings(model.get("chart_rows"))) if model.get("chart_rows") else None,
            graph_id="univariate-return-risk-chart",
        ),
        _metric_dashboard(distributions),
        TableCard(
            "Univariate Statistics",
            [
                html.P(
                    _preview_message(len(rows), _TABLE_PREVIEW_LIMIT),
                    className="pf-table-preview-note",
                ),
                _statistics_table(rows[:_TABLE_PREVIEW_LIMIT], selected),
            ]
            if rows
            else [EmptyState("Compute Univariate statistics to populate this table.")],
            component_id="univariate-statistics-table",
        ),
        HistoryCard([_history(universe, run, selection)]),
        StageFooter(
            [
                html.Button(
                    children="Apply selection & compute downstream",
                    id="univariate-save-selection",
                    className="pf-button",
                    title="Save selection",
                    disabled=run is None or run.get("status") != "succeeded",
                ),
                html.A(
                    children="Continue to Bivariate",
                    href="/bivariate" if ready else "#",
                    id="univariate-continue-bivariate",
                    className="pf-button pf-button-primary" if ready else "pf-button",
                    **cast(Any, {"aria-disabled": "false" if ready else "true"}),
                ),
            ]
        ),
    ]


def _metric_dashboard(distributions: Mapping[str, object] | None) -> Component:
    cards = metric_card_models(distributions or {})
    if not cards:
        return html.Div()
    groups: dict[str, list[Component]] = {}
    for card in cards:
        distribution = cast(dict[str, Any], card["distribution"])
        if distribution.get("kind") == "categorical":
            details = html.Div(str(distribution.get("categories", [])))
        else:
            summary = distribution.get("summary", {})
            details = html.Div(str(summary))
        component = html.Article(
            [
                html.H4(card["title"]),
                html.Div(card["definition"], className="pf-metric-definition"),
                html.Div(
                    [
                        html.Div(details, className="pf-metric-plot"),
                        html.Div("Summary", className="pf-metric-table"),
                        html.Div("Filters", className="pf-metric-selector"),
                    ],
                    className="pf-metric-card-grid",
                ),
            ],
            className="pf-metric-card",
            id=f"univariate-metric-{card['metric_id']}",
        )
        groups.setdefault(str(card["group"]), []).append(component)
    children: list[Component] = []
    for group, items in groups.items():
        children.extend([html.H3(group), html.Div(items, className="pf-metric-group")])
    return html.Section(
        children,
        id="univariate-metric-dashboard",
        className="pf-metric-dashboard",
    )


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
                                dcc.Checklist(
                                    id={"type": "univariate-member", "id": _row_member_id(row)},
                                    options=[
                                        {
                                            "label": "",
                                            "value": _row_member_id(row),
                                            "disabled": row.get("availability_reason") != "ok",
                                        }
                                    ],
                                    value=(
                                        [_row_member_id(row)]
                                        if _row_member_id(row) in selected
                                        else []
                                    ),
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


def _string_set(value: object) -> set[str]:
    if not isinstance(value, set):
        return set()
    strings: set[str] = set()
    for item in cast(set[object], value):
        if isinstance(item, str):
            strings.add(item)
    return strings


def _member_id(value: Mapping[str, object]) -> str:
    return f"{value.get('isin', '')}:{value.get('exchange', '')}:{value.get('code', '')}"


def _row_member_id(row: Mapping[str, object]) -> str:
    return _member_id(row)


def _short(value: object) -> str:
    text = "" if value is None else str(value)
    return text[:12] if text else "—"


def _display(value: object) -> str:
    return "—" if value is None else str(value)


def _preview_message(total: int, limit: int) -> str:
    """Keep presentation bounded without changing the persisted selection source."""
    if total <= limit:
        return f"Showing all {total:,} persisted results."
    return f"Showing the first {limit:,} of {total:,} persisted results."


def _error_code(error: Exception) -> str:
    code = getattr(error, "code", None)
    return str(code) if isinstance(code, str) else "unavailable"


__all__ = ["build_page", "data_regions", "save_selection", "univariate_page_data"]
