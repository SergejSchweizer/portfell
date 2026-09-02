"""Reference-style four-route Dash shell with identifier-only workflow context."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol, cast

from dash import dcc, html
from dash.development.base_component import Component

from portfell.dash_app.components import JobProgress, PageHeader, StatusBanner
from portfell.dash_app.contracts import DEFAULT_ROUTE, PAGE_BY_ROUTE, PAGE_SPECS, PageSpec
from portfell.dash_app.state import BrowserState, browser_state_from_workflow


class PageBuilder(Protocol):
    def __call__(self, services: object | None = None) -> Component: ...


class WorkflowService(Protocol):
    def workflow_state(self) -> dict[str, object]: ...


@dataclass(frozen=True, slots=True)
class WorkflowContext:
    project_options: tuple[dict[str, str], ...] = ()
    selected_project: str | None = None
    project_metadata: tuple[tuple[str, str], ...] = ()
    universe_version: str = "—"
    selected_count: str = "—"
    snapshot_short_id: str = "—"
    stage_readiness: str = "Not ready"
    previous_result: str = "—"


def normalize_route(pathname: str | None) -> str:
    if pathname is None or pathname in {"", "/"}:
        return DEFAULT_ROUTE
    normalized = pathname.rstrip("/") or "/"
    return normalized if normalized in PAGE_BY_ROUTE else DEFAULT_ROUTE


def navigation(pathname: str) -> Component:
    active = normalize_route(pathname)
    links = [
        html.A(
            children=spec.label,
            href=spec.route,
            className=("pf-nav-link pf-nav-link-active" if spec.route == active else "pf-nav-link"),
            **cast(Any, {"aria-current": "page" if spec.route == active else "false"}),
        )
        for spec in PAGE_SPECS
    ]
    return html.Nav(
        links,
        className="pf-navigation",
        **cast(Any, {"aria-label": "Workflow"}),
    )


def workflow_context(context: WorkflowContext | None = None) -> Component:
    value = context or WorkflowContext()
    return html.Section(
        [
            html.Div("Current analysis", className="pf-context-title"),
            dcc.Dropdown(
                id="sidebar-project-selection",
                options=list(value.project_options),
                value=value.selected_project,
                placeholder="Select project",
                clearable=False,
                disabled=not value.project_options,
                className="pf-project-selection",
            ),
            html.Div(
                [_context_row(label, value, f"pf-project-{label.lower().replace(' ', '-')}")
                 for label, value in value.project_metadata],
                className="pf-project-metadata",
            ),
            _context_row("Universe", value.universe_version, "pf-context-universe"),
            _context_row("Selected", value.selected_count, "pf-context-selected"),
            _context_row("Snapshot", value.snapshot_short_id, "pf-context-snapshot"),
            _context_row("Readiness", value.stage_readiness, "pf-context-readiness"),
            _context_row("Previous result", value.previous_result, "pf-context-previous"),
        ],
        className="pf-workflow-context",
    )


def sidebar(pathname: str, context: WorkflowContext | None = None) -> Component:
    return html.Aside(
        [
            html.Div("Portfell", className="pf-product-header"),
            navigation(pathname),
            workflow_context(context),
        ],
        className="pf-sidebar",
    )


def placeholder_page(spec: PageSpec) -> Component:
    return html.Div(
        [
            PageHeader(spec.title, spec.subtitle),
            StatusBanner(
                "This stage is wired to the shared shell; its page contract is not available."
            ),
        ],
        className="pf-page",
    )


def load_page(
    spec: PageSpec,
    services: object | None = None,
    *,
    project_id: str | None = None,
    metadata_filters: Mapping[str, str | None] | None = None,
) -> Component:
    """Load one workflow page plugin; absent plugins fail visibly rather than adding a route."""
    module_name = f"portfell.dash_app.pages.{spec.page_id}"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        if error.name != module_name:
            raise
        return placeholder_page(spec)
    builder = getattr(module, "build_page", None)
    if not callable(builder):
        return placeholder_page(spec)
    if spec.page_id == "metadata":
        return cast(Any, builder)(
            services, project_id=project_id, filters=metadata_filters
        )
    return cast(PageBuilder, builder)(services)


def application_frame(
    pathname: str | None,
    *,
    services: object | None = None,
    context: WorkflowContext | None = None,
    project_id: str | None = None,
    metadata_filters: Mapping[str, str | None] | None = None,
) -> Component:
    route = normalize_route(pathname)
    spec = PAGE_BY_ROUTE[route]
    return html.Div(
        [
            sidebar(route, context),
            html.Main(
                load_page(
                    spec,
                    services,
                    project_id=project_id,
                    metadata_filters=metadata_filters,
                ),
                id="pf-main-content",
                className="pf-main",
            ),
        ],
        className="pf-app-shell",
    )


def root_layout() -> Component:
    return html.Div(
        [
            dcc.Location(id="pf-location", refresh=False),
            dcc.Store(id="pf-browser-state", storage_type="memory", data=BrowserState().to_store()),
            dcc.Interval(id="pf-job-poll", interval=1_000, disabled=True, n_intervals=0),
            html.Div(id="pf-route-content"),
            html.Div(JobProgress(BrowserState().job), id="pf-job-progress-region"),
        ],
        id="pf-root",
    )


def workflow_context_from_state(state: BrowserState, pathname: str | None) -> WorkflowContext:
    route = normalize_route(pathname)
    stage = PAGE_BY_ROUTE[route].page_id
    ready = getattr(state.readiness, stage)
    selected = next(
        (row for row in state.project_records if row.get("universe_id") == state.universe_id),
        None,
    )
    project_metadata = (
        (("Metadata", str(selected.get("member_count", "—"))),)
        if selected is not None
        else (("Metadata", "—"),)
    )
    return WorkflowContext(
        project_options=state.project_options,
        selected_project=state.universe_id,
        project_metadata=project_metadata,
        universe_version="—" if state.universe_version is None else str(state.universe_version),
        selected_count="—" if state.selected_count is None else str(state.selected_count),
        snapshot_short_id=(
            "—" if state.source_snapshot_id is None else state.source_snapshot_id[:12]
        ),
        stage_readiness="Ready" if ready else "Not ready",
        previous_result=(
            "Previous result available" if state.previous_ready_run is not None else "—"
        ),
    )


def route_renderer(services: object | None = None) -> Callable[[str | None, object], Component]:
    def render(pathname: str | None, store: object) -> Component:
        state = BrowserState.from_store(store)
        if services is not None and state == BrowserState():
            try:
                state = browser_state_from_workflow(
                    cast(WorkflowService, services).workflow_state()
                )
            except Exception:
                state = BrowserState(message_code="workflow_state_unavailable")
        return application_frame(
            pathname,
            services=services,
            context=workflow_context_from_state(state, pathname),
            project_id=state.universe_id,
                    metadata_filters=state.metadata_filters or None,
        )

    return render


def _context_row(label: str, value: str, component_id: str) -> Component:
    return html.Div(
        [
            html.Span(children=label, className="pf-context-label"),
            html.Span(children=value, id=component_id),
        ],
        className="pf-context-row",
    )


__all__ = [
    "WorkflowContext",
    "application_frame",
    "navigation",
    "normalize_route",
    "root_layout",
    "route_renderer",
    "sidebar",
    "workflow_context",
    "workflow_context_from_state",
]
