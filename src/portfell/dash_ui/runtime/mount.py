# pyright: reportMissingImports=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownLambdaType=false
"""Production Dash application creation over the typed presentation gateway."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import cast

from dash import Dash, Input, Output, State, ctx, dcc, html, page_container, register_page
from starlette.middleware.wsgi import WSGIMiddleware

from portfell.dash_ui.callbacks.bivariate_statistics.commands import start_command_key as bivariate_key
from portfell.dash_ui.callbacks.metadata_builder.commands import command_key as metadata_key
from portfell.dash_ui.callbacks.univariate_statistics.commands import start_command_key as univariate_key
from portfell.dash_ui.core.gateway import DashResearchGateway
from portfell.dash_ui.core.ids import (
    BIVARIATE_NAMESPACE,
    METADATA_NAMESPACE,
    MULTIVARIATE_NAMESPACE,
    OBJECTIVE_SELECTOR_ID,
    UNIVARIATE_NAMESPACE,
    component_id,
)
from portfell.dash_ui.core.run_control import RunStatus, StatisticsRunControl, normalize_progress
from portfell.dash_ui.core.routes import WorkflowId
from portfell.dash_ui.pages.bivariate_statistics.layout import build_bivariate_layout
from portfell.dash_ui.pages.metadata_builder.layout import build_metadata_layout
from portfell.dash_ui.pages.multivariate_statistics.layout import build_multivariate_layout
from portfell.dash_ui.pages.univariate_statistics.layout import build_univariate_layout
from portfell.dash_ui.viewmodels.bivariate_statistics.model import BivariateView
from portfell.dash_ui.viewmodels.metadata_builder.model import MetadataBuilderView
from portfell.dash_ui.viewmodels.univariate_statistics.model import UnivariateView

_PROJECT_PATH = re.compile(r"^/projects/([^/]+)/")
_DEFAULT_DIVIDEND_FREQUENCIES = ("none", "monthly", "quarterly", "semiannual", "annual")
_UNIVARIATE_TABS = (
    ("summary", "Summary"),
    ("return", "Return"),
    ("risk", "Risk"),
    ("drawdown", "Drawdown"),
    ("income", "Income"),
)


def _mapping(value: object) -> dict[str, object]:
    return dict(cast(Mapping[str, object], value)) if isinstance(value, Mapping) else {}


def _slug(pathname: str | None) -> str | None:
    match = _PROJECT_PATH.match(pathname or "")
    return None if match is None else match.group(1)


def _control(stage_id: str, row: Mapping[str, object]) -> StatisticsRunControl:
    raw_status = str(row.get("status") or "idle")
    status = {
        "ready": RunStatus.IDLE,
        "locked": RunStatus.IDLE,
        "idle": RunStatus.IDLE,
        "starting": RunStatus.STARTING,
        "running": RunStatus.RUNNING,
        "complete": RunStatus.COMPLETE,
        "succeeded": RunStatus.COMPLETE,
        "failed": RunStatus.FAILED,
        "stale": RunStatus.STALE,
    }.get(raw_status, RunStatus.IDLE)
    completed = row.get("completed_units", row.get("completed"))
    total = row.get("total_units", row.get("total"))
    completed_units = completed if isinstance(completed, int) else None
    total_units = total if isinstance(total, int) else None
    percent_value = row.get("percent")
    percent = float(percent_value) if isinstance(percent_value, (int, float)) else normalize_progress(
        completed_units, total_units
    )
    failure = row.get("failure_reason") or row.get("error_code")
    failure_reason = str(failure) if failure is not None else None
    if status is RunStatus.FAILED and not failure_reason:
        failure_reason = "calculation_failed"
    return StatisticsRunControl(
        stage_id=stage_id,
        status=status,
        phase=str(row.get("phase")) if row.get("phase") is not None else None,
        completed_units=completed_units,
        total_units=total_units,
        percent=percent,
        message=str(row.get("message")) if row.get("message") is not None else None,
        can_start=raw_status not in {"locked", "starting", "running"},
        failure_reason=failure_reason,
    )


def _control_outputs(control: StatisticsRunControl) -> tuple[float | None, str, str, bool]:
    return (
        control.percent,
        control.phase or control.status.value,
        control.failure_reason or "",
        control.status in {RunStatus.STARTING, RunStatus.RUNNING} or not control.can_start,
    )


def _options(row: Mapping[str, object], key: str) -> tuple[tuple[str, str], ...]:
    raw = row.get(key)
    if not isinstance(raw, list):
        return ()
    options: list[tuple[str, str]] = []
    for item in cast(list[object], raw):
        if not isinstance(item, Mapping):
            continue
        value = item.get("value")
        count = item.get("isin_count")
        if isinstance(value, str):
            label = f"{value} ({count})" if isinstance(count, int) else value
            options.append((label, value))
    return tuple(options)


def _metadata_view(gateway: DashResearchGateway, project_slug: str) -> MetadataBuilderView:
    page = _mapping(gateway.page_view(project_slug=project_slug, workflow=WorkflowId.METADATA_BUILDER))
    summary = _mapping(page.get("summary"))
    criteria = _mapping(summary.get("criteria"))
    initial_fill = _mapping(summary.get("initial_fill"))
    options = _mapping(page.get("options"))
    selected_count = criteria.get("selected_count")
    unique_count = selected_count if isinstance(selected_count, int) else 0
    listing_value = initial_fill.get("selected_listing_count")
    listing_count = listing_value if isinstance(listing_value, int) else unique_count
    fill_status = str(initial_fill.get("status") or "not_run")
    metadata_ready = options.get("metadata_ready") is True
    return MetadataBuilderView(
        fetch_status="ready" if metadata_ready else "metadata required",
        fetch_active=False,
        fetch_percent=None,
        exchange_options=_options(options, "exchange"),
        instrument_type_options=_options(options, "instrument_type"),
        country_options=_options(options, "country"),
        currency_options=_options(options, "currency"),
        can_create_project=metadata_ready,
        listing_count=listing_count,
        unique_isin_count=unique_count,
        history_label=f"Initial history: {fill_status}",
    )


def _univariate_view(gateway: DashResearchGateway, project_slug: str) -> UnivariateView:
    page = _mapping(gateway.page_view(project_slug=project_slug, workflow=WorkflowId.UNIVARIATE_STATISTICS))
    status = _mapping(gateway.run_status(project_slug=project_slug, stage_id=WorkflowId.UNIVARIATE_STATISTICS))
    settings = _mapping(gateway.selection_settings(project_slug=project_slug, stage_id=WorkflowId.UNIVARIATE_STATISTICS))
    selected_raw = settings.get("dividend_frequencies")
    selected = tuple(str(item) for item in selected_raw) if isinstance(selected_raw, list) else ()
    allowed = tuple(dict.fromkeys((*_DEFAULT_DIVIDEND_FREQUENCIES, *selected)))
    sections = _mapping(page.get("sections"))
    result_section = _mapping(sections.get("results"))
    revision = result_section.get("revision")
    return UnivariateView(
        run_control=_control(WorkflowId.UNIVARIATE_STATISTICS.value, status),
        dividend_frequencies=allowed,
        selected_dividend_frequencies=selected,
        duration_thresholds=(),
        metric_tabs=_UNIVARIATE_TABS,
        active_metric="summary",
        result_revision=revision if isinstance(revision, str) else None,
    )


def _bivariate_view(gateway: DashResearchGateway, project_slug: str) -> BivariateView:
    page = _mapping(gateway.page_view(project_slug=project_slug, workflow=WorkflowId.BIVARIATE_STATISTICS))
    status = _mapping(gateway.run_status(project_slug=project_slug, stage_id=WorkflowId.BIVARIATE_STATISTICS))
    input_row = _mapping(page.get("input"))
    upstream = input_row.get("univariate_selection_id")
    return BivariateView(
        run_control=_control(WorkflowId.BIVARIATE_STATISTICS.value, status),
        upstream_revision=upstream if isinstance(upstream, str) else None,
    )


def _unavailable(title: str, code: str = "project_unavailable") -> object:
    return html.Section([html.H2(title), html.P(code)], className="portfell-unavailable")


def _with_poll(layout: object, poll_id: str) -> object:
    return html.Div([layout, dcc.Interval(id=poll_id, interval=2000, n_intervals=0)])


def create_production_dash_app(gateway: DashResearchGateway) -> Dash:
    """Create four canonical project pages backed only by the typed gateway."""

    app = Dash(
        __name__,
        use_pages=True,
        pages_folder="",
        requests_pathname_prefix="/",
        routes_pathname_prefix="/",
        suppress_callback_exceptions=False,
        title="Portfell",
    )

    def metadata_layout(project_slug: str | None = None, **_: object) -> object:
        if not project_slug:
            return _unavailable("Metadata Builder")
        try:
            return _with_poll(
                build_metadata_layout(_metadata_view(gateway, project_slug)),
                "metadata-status-poll",
            )
        except (KeyError, ValueError):
            return _unavailable("Metadata Builder")

    def univariate_layout(project_slug: str | None = None, **_: object) -> object:
        if not project_slug:
            return _unavailable("Univariate Statistics")
        try:
            return _with_poll(
                build_univariate_layout(_univariate_view(gateway, project_slug)),
                "univariate-status-poll",
            )
        except (KeyError, ValueError):
            return _unavailable("Univariate Statistics")

    def bivariate_layout(project_slug: str | None = None, **_: object) -> object:
        if not project_slug:
            return _unavailable("Bivariate Statistics")
        try:
            return _with_poll(
                build_bivariate_layout(_bivariate_view(gateway, project_slug)),
                "bivariate-status-poll",
            )
        except (KeyError, ValueError):
            return _unavailable("Bivariate Statistics")

    def multivariate_layout(project_slug: str | None = None, **_: object) -> object:
        if not project_slug:
            return _unavailable("Multivariate Statistics")
        return _with_poll(build_multivariate_layout(), "multivariate-status-poll")

    pages = (
        ("portfell.metadata_builder", "/projects/<project_slug>/metadata-builder", "Metadata Builder", metadata_layout),
        ("portfell.univariate_statistics", "/projects/<project_slug>/univariate-statistics", "Univariate Statistics", univariate_layout),
        ("portfell.bivariate_statistics", "/projects/<project_slug>/bivariate-statistics", "Bivariate Statistics", bivariate_layout),
        ("portfell.multivariate_statistics", "/projects/<project_slug>/multivariate-statistics", "Multivariate Statistics", multivariate_layout),
    )
    for module, path_template, name, layout in pages:
        register_page(module, path_template=path_template, name=name, layout=layout)

    app.layout = html.Main(
        [dcc.Location(id="portfell-location", refresh="callback-nav"), page_container],
        id="portfell-dash-page-container",
    )

    # Static validation tree keeps strict callback validation while pages remain dynamic.
    app.validation_layout = html.Div(
        [
            app.layout,
            _with_poll(
                build_metadata_layout(
                    MetadataBuilderView("idle", False, None, (), (), (), (), False, 0, 0, "unavailable")
                ),
                "metadata-status-poll",
            ),
            _with_poll(
                build_univariate_layout(
                    UnivariateView(
                        _control("univariate_statistics", {"status": "ready"}),
                        _DEFAULT_DIVIDEND_FREQUENCIES,
                        (),
                        (),
                        _UNIVARIATE_TABS,
                        "summary",
                        None,
                    )
                ),
                "univariate-status-poll",
            ),
            _with_poll(
                build_bivariate_layout(
                    BivariateView(_control("bivariate_statistics", {"status": "ready"}), None)
                ),
                "bivariate-status-poll",
            ),
            _with_poll(build_multivariate_layout(), "multivariate-status-poll"),
        ]
    )

    @app.callback(
        Output(component_id(METADATA_NAMESPACE, "fetch-progress"), "value"),
        Output(component_id(METADATA_NAMESPACE, "fetch-status"), "children"),
        Output(component_id(METADATA_NAMESPACE, "fetch-button"), "disabled"),
        Input(component_id(METADATA_NAMESPACE, "fetch-button"), "n_clicks"),
        State("portfell-location", "pathname"),
        prevent_initial_call=True,
    )
    def fetch_metadata(n_clicks: int | None, pathname: str | None) -> tuple[float | None, str, bool]:
        project_slug = _slug(pathname)
        if not n_clicks or project_slug is None:
            return None, "metadata unavailable", False
        key = metadata_key(command="fetch_metadata", project_slug=project_slug, payload={})
        row = gateway.start_run(
            project_slug=project_slug,
            stage_id=WorkflowId.METADATA_BUILDER,
            command_key=key,
            settings={"action": "fetch_metadata"},
        )
        percent = row.get("percent")
        return (
            float(percent) if isinstance(percent, (int, float)) else None,
            str(row.get("status") or "running"),
            str(row.get("status")) == "running",
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
        project_slug = _slug(pathname) or "project"
        payload = {
            "exchange": exchange or "",
            "instrument_type": instrument_type or "",
            "country": country or "",
            "currency": currency or "",
            "name": name or "",
        }
        key = metadata_key(command="create_project", project_slug=project_slug, payload=payload)
        if not n_clicks:
            return pathname or "/"
        row = gateway.start_run(
            project_slug=project_slug,
            stage_id=WorkflowId.METADATA_BUILDER,
            command_key=key,
            settings={"action": "create_project", **payload},
        )
        new_slug = row.get("project_slug")
        return f"/projects/{new_slug}/metadata-builder" if isinstance(new_slug, str) else (pathname or "/")

    @app.callback(
        Output(component_id(UNIVARIATE_NAMESPACE, "progress"), "value"),
        Output(component_id(UNIVARIATE_NAMESPACE, "status"), "children"),
        Output(component_id(UNIVARIATE_NAMESPACE, "failure"), "children"),
        Output(component_id(UNIVARIATE_NAMESPACE, "compute"), "disabled"),
        Input(component_id(UNIVARIATE_NAMESPACE, "compute"), "n_clicks"),
        Input("univariate-status-poll", "n_intervals"),
        State("portfell-location", "pathname"),
    )
    def update_univariate(n_clicks: int | None, _: int, pathname: str | None) -> tuple[float | None, str, str, bool]:
        project_slug = _slug(pathname)
        if project_slug is None:
            return None, "unavailable", "project_unavailable", True
        if ctx.triggered_id == component_id(UNIVARIATE_NAMESPACE, "compute") and n_clicks:
            page = _mapping(gateway.page_view(project_slug=project_slug, workflow=WorkflowId.UNIVARIATE_STATISTICS))
            upstream = str(_mapping(page.get("input")).get("metadata_selection_id") or "unavailable")
            gateway.start_run(
                project_slug=project_slug,
                stage_id=WorkflowId.UNIVARIATE_STATISTICS,
                command_key=univariate_key(project_slug=project_slug, upstream_revision=upstream),
                settings={},
            )
        return _control_outputs(
            _control(
                WorkflowId.UNIVARIATE_STATISTICS.value,
                gateway.run_status(project_slug=project_slug, stage_id=WorkflowId.UNIVARIATE_STATISTICS),
            )
        )

    @app.callback(
        Output(component_id(BIVARIATE_NAMESPACE, "progress"), "value"),
        Output(component_id(BIVARIATE_NAMESPACE, "status"), "children"),
        Output(component_id(BIVARIATE_NAMESPACE, "failure"), "children"),
        Output(component_id(BIVARIATE_NAMESPACE, "compute"), "disabled"),
        Input(component_id(BIVARIATE_NAMESPACE, "compute"), "n_clicks"),
        Input("bivariate-status-poll", "n_intervals"),
        State("portfell-location", "pathname"),
    )
    def update_bivariate(n_clicks: int | None, _: int, pathname: str | None) -> tuple[float | None, str, str, bool]:
        project_slug = _slug(pathname)
        if project_slug is None:
            return None, "unavailable", "project_unavailable", True
        if ctx.triggered_id == component_id(BIVARIATE_NAMESPACE, "compute") and n_clicks:
            page = _mapping(gateway.page_view(project_slug=project_slug, workflow=WorkflowId.BIVARIATE_STATISTICS))
            upstream = str(_mapping(page.get("input")).get("univariate_selection_id") or "unavailable")
            gateway.start_run(
                project_slug=project_slug,
                stage_id=WorkflowId.BIVARIATE_STATISTICS,
                command_key=bivariate_key(project_slug=project_slug, univariate_revision=upstream),
                settings={},
            )
        return _control_outputs(
            _control(
                WorkflowId.BIVARIATE_STATISTICS.value,
                gateway.run_status(project_slug=project_slug, stage_id=WorkflowId.BIVARIATE_STATISTICS),
            )
        )

    @app.callback(
        Output(component_id(MULTIVARIATE_NAMESPACE, "progress"), "value"),
        Output(component_id(MULTIVARIATE_NAMESPACE, "status"), "children"),
        Output(component_id(MULTIVARIATE_NAMESPACE, "failure"), "children"),
        Output(component_id(MULTIVARIATE_NAMESPACE, "optimize"), "disabled"),
        Input(component_id(MULTIVARIATE_NAMESPACE, "optimize"), "n_clicks"),
        Input("multivariate-status-poll", "n_intervals"),
        State(OBJECTIVE_SELECTOR_ID, "value"),
        State("portfell-location", "pathname"),
    )
    def update_multivariate(
        n_clicks: int | None, _: int, objective: str | None, pathname: str | None
    ) -> tuple[float | None, str, str, bool]:
        project_slug = _slug(pathname)
        if project_slug is None:
            return None, "unavailable", "project_unavailable", True
        if ctx.triggered_id == component_id(MULTIVARIATE_NAMESPACE, "optimize") and n_clicks:
            page = _mapping(gateway.page_view(project_slug=project_slug, workflow=WorkflowId.MULTIVARIATE_STATISTICS))
            upstream = str(_mapping(page.get("input")).get("bivariate_run_id") or "unavailable")
            selected_objective = objective or "return_risk"
            command_key = f"multivariate:{project_slug}:{upstream}:{selected_objective}"
            gateway.start_run(
                project_slug=project_slug,
                stage_id=WorkflowId.MULTIVARIATE_STATISTICS,
                command_key=command_key,
                settings={"objective": selected_objective},
            )
        return _control_outputs(
            _control(
                WorkflowId.MULTIVARIATE_STATISTICS.value,
                gateway.run_status(project_slug=project_slug, stage_id=WorkflowId.MULTIVARIATE_STATISTICS),
            )
        )

    return app


def mount_dash_application(application: object, gateway: DashResearchGateway) -> object:
    """Mount Dash last so existing REST routes keep precedence."""

    dash_app = create_production_dash_app(gateway)
    application.mount("/", WSGIMiddleware(dash_app.server), name="portfell-dash")
    return application
