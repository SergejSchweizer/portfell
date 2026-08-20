# pyright: reportMissingImports=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Dash callback registration for Metadata Builder actions."""

from __future__ import annotations

import re

from dash import Dash, Input, Output, State

from portfell.dash_ui.callbacks.metadata_builder.commands import command_key
from portfell.dash_ui.core.gateway import DashResearchGateway
from portfell.dash_ui.core.ids import METADATA_NAMESPACE, component_id
from portfell.dash_ui.core.routes import WorkflowId

_PROJECT_PATH = re.compile(r"^/projects/([^/]+)/")


def _project_slug(pathname: str | None) -> str | None:
    match = _PROJECT_PATH.match(pathname or "")
    return None if match is None else match.group(1)


def register_metadata_callbacks(app: Dash, gateway: DashResearchGateway) -> None:
    """Register idempotent Metadata Builder commands against the typed gateway."""

    @app.callback(
        Output(component_id(METADATA_NAMESPACE, "fetch-progress"), "value"),
        Output(component_id(METADATA_NAMESPACE, "fetch-status"), "children"),
        Output(component_id(METADATA_NAMESPACE, "fetch-button"), "disabled"),
        Input(component_id(METADATA_NAMESPACE, "fetch-button"), "n_clicks"),
        State("portfell-location", "pathname"),
        prevent_initial_call=True,
    )
    def fetch_metadata(
        n_clicks: int | None,
        pathname: str | None,
    ) -> tuple[float | None, str, bool]:
        project_slug = _project_slug(pathname)
        if not n_clicks or project_slug is None:
            return None, "metadata unavailable", False
        key = command_key(command="fetch_metadata", project_slug=project_slug, payload={})
        row = gateway.start_run(
            project_slug=project_slug,
            stage_id=WorkflowId.METADATA_BUILDER,
            command_key=key,
            settings={"action": "fetch_metadata"},
        )
        percent = row.get("percent")
        status = str(row.get("status") or "running")
        return (
            float(percent) if isinstance(percent, (int, float)) else None,
            status,
            status in {"starting", "running"},
        )

    @app.callback(
        Output("portfell-location", "href"),
        Input(component_id(METADATA_NAMESPACE, "create-project"), "n_clicks"),
        State(component_id(METADATA_NAMESPACE, "exchange"), "value"),
        State(component_id(METADATA_NAMESPACE, "instrument-type"), "value"),
        State(component_id(METADATA_NAMESPACE, "country"), "value"),
        State(component_id(METADATA_NAMESPACE, "currency"), "value"),
        State(component_id(METADATA_NAMESPACE, "name-contains"), "value"),
        State("portfell-location", "pathname"),
        prevent_initial_call=True,
    )
    def create_project(
        n_clicks: int | None,
        exchange: str | None,
        instrument_type: str | None,
        country: str | None,
        currency: str | None,
        name: str | None,
        pathname: str | None,
    ) -> str:
        if not n_clicks:
            return pathname or "/"
        project_slug = _project_slug(pathname) or "project"
        payload = {
            "exchange": exchange or "",
            "instrument_type": instrument_type or "",
            "country": country or "",
            "currency": currency or "",
            "name": name or "",
        }
        key = command_key(command="create_project", project_slug=project_slug, payload=payload)
        row = gateway.start_run(
            project_slug=project_slug,
            stage_id=WorkflowId.METADATA_BUILDER,
            command_key=key,
            settings={"action": "create_project", **payload},
        )
        new_slug = row.get("project_slug")
        if isinstance(new_slug, str) and new_slug:
            return f"/projects/{new_slug}/metadata-builder"
        return pathname or "/"
