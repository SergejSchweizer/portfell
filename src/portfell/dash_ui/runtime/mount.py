# pyright: reportMissingImports=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Mount the production Dash browser UI into the existing FastAPI application."""

from __future__ import annotations

from dash import Dash, html, page_container, register_page
from starlette.middleware.wsgi import WSGIMiddleware

from portfell.dash_ui.core.run_control import RunStatus, StatisticsRunControl
from portfell.dash_ui.pages.bivariate_statistics.layout import build_bivariate_layout
from portfell.dash_ui.pages.metadata_builder.layout import build_metadata_layout
from portfell.dash_ui.pages.multivariate_statistics.layout import build_multivariate_layout
from portfell.dash_ui.pages.univariate_statistics.layout import build_univariate_layout
from portfell.dash_ui.viewmodels.bivariate_statistics.model import BivariateView
from portfell.dash_ui.viewmodels.metadata_builder.model import MetadataBuilderView
from portfell.dash_ui.viewmodels.univariate_statistics.model import UnivariateView
from portfell.hosted_api import create_runtime_app


def _idle_control(stage_id: str) -> StatisticsRunControl:
    return StatisticsRunControl(stage_id, RunStatus.IDLE, None, None, None, None, None, True)


def _metadata_layout(**_: object) -> object:
    return build_metadata_layout(
        MetadataBuilderView(
            fetch_status="idle",
            fetch_active=False,
            fetch_percent=None,
            exchange_options=(),
            instrument_type_options=(),
            country_options=(),
            currency_options=(),
            can_create_project=False,
            listing_count=0,
            unique_isin_count=0,
            history_label="History unavailable until project evidence is loaded",
        )
    )


def _univariate_layout(**_: object) -> object:
    return build_univariate_layout(
        UnivariateView(
            run_control=_idle_control("univariate_statistics"),
            dividend_frequencies=(),
            selected_dividend_frequencies=(),
            duration_thresholds=(),
            metric_tabs=(("summary", "Summary"),),
            active_metric="summary",
            result_revision=None,
        )
    )


def _bivariate_layout(**_: object) -> object:
    return build_bivariate_layout(BivariateView(run_control=_idle_control("bivariate_statistics"), upstream_revision=None))


def _multivariate_layout(**_: object) -> object:
    return build_multivariate_layout()


def create_production_dash_app() -> Dash:
    """Create exactly four canonical project pages without the temporary `/dash` prefix."""

    app = Dash(
        __name__,
        use_pages=True,
        pages_folder="",
        requests_pathname_prefix="/",
        routes_pathname_prefix="/",
        suppress_callback_exceptions=False,
        title="Portfell",
    )
    pages = (
        ("portfell.metadata_builder", "/projects/<project_slug>/metadata-builder", "Metadata Builder", _metadata_layout),
        ("portfell.univariate_statistics", "/projects/<project_slug>/univariate-statistics", "Univariate Statistics", _univariate_layout),
        ("portfell.bivariate_statistics", "/projects/<project_slug>/bivariate-statistics", "Bivariate Statistics", _bivariate_layout),
        ("portfell.multivariate_statistics", "/projects/<project_slug>/multivariate-statistics", "Multivariate Statistics", _multivariate_layout),
    )
    for module, path_template, name, layout in pages:
        register_page(module, path_template=path_template, name=name, layout=layout)
    app.layout = html.Main(page_container, id="portfell-dash-page-container")
    return app


def create_runtime_app_with_dash() -> object:
    """Create the hosted FastAPI app and mount Dash last so `/api` routes keep precedence."""

    application = create_runtime_app()
    dash_app = create_production_dash_app()
    application.mount("/", WSGIMiddleware(dash_app.server), name="portfell-dash")
    return application
