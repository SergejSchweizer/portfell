"""Metadata Dash page: active instrument filtering and persisted universe creation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, cast

import plotly.graph_objects as go  # pyright: ignore[reportMissingTypeStubs]
from dash import dcc, html
from dash.development.base_component import Component

from portfell.dash_app.components import (
    ChartCard,
    ControlBar,
    ErrorState,
    KpiCard,
    PageHeader,
    StatusBanner,
)
from portfell.dash_app.figures import apply_portfell_template
from portfell.dash_app.metadata_distributions import universe_distributions


class MetadataService(Protocol):
    def metadata_options(self) -> dict[str, object]: ...

    def active_listings(
        self,
        *,
        exchange: str | None = None,
        instrument_type: str | None = None,
        country: str | None = None,
        currency: str | None = None,
    ) -> tuple[dict[str, object], ...]: ...

    def metadata_universe(self, universe_id: str) -> dict[str, object]: ...

    def metadata_history(self) -> tuple[dict[str, object], ...]: ...

    def workflow_state(self) -> dict[str, object]: ...

    def create_metadata_universe(
        self,
        *,
        exchange: str | None = None,
        instrument_type: str | None = None,
        country: str | None = None,
        currency: str | None = None,
    ) -> object: ...

    def create_universe_and_start_univariate(
        self,
        *,
        exchange: str | None = None,
        instrument_type: str | None = None,
        country: str | None = None,
        currency: str | None = None,
    ) -> object: ...


_FILTERS = ("exchange", "instrument_type", "country", "currency")
_LISTING_PREVIEW_LIMIT = 100
_METADATA_CHART_HEIGHT = 220


def metadata_page_data(
    service: MetadataService,
    filters: Mapping[str, str | None] | None = None,
    project_id: str | None = None,
) -> dict[str, object]:
    """Read presentation data only; never creates a universe as a render side effect."""
    selected = dict(filters or {})
    options = service.metadata_options()
    # Filter controls describe the complete downloaded market universe, not the
    # currently selected project's already-filtered membership.
    full_listing_rows = tuple(service.active_listings())
    workflow = service.workflow_state()
    current_row = _mapping(workflow.get("metadata_universe"))
    project_rows: tuple[dict[str, object], ...] = ()
    if project_id and hasattr(service, "metadata_universe"):
        try:
            project = service.metadata_universe(project_id)
            project_rows = _mappings(project.get("items"))
        except Exception:
            project_rows = ()
    if project_id and not project_rows:
        project_record = next(
            (
                row
                for row in _mappings(workflow.get("metadata_universes"))
                if row.get("universe_id") == project_id
            ),
            None,
        )
        members = {
            (str(row.get("isin")), str(row.get("exchange")), str(row.get("code")))
            for row in _mappings(None if project_record is None else project_record.get("members"))
        }
        if members:
            project_rows = tuple(
                row
                for row in service.active_listings()
                if (str(row.get("isin")), str(row.get("exchange")), str(row.get("code")))
                in members
            )
    # Metadata selection starts from the complete downloaded listing universe;
    # project membership is an analytical output, not an input restriction here.
    source_rows = full_listing_rows
    matched_rows = tuple(
        row
        for row in source_rows
        if all(
            not selected.get(field) or row.get(field) == selected.get(field)
            for field in _FILTERS
        )
    )
    options = dict(options)
    for field in _FILTERS:
        members_by_value: dict[str, set[str]] = {}
        for row in full_listing_rows:
            if any(
                other != field
                and selected.get(other)
                and row.get(other) != selected.get(other)
                for other in _FILTERS
            ):
                continue
            value = row.get(field)
            if value not in {None, ""}:
                key = str(value)
                members_by_value.setdefault(key, set()).add(str(row.get("isin", "")))
        options[field] = [
            {"label": f"{key} ({len(isins)})", "value": key}
            for key, isins in sorted(members_by_value.items())
        ]
    history = service.metadata_history()
    # Distributions describe the complete selected project and are intentionally
    # independent of the transient dropdown filters used for the table/KPIs.
    distribution_rows = full_listing_rows
    return {
        "options": options,
        # Rendering thousands of HTML table rows blocks the browser before a user can
        # choose a filter.  The full filtered set remains authoritative for universe
        # creation; only the non-authoritative on-screen preview is bounded.
        "rows": matched_rows[:_LISTING_PREVIEW_LIMIT],
        "history": history,
        "active_count": options.get("active_listing_count"),
        "filtered_count": len(matched_rows),
        "selected_count": len(matched_rows),
        "preview_count": min(len(matched_rows), _LISTING_PREVIEW_LIMIT),
        "universe_version": None if current_row is None else current_row.get("version"),
        "ready": current_row is not None,
        "current": current_row,
        "distributions": universe_distributions(distribution_rows),
        "selected_filters": {
            field: (
                selected.get(field)
                if filters is not None
                else _single_value(project_rows, field)
            )
            for field in _FILTERS
        },
    }


def create_universe(service: MetadataService, filters: Mapping[str, str | None]) -> object:
    """Explicit action boundary used by callbacks; creation is content-idempotent in the service."""
    return service.create_universe_and_start_univariate(
        exchange=filters.get("exchange"),
        instrument_type=filters.get("instrument_type"),
        country=filters.get("country"),
        currency=filters.get("currency"),
    )


def build_page(
    services: object | None = None,
    project_id: str | None = None,
    filters: Mapping[str, str | None] | None = None,
) -> Component:
    if services is None:
        return _layout(_empty_model(), message="Application service is unavailable.")
    try:
        model = metadata_page_data(
            cast(MetadataService, services), filters=filters, project_id=project_id
        )
    except Exception as error:
        return _layout(_empty_model(), error=_error_code(error))
    return _layout(model)


def _layout(
    model: Mapping[str, object], *, message: str | None = None, error: str | None = None
) -> Component:
    options = _mapping(model.get("options")) or {}
    selected_filters = _mapping(model.get("selected_filters")) or {}
    status: Component | None = None
    if error:
        status = ErrorState(f"Metadata unavailable: {error}")
    elif message:
        status = StatusBanner(message)

    children: list[Component] = [
        PageHeader("Metadata", "Define the starting selection for the analysis funnel."),
        ControlBar(
            [
                _dropdown(
                    "Exchange", "metadata-filter-exchange", options.get("exchange"),
                    selected_filters.get("exchange"),
                ),
                _dropdown(
                    "Instrument type",
                    "metadata-filter-instrument-type",
                    options.get("instrument_type"),
                    selected_filters.get("instrument_type"),
                ),
                _dropdown(
                    "Country", "metadata-filter-country", options.get("country"),
                    selected_filters.get("country"),
                ),
                _dropdown(
                    "Currency", "metadata-filter-currency", options.get("currency"),
                    selected_filters.get("currency"),
                ),
            ],
            component_id="metadata-controls",
        ),
    ]
    if status is not None:
        children.append(status)
    children.extend(
        [
            html.Div(
                [
                    KpiCard("Active listings", _display(model.get("active_count"))),
                    KpiCard("Selected listings", _display(model.get("selected_count"))),
                ],
                className="pf-kpi-grid",
                id="metadata-kpi-grid",
            ),
            html.Div(
                [
                    ChartCard(
                        "Instrument Type Distribution",
                        _metadata_distribution(
                            _distribution_rows(model.get("distributions")),
                            x_title="Instrument type",
                            height=252,
                        ),
                        graph_id="metadata-instrument-type-distribution",
                    ),
                    ChartCard(
                        "Country Distribution",
                        _metadata_distribution(
                            _distribution_rows(model.get("distributions"), field="country"),
                            x_title="Country",
                        ),
                        graph_id="metadata-country-distribution",
                    ),
                    ChartCard(
                        "Currency Distribution",
                        _metadata_distribution(
                            _distribution_rows(model.get("distributions"), field="currency"),
                            x_title="Currency",
                        ),
                        graph_id="metadata-currency-distribution",
                    ),
                ],
                className="pf-metadata-distribution-grid",
            ),
        ]
    )
    return html.Div(children, className="pf-page", id="metadata-page")


def _dropdown(label: str, component_id: str, values: object, value: object = None) -> Component:
    raw = _items(values)
    option_rows = (
        [item for item in raw if isinstance(item, dict) and "value" in item]
        if raw and isinstance(raw[0], dict)
        else [{"label": str(item), "value": str(item)} for item in raw]
    )
    return html.Label(
        [
            html.Span(label, className="pf-context-label"),
            dcc.Dropdown(
                id=component_id,
                options=option_rows,
                value=value,
                clearable=True,
            ),
        ]
    )


def _metadata_distribution(
    rows: tuple[dict[str, object], ...], *, x_title: str, height: int = _METADATA_CHART_HEIGHT
) -> object | None:
    """Render a compact count-based metadata distribution with consistent dimensions."""
    if not rows:
        return None
    labels = [str(row.get("category", "Unknown")) for row in rows]
    counts = []
    for row in rows:
        value = row.get("count", 0)
        counts.append(float(value) if isinstance(value, int | float) and value >= 0 else 0.0)
    total = sum(counts)
    if total <= 0:
        return None
    percentages = [count / total * 100 for count in counts]
    figure = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=percentages,
                text=[f"{percentage:.1f}%" for percentage in percentages],
                texttemplate="%{text}",
                textposition="outside",
                customdata=labels,
                hovertemplate=f"{x_title}: %{{customdata}}<br>Share: %{{y:.1f}}%<extra></extra>",
            )
        ]
    )
    return apply_portfell_template(
        figure,
        x_title=x_title,
        y_title="Share of listings (%)",
    ).update_layout(height=height)


def _distribution_rows(
    value: object, *, field: str = "instrument_type"
) -> tuple[dict[str, object], ...]:
    distributions = _mapping(value) or {}
    return _mappings(distributions.get(field))


def _single_value(rows: tuple[dict[str, object], ...], field: str) -> str | None:
    values = {str(row[field]) for row in rows if row.get(field) not in {None, ""}}
    return next(iter(values)) if len(values) == 1 else None


def _empty_model() -> dict[str, object]:
    return {
        "options": {},
        "rows": (),
        "active_count": None,
        "filtered_count": None,
        "selected_count": None,
        "preview_count": None,
        "universe_version": None,
        "ready": False,
        "current": None,
    }


def _mapping(value: object) -> dict[str, object] | None:
    return cast(dict[str, object], value) if isinstance(value, dict) else None


def _items(value: object) -> tuple[object, ...]:
    items = (
        cast(list[object] | tuple[object, ...], value) if isinstance(value, list | tuple) else ()
    )
    return tuple(items)


def _mappings(value: object) -> tuple[dict[str, object], ...]:
    rows: list[dict[str, object]] = []
    for item in _items(value):
        row = _mapping(item)
        if row is not None:
            rows.append(row)
    return tuple(rows)


def _display(value: object) -> str:
    return "—" if value is None else str(value)


def _error_code(error: Exception) -> str:
    code = getattr(error, "code", None)
    return str(code) if isinstance(code, str) else "unavailable"


__all__ = ["build_page", "create_universe", "metadata_page_data"]
