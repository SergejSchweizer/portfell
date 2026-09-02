"""Univariate Dash page over immutable backend run/selection artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Protocol, cast

import plotly.graph_objects as go  # pyright: ignore[reportMissingTypeStubs]
from dash import dcc, html
from dash.development.base_component import Component

from portfell.dash_app.components import (
    ChartCard,
    ErrorState,
    KpiCard,
    PageHeader,
    StatusBanner,
    TableCard,
)
from portfell.dash_app.figures import apply_portfell_template

_CHART_PREVIEW_LIMIT = 5000
_TABLE_PREVIEW_LIMIT = 100
_MAX_PLOT_RISK = 0.99
_MIN_PLOT_RETURN = -0.49
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


def univariate_page_data(
    service: UnivariateService, *, metadata_member_count: int | None = None
) -> dict[str, object]:
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
            metadata_member_count
            if metadata_member_count is not None
            else (
                len(metadata_isins)
                if metadata_isins
                else (None if universe is None else universe.get("member_count"))
            )
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


def build_page(
    services: object | None = None, *, metadata_member_count: int | None = None
) -> Component:
    if services is None:
        return _layout(_empty_model(), message="Application service is unavailable.")
    try:
        model = univariate_page_data(
            cast(UnivariateService, services), metadata_member_count=metadata_member_count
        )
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


def data_regions(
    services: object | None = None, *, metadata_member_count: int | None = None
) -> list[Component]:
    """Refresh only persisted Univariate result content after job-status changes."""
    if services is None:
        return _data_regions(_empty_model())
    try:
        return _data_regions(
            univariate_page_data(
                cast(UnivariateService, services),
                metadata_member_count=metadata_member_count,
            )
        )
    except Exception as error:
        return [ErrorState(f"Univariate unavailable: {_error_code(error)}")]


def _data_regions(model: Mapping[str, object]) -> list[Component]:
    selected = _string_set(model.get("selected"))
    return [
        html.Div(
            [
                KpiCard("Metadata Selected ISINs", _display(model.get("input_count"))),
                KpiCard("Univariate Selected ISINs", _display(model.get("selected_count"))),
            ],
            className="pf-kpi-grid",
        ),
        html.Div(
            ChartCard(
                "Univariate Return / Risk Universe",
                _scatter(_mappings(model.get("chart_rows"))) if model.get("chart_rows") else None,
                graph_id="univariate-return-risk-chart",
            ),
            className="pf-univariate-risk-chart",
        ),
        _dividend_window(_mappings(model.get("chart_rows")), selected),
    ]


def _dividend_window(rows: Sequence[Mapping[str, object]], selected: set[str]) -> Component:
    """Show the cross-sectional dividend-payment frequency after the universe plot."""
    order = ("none / unknown", "monthly", "quarterly", "semiannual", "annual", "irregular")
    counts = {category: 0 for category in order}
    for row in rows:
        category = _frequency_category(row)
        if category not in counts:
            counts[category] = 0
        counts[category] += 1
    total = sum(counts.values())
    categories = [category for category in counts if counts[category] or total == 0]
    categories.sort(
        key=lambda category: (
            -counts[category],
            order.index(category) if category in order else len(order),
        )
    )
    labels = [_dividend_label(category) for category in categories]
    values = [counts[category] for category in categories]
    shares = [(value / total * 100) if total else 0.0 for value in values]
    selected_categories = {
        category
        for category in categories
        if any(_frequency_category(row) == category for row in rows)
        and all(
            _row_member_id(row) in selected
            for row in rows
            if _frequency_category(row) == category
        )
    }
    figure = go.Figure(
        go.Bar(
            x=labels,
            y=shares,
            customdata=[[value, share] for value, share in zip(values, shares, strict=False)],
            marker_color=[
                (
                    "#2563eb",
                    "#16a34a",
                    "#f59e0b",
                    "#9333ea",
                    "#ef4444",
                    "#06b6d4",
                    "#ec4899",
                )[index % 7]
                for index in range(len(categories))
            ],
            text=[f"{share:.1f}%" for share in shares],
            textposition="outside",
            hovertemplate=(
                "%{x}<br>ISINs: %{customdata[0]}<br>Share: %{customdata[1]:.1f}%<extra></extra>"
            ),
            name="Dividend payment frequency",
        )
    )
    apply_portfell_template(figure, x_title="Dividend payment frequency", y_title="ISIN share (%)")
    figure.update_layout(showlegend=False, height=340)
    table = html.Table(
        [
            html.Thead(
                html.Tr(
                    [
                        html.Th("Select"),
                        html.Th("Payment frequency"),
                        html.Th("ISINs"),
                        html.Th("Share"),
                    ]
                )
            ),
            html.Tbody(
                [
                    html.Tr(
                        [
                            html.Td(
                                dcc.Checklist(
                                    id={
                                        "type": "univariate-dividend-frequency",
                                        "category": category,
                                    },
                                    options=[
                                        {"label": "", "value": category, "disabled": not value}
                                    ],
                                    value=[category] if category in selected_categories else [],
                                )
                            ),
                            html.Td(label),
                            html.Td(f"{value:,}"),
                            html.Td(f"{share:.1f}%"),
                        ]
                    )
                    for label, value, share, category in zip(
                        labels, values, shares, categories, strict=False
                    )
                ]
            ),
        ],
        className="pf-table",
    )
    return html.Section(
        [
            html.H2("Dividend Payments", className="pf-card-title"),
            html.Div(
                [
                    ChartCard(
                        "Distribution", figure, graph_id="univariate-dividend-frequency-chart"
                    ),
                    TableCard(
                        "Statistics",
                        [table],
                        component_id="univariate-dividend-frequency-table",
                    ),
                ],
                className="pf-univariate-dividend-grid",
            ),
        ],
        className="pf-card pf-univariate-dividend-window",
        id="univariate-dividend-window",
    )


def _dividend_label(category: str) -> str:
    return {
        "none / unknown": "None / unknown",
        "semiannual": "Semi-annual",
    }.get(category, category.title())


def _frequency_category(row: Mapping[str, object]) -> str:
    value = str(row.get("distribution_frequency") or "unknown").strip().lower()
    return "none / unknown" if value in {"", "none", "unknown"} else value


def _scatter(rows: Sequence[Mapping[str, object]]) -> go.Figure:
    available = [
        row
        for row in rows
        if isinstance(row.get("annualized_volatility"), int | float)
        and isinstance(row.get("annualized_return"), int | float)
        and row.get("availability_reason") == "ok"
        and float(row["annualized_volatility"]) <= _MAX_PLOT_RISK
        and float(row["annualized_return"]) > _MIN_PLOT_RETURN
    ]
    ages = [
        float(row.get("history_years", 0) or 0)
        if isinstance(row.get("history_years", 0), int | float)
        else 0.0
        for row in available
    ]
    figure = go.Figure(
        go.Scatter(
            x=[row["annualized_volatility"] for row in available],
            y=[row["annualized_return"] for row in available],
            mode="markers",
            customdata=[
                [row.get("isin"), row.get("exchange"), row.get("code"), age]
                for row, age in zip(available, ages, strict=False)
            ],
            marker={
                "color": ages,
                "colorscale": "RdYlGn",
                "showscale": True,
                "colorbar": {"title": "History age (years)"},
                "size": 9,
                "line": {"width": 0.5, "color": "#333333"},
            },
            hovertemplate=(
                "ISIN %{customdata[0]}<br>Exchange %{customdata[1]}<br>Code %{customdata[2]}"
                "<br>Annualized risk %{x}<br>Annualized return %{y}"
                "<br>History age %{customdata[3]:.1f} years<extra></extra>"
            ),
            name="Available",
        )
    )
    return apply_portfell_template(
        figure, x_title="Annualized volatility", y_title="Annualized return"
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
