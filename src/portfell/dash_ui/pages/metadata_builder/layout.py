# pyright: reportMissingImports=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Metadata Builder presentation layout."""

from __future__ import annotations

from dash import dcc, html

from portfell.dash_ui.core.ids import METADATA_NAMESPACE, component_id
from portfell.dash_ui.viewmodels.metadata_builder.model import MetadataBuilderView


def _criterion(label: str, suffix: str, options: tuple[tuple[str, str], ...]) -> object:
    return html.Label(
        [
            html.Span(label),
            dcc.Dropdown(
                id=component_id(METADATA_NAMESPACE, suffix),
                options=[{"label": text, "value": value} for text, value in options],
                clearable=True,
            ),
        ],
        className="metadata-criterion",
    )


def build_metadata_layout(view: MetadataBuilderView) -> object:
    """Render server-owned metadata state and exactly five builder criteria."""

    return html.Section(
        [
            html.H2("Metadata Builder"),
            html.Div(
                [
                    html.Button(
                        "Fetch metadata",
                        id=component_id(METADATA_NAMESPACE, "fetch-button"),
                        disabled=view.fetch_active,
                    ),
                    html.Progress(
                        id=component_id(METADATA_NAMESPACE, "fetch-progress"),
                        value=view.fetch_percent if view.fetch_percent is not None else None,
                        max=100,
                    ),
                    html.Span(
                        view.fetch_status,
                        id=component_id(METADATA_NAMESPACE, "fetch-status"),
                    ),
                ],
                className="metadata-fetch",
            ),
            _criterion("Exchange", "exchange", view.exchange_options),
            _criterion("Instrument type", "instrument-type", view.instrument_type_options),
            _criterion("Country", "country", view.country_options),
            _criterion("Currency", "currency", view.currency_options),
            html.Label(
                [
                    html.Span("Name contains"),
                    dcc.Input(id=component_id(METADATA_NAMESPACE, "name-contains"), type="text"),
                ],
                className="metadata-criterion",
            ),
            html.Button(
                "Create project",
                id=component_id(METADATA_NAMESPACE, "create-project"),
                disabled=not view.can_create_project,
            ),
            html.Div(
                [
                    html.Strong(f"Listings: {view.listing_count}"),
                    html.Span(f"Unique ISINs: {view.unique_isin_count}"),
                    html.Span(view.history_label),
                ],
                id=component_id(METADATA_NAMESPACE, "universe-history"),
            ),
        ],
        id=component_id(METADATA_NAMESPACE, "page"),
    )
