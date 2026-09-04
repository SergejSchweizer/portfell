"""Reference-style four-route Dash shell with identifier-only workflow context."""

from __future__ import annotations

import importlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast

from dash import dcc, html
from dash.development.base_component import Component

from portfell.dash_app.components import JobProgress, PageHeader, StatusBanner
from portfell.dash_app.contracts import DEFAULT_ROUTE, PAGE_BY_ROUTE, PAGE_SPECS, PageSpec
from portfell.dash_app.state import BrowserState, browser_state_from_workflow
from portfell.modules.runtime import ModuleRegistry


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
    selection_sections: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = ()


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
    sections = value.selection_sections or (("Current selection", value.project_metadata),)
    return html.Section(
        [
            html.Div("Current selection", className="pf-context-title"),
            *[
                html.Div(
                    [
                        html.Div(section, className="pf-context-section-title"),
                        html.Ul(
                            [html.Li([html.Span(label), html.Span(item_value)]) for label, item_value in items],
                            className="pf-context-list",
                        ),
                    ],
                    className="pf-project-metadata",
                )
                for section, items in sections
            ],
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
    metadata_member_count: int | None = None,
    univariate_filter_predicates: Sequence[Mapping[str, object]] = (),
) -> Component:
    """Load one workflow page plugin; absent plugins fail visibly rather than adding a route."""
    module_name = f"portfell.modules.{spec.page_id}.ui"
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as error:
        if error.name != module_name:
            raise
        return placeholder_page(spec)
    builder = getattr(module, "build_page", None)
    if not callable(builder):
        return placeholder_page(spec)
    page_services = (
        services.page_service(spec.page_id) if isinstance(services, ModuleRegistry) else services
    )
    if spec.page_id == "metadata":
        return cast(Any, builder)(page_services, project_id=project_id, filters=metadata_filters)
    if spec.page_id == "univariate":
        return cast(Any, builder)(
            page_services,
            metadata_member_count=metadata_member_count,
            filter_predicates=univariate_filter_predicates,
        )
    return cast(PageBuilder, builder)(page_services)


def application_frame(
    pathname: str | None,
    *,
    services: object | None = None,
    context: WorkflowContext | None = None,
    project_id: str | None = None,
    metadata_filters: Mapping[str, str | None] | None = None,
    metadata_member_count: int | None = None,
    univariate_filter_predicates: Sequence[Mapping[str, object]] = (),
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
                    metadata_member_count=metadata_member_count,
                    univariate_filter_predicates=univariate_filter_predicates,
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
            # Leave ``data`` unset so Dash hydrates the local-storage value
            # before any callback can write the empty initial state over it.
            dcc.Store(id="pf-browser-state", storage_type="local"),
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
    project_metadata = (
        ("Metadata", _display_count(state.metadata_member_count)),
        ("Univariate", _display_count(state.selected_count)),
        (
            "Bivariate",
            _display_count(
                state.bivariate_pair_count
                if state.bivariate_pair_count is not None
                else (
                    state.selected_count * (state.selected_count - 1) // 2
                    if state.selected_count is not None
                    else None
                )
            ),
        ),
    )
    selection_sections = (
        ("Metadata", (("ISINs", _display_count(state.metadata_member_count)), ("Date", state.metadata_date_range or "—"))),
        ("Univariate", (("ISINs", _display_count(state.selected_count)), ("Date", state.univariate_date_range or "—"))),
        ("Bivariate", (("Pairs", _display_count(state.bivariate_pair_count)), ("Date", state.bivariate_date_range or "—"))),
    )
    return WorkflowContext(
        project_options=state.project_options,
        selected_project=state.universe_id,
        project_metadata=project_metadata,
        selection_sections=selection_sections,
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
                workflow_service = (
                    services.workflow if isinstance(services, ModuleRegistry) else services
                )
                state = browser_state_from_workflow(
                    cast(WorkflowService, workflow_service).workflow_state()
                )
            except Exception:
                state = BrowserState(message_code="workflow_state_unavailable")
        return application_frame(
            pathname,
            services=services,
            context=workflow_context_from_state(state, pathname),
            project_id=state.universe_id,
            metadata_filters=state.metadata_filters or None,
            metadata_member_count=state.metadata_member_count,
            univariate_filter_predicates=state.univariate_filter_predicates,
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


def _display_count(value: int | None) -> str:
    return "—" if value is None else str(value)


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
