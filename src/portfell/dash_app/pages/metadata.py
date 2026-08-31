"""Metadata Dash page: active Xetra universe filtering and persisted universe creation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, cast

from dash import dcc, html
from dash.development.base_component import Component

from portfell.dash_app.components import (
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


_FILTERS = ("exchange", "instrument_type", "country", "currency")


def metadata_page_data(
    service: MetadataService, filters: Mapping[str, str | None] | None = None
) -> dict[str, object]:
    """Read presentation data only; never creates a universe as a render side effect."""
    selected = dict(filters or {})
    options = service.metadata_options()
    rows = service.active_listings(
        exchange=selected.get("exchange"),
        instrument_type=selected.get("instrument_type"),
        country=selected.get("country"),
        currency=selected.get("currency"),
    )
    history = service.metadata_history()
    workflow = service.workflow_state()
    current_row = _mapping(workflow.get("metadata_universe"))
    return {
        "options": options,
        "rows": rows,
        "history": history,
        "active_count": options.get("active_listing_count"),
        "filtered_count": len(rows),
        "selected_count": len(rows),
        "universe_version": None if current_row is None else current_row.get("version"),
        "ready": current_row is not None,
        "current": current_row,
    }


def create_universe(service: MetadataService, filters: Mapping[str, str | None]) -> object:
    """Explicit action boundary used by callbacks; creation is content-idempotent in the service."""
    return service.create_metadata_universe(
        exchange=filters.get("exchange"),
        instrument_type=filters.get("instrument_type"),
        country=filters.get("country"),
        currency=filters.get("currency"),
    )


def build_page(services: object | None = None) -> Component:
    if services is None:
        return _layout(_empty_model(), message="Application service is unavailable.")
    try:
        model = metadata_page_data(cast(MetadataService, services))
    except Exception as error:
        return _layout(_empty_model(), error=_error_code(error))
    return _layout(model)


def _layout(
    model: Mapping[str, object], *, message: str | None = None, error: str | None = None
) -> Component:
    options = _mapping(model.get("options")) or {}
    rows = _mappings(model.get("rows"))
    current = _mapping(model.get("current"))
    ready = model.get("ready") is True
    status: Component | None = None
    if error:
        status = ErrorState(f"Metadata unavailable: {error}")
    elif message:
        status = StatusBanner(message)

    children: list[Component] = [
        PageHeader("Metadata", "Build the active Xetra instrument universe."),
        ControlBar(
            [
                _dropdown("Exchange", "metadata-filter-exchange", options.get("exchange")),
                _dropdown(
                    "Instrument type",
                    "metadata-filter-instrument-type",
                    options.get("instrument_type"),
                ),
                _dropdown("Country", "metadata-filter-country", options.get("country")),
                _dropdown("Currency", "metadata-filter-currency", options.get("currency")),
                html.Button(
                    children="Reset filters",
                    id="metadata-reset-filters",
                    className="pf-button",
                ),
                html.Button(
                    children="Create universe",
                    id="metadata-create-universe",
                    className="pf-button pf-button-primary",
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
                    KpiCard("Filtered listings", _display(model.get("filtered_count"))),
                    KpiCard("Selected listings", _display(model.get("selected_count"))),
                    KpiCard("Universe version", _display(model.get("universe_version"))),
                ],
                className="pf-kpi-grid",
            ),
            TableCard(
                "Xetra Listings",
                (
                    [_listing_table(rows)]
                    if rows
                    else [EmptyState("No active listings match the filters.")]
                ),
                component_id="metadata-listings-table",
            ),
            HistoryCard([_history(current)]),
            StageFooter(
                [
                    html.A(
                        children="Continue to Univariate",
                        href="/univariate" if ready else "#",
                        id="metadata-continue-univariate",
                        className="pf-button pf-button-primary" if ready else "pf-button",
                        **cast(Any, {"aria-disabled": "false" if ready else "true"}),
                    )
                ]
            ),
        ]
    )
    return html.Div(children, className="pf-page", id="metadata-page")


def _dropdown(label: str, component_id: str, values: object) -> Component:
    raw = _items(values)
    return html.Label(
        [
            html.Span(label, className="pf-context-label"),
            dcc.Dropdown(
                id=component_id,
                options=[{"label": str(value), "value": str(value)} for value in raw],
                value=None,
                clearable=True,
            ),
        ]
    )


def _listing_table(rows: object) -> Component:
    items = _mappings(rows)
    columns = ("isin", "exchange", "code", "name", "instrument_type", "country", "currency")
    return html.Table(
        [
            html.Thead(html.Tr([html.Th(column.replace("_", " ").title()) for column in columns])),
            html.Tbody(
                [
                    html.Tr([html.Td(_display(row.get(column))) for column in columns])
                    for row in items
                ]
            ),
        ],
        className="pf-table",
    )


def _history(current: Mapping[str, object] | None) -> Component:
    if current is None:
        return EmptyState("No persisted Metadata universe yet.")
    rows = (
        ("Version", current.get("version")),
        ("Created", current.get("created_at")),
        ("Source snapshot", _short(current.get("source_snapshot_id"))),
        ("Members", current.get("member_count")),
    )
    return html.Dl(
        [item for label, value in rows for item in (html.Dt(label), html.Dd(_display(value)))],
        className="pf-evidence-list",
    )


def _empty_model() -> dict[str, object]:
    return {
        "options": {},
        "rows": (),
        "active_count": None,
        "filtered_count": None,
        "selected_count": None,
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


def _short(value: object) -> str:
    text = str(value) if value not in {None, ""} else ""
    return text[:12] if text else "—"


def _display(value: object) -> str:
    return "—" if value is None else str(value)


def _error_code(error: Exception) -> str:
    code = getattr(error, "code", None)
    return str(code) if isinstance(code, str) else "unavailable"


__all__ = ["build_page", "create_universe", "metadata_page_data"]
