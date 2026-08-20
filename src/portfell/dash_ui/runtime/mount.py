# pyright: reportMissingImports=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Production Dash application creation over the typed presentation gateway."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from dash import Dash, dcc, html, page_container, register_page
from starlette.middleware.wsgi import WSGIMiddleware

from portfell.dash_ui.callbacks.bivariate_statistics.registration import (
    register_bivariate_callbacks,
)
from portfell.dash_ui.callbacks.metadata_builder.registration import (
    register_metadata_callbacks,
)
from portfell.dash_ui.callbacks.multivariate_statistics.registration import (
    register_multivariate_callbacks,
)
from portfell.dash_ui.callbacks.univariate_statistics.registration import (
    register_univariate_callbacks,
)
from portfell.dash_ui.core.gateway import DashResearchGateway
from portfell.dash_ui.core.routes import WorkflowId
from portfell.dash_ui.core.run_control import RunStatus, StatisticsRunControl, normalize_progress
from portfell.dash_ui.pages.bivariate_statistics.layout import build_bivariate_layout
from portfell.dash_ui.pages.metadata_builder.layout import build_metadata_layout
from portfell.dash_ui.pages.multivariate_statistics.layout import build_multivariate_layout
from portfell.dash_ui.pages.univariate_statistics.layout import build_univariate_layout
from portfell.dash_ui.viewmodels.bivariate_statistics.model import BivariateView
from portfell.dash_ui.viewmodels.metadata_builder.model import MetadataBuilderView
from portfell.dash_ui.viewmodels.univariate_statistics.model import UnivariateView

_DEFAULT_DIVIDEND_FREQUENCIES = (
    "none",
    "monthly",
    "quarterly",
    "semiannual",
    "annual",
)
_UNIVARIATE_TABS = (
    ("summary", "Summary"),
    ("return", "Return"),
    ("risk", "Risk"),
    ("drawdown", "Drawdown"),
    ("income", "Income"),
)


def _mapping(value: object) -> dict[str, object]:
    return dict(cast(Mapping[str, object], value)) if isinstance(value, Mapping) else {}


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
    percent = (
        float(percent_value)
        if isinstance(percent_value, (int, float))
        else normalize_progress(completed_units, total_units)
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


def _metadata_view(
    gateway: DashResearchGateway,
    project_slug: str,
) -> MetadataBuilderView:
    page = _mapping(
        gateway.page_view(
            project_slug=project_slug,
            workflow=WorkflowId.METADATA_BUILDER,
        )
    )
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


def _univariate_view(
    gateway: DashResearchGateway,
    project_slug: str,
) -> UnivariateView:
    page = _mapping(
        gateway.page_view(
            project_slug=project_slug,
            workflow=WorkflowId.UNIVARIATE_STATISTICS,
        )
    )
    status = _mapping(
        gateway.run_status(
            project_slug=project_slug,
            stage_id=WorkflowId.UNIVARIATE_STATISTICS,
        )
    )
    settings = _mapping(
        gateway.selection_settings(
            project_slug=project_slug,
            stage_id=WorkflowId.UNIVARIATE_STATISTICS,
        )
    )
    selected_raw = settings.get("dividend_frequencies")
    selected = (
        tuple(str(item) for item in selected_raw)
        if isinstance(selected_raw, list)
        else ()
    )
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


def _bivariate_view(
    gateway: DashResearchGateway,
    project_slug: str,
) -> BivariateView:
    page = _mapping(
        gateway.page_view(
            project_slug=project_slug,
            workflow=WorkflowId.BIVARIATE_STATISTICS,
        )
    )
    status = _mapping(
        gateway.run_status(
            project_slug=project_slug,
            stage_id=WorkflowId.BIVARIATE_STATISTICS,
        )
    )
    input_row = _mapping(page.get("input"))
    upstream = input_row.get("univariate_selection_id")
    return BivariateView(
        run_control=_control(WorkflowId.BIVARIATE_STATISTICS.value, status),
        upstream_revision=upstream if isinstance(upstream, str) else None,
    )


def _unavailable(title: str, code: str = "project_unavailable") -> object:
    return html.Section(
        [html.H2(title), html.P(code)],
        className="portfell-unavailable",
    )


def _with_poll(layout: object, poll_id: str) -> object:
    return html.Div([layout, dcc.Interval(id=poll_id, interval=2000, n_intervals=0)])


def create_production_dash_app(gateway: DashResearchGateway) -> Dash:
    """Create exactly four canonical project pages over the typed gateway."""

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
        return _with_poll(
            build_multivariate_layout(),
            "multivariate-status-poll",
        )

    pages = (
        (
            "portfell.metadata_builder",
            "/projects/<project_slug>/metadata-builder",
            "Metadata Builder",
            metadata_layout,
        ),
        (
            "portfell.univariate_statistics",
            "/projects/<project_slug>/univariate-statistics",
            "Univariate Statistics",
            univariate_layout,
        ),
        (
            "portfell.bivariate_statistics",
            "/projects/<project_slug>/bivariate-statistics",
            "Bivariate Statistics",
            bivariate_layout,
        ),
        (
            "portfell.multivariate_statistics",
            "/projects/<project_slug>/multivariate-statistics",
            "Multivariate Statistics",
            multivariate_layout,
        ),
    )
    for module, path_template, name, layout in pages:
        register_page(
            module,
            path_template=path_template,
            name=name,
            layout=layout,
        )

    app.layout = html.Main(
        [
            dcc.Location(id="portfell-location", refresh="callback-nav"),
            page_container,
        ],
        id="portfell-dash-page-container",
    )

    app.validation_layout = html.Div(
        [
            app.layout,
            _with_poll(
                build_metadata_layout(
                    MetadataBuilderView(
                        "idle",
                        False,
                        None,
                        (),
                        (),
                        (),
                        (),
                        False,
                        0,
                        0,
                        "unavailable",
                    )
                ),
                "metadata-status-poll",
            ),
            _with_poll(
                build_univariate_layout(
                    UnivariateView(
                        _control(
                            WorkflowId.UNIVARIATE_STATISTICS.value,
                            {"status": "ready"},
                        ),
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
                    BivariateView(
                        _control(
                            WorkflowId.BIVARIATE_STATISTICS.value,
                            {"status": "ready"},
                        ),
                        None,
                    )
                ),
                "bivariate-status-poll",
            ),
            _with_poll(
                build_multivariate_layout(),
                "multivariate-status-poll",
            ),
        ]
    )

    register_metadata_callbacks(app, gateway)
    register_univariate_callbacks(app, gateway)
    register_bivariate_callbacks(app, gateway)
    register_multivariate_callbacks(app, gateway)
    return app


def mount_dash_application(
    application: object,
    gateway: DashResearchGateway,
) -> object:
    """Mount Dash last so existing REST routes keep precedence."""

    dash_app = create_production_dash_app(gateway)
    application.mount("/", WSGIMiddleware(dash_app.server), name="portfell-dash")
    return application
