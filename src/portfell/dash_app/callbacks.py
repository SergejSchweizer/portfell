"""Shared Dash callback orchestration over identifier-only browser state."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Protocol, cast

from dash import Dash, Input, Output, State, no_update

from portfell.dash_app.components import JobProgress
from portfell.dash_app.state import BrowserState, browser_state_from_workflow, with_job_status


class CallbackService(Protocol):
    def workflow_state(self) -> dict[str, object]: ...

    def active_analysis_job(self) -> dict[str, object] | None: ...

    def analysis_job_status(self, job_id: str) -> dict[str, object]: ...

    def create_metadata_universe(self, **filters: object) -> object: ...

    def run_univariate(self, universe_id: str) -> dict[str, object]: ...

    def create_univariate_selection(
        self, run_id: str, *, predicates: Mapping[str, object] | None = None
    ) -> object: ...

    def run_bivariate(self, selection_id: str) -> dict[str, object]: ...

    def run_multivariate(
        self,
        *,
        selection_id: str,
        bivariate_run_id: str,
        objective: str = "return_risk",
    ) -> dict[str, object]: ...


def persisted_browser_state(service: CallbackService) -> BrowserState:
    return browser_state_from_workflow(service.workflow_state())


def execute_action(
    service: CallbackService,
    state: BrowserState,
    *,
    action: str,
    filters: dict[str, str | None] | None = None,
    objective: str = "return_risk",
) -> BrowserState:
    """Execute one explicit command and reconstruct state from persistence afterwards."""
    try:
        if action == "metadata-create-universe":
            service.create_metadata_universe(**dict(filters or {}))
        elif action == "univariate-compute":
            if state.universe_id is None:
                return replace(state, message_code="metadata_not_ready")
            service.run_univariate(state.universe_id)
        elif action == "univariate-save-selection":
            if state.univariate_run_id is None:
                return replace(state, message_code="univariate_not_ready")
            service.create_univariate_selection(state.univariate_run_id, predicates=None)
        elif action == "bivariate-compute":
            if state.selection_id is None:
                return replace(state, message_code="univariate_selection_not_ready")
            service.run_bivariate(state.selection_id)
        elif action == "multivariate-optimize":
            if state.selection_id is None or state.bivariate_run_id is None:
                return replace(state, message_code="bivariate_not_ready")
            service.run_multivariate(
                selection_id=state.selection_id,
                bivariate_run_id=state.bivariate_run_id,
                objective=objective,
            )
        elif action == "refresh":
            pass
        else:
            return state
        return persisted_browser_state(service)
    except Exception as error:
        code = getattr(error, "code", None)
        try:
            persisted = persisted_browser_state(service)
        except Exception:
            persisted = state
        return replace(
            persisted,
            message_code=str(code) if isinstance(code, str) else "action_failed",
        )


def refresh_job_presentation(service: CallbackService, state: BrowserState) -> BrowserState:
    """Read only the current durable job record; this never invokes computation or market I/O."""
    try:
        row = (
            service.analysis_job_status(state.job.job_id)
            if state.job.job_id is not None
            else service.active_analysis_job()
        )
        return with_job_status(state, row)
    except Exception:
        return state


def register_callbacks(app: Dash, services: object | None) -> None:
    """Register route-safe page actions; GET/render paths never mutate analytical state."""
    if services is None:
        return
    service = cast(CallbackService, services)

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        Output("pf-browser-state", "data"),
        Input("pf-location", "pathname"),
        prevent_initial_call=False,
    )
    def _refresh_state(  # pyright: ignore[reportUnusedFunction]
        _pathname: str | None,
    ) -> dict[str, object]:
        return execute_action(service, BrowserState(), action="refresh").to_store()

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        Output("pf-browser-state", "data", allow_duplicate=True),
        Input("pf-job-poll", "n_intervals"),
        State("pf-browser-state", "data"),
        prevent_initial_call=True,
    )
    def _poll_job(  # pyright: ignore[reportUnusedFunction]
        _poll: int, store: object
    ) -> dict[str, object]:
        return refresh_job_presentation(service, BrowserState.from_store(store)).to_store()

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        Output("pf-job-progress-region", "children"),
        Input("pf-browser-state", "data"),
    )
    def _render_job_progress(store: object) -> object:  # pyright: ignore[reportUnusedFunction]
        return JobProgress(BrowserState.from_store(store).job)

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        Output("pf-browser-state", "data", allow_duplicate=True),
        Input("metadata-create-universe", "n_clicks"),
        State("pf-browser-state", "data"),
        State("metadata-filter-exchange", "value"),
        State("metadata-filter-instrument-type", "value"),
        State("metadata-filter-country", "value"),
        State("metadata-filter-currency", "value"),
        prevent_initial_call=True,
    )
    def _create_universe(  # pyright: ignore[reportUnusedFunction]
        n_clicks: int | None,
        store: object,
        exchange: str | None,
        instrument_type: str | None,
        country: str | None,
        currency: str | None,
    ) -> dict[str, object] | object:
        if not n_clicks:
            return no_update
        return execute_action(
            service,
            BrowserState.from_store(store),
            action="metadata-create-universe",
            filters={
                "exchange": exchange,
                "instrument_type": instrument_type,
                "country": country,
                "currency": currency,
            },
        ).to_store()

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        Output("pf-browser-state", "data", allow_duplicate=True),
        Input("univariate-compute", "n_clicks"),
        State("pf-browser-state", "data"),
        prevent_initial_call=True,
    )
    def _compute_univariate(  # pyright: ignore[reportUnusedFunction]
        n_clicks: int | None, store: object
    ) -> dict[str, object] | object:
        if not n_clicks:
            return no_update
        return execute_action(
            service, BrowserState.from_store(store), action="univariate-compute"
        ).to_store()

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        Output("pf-browser-state", "data", allow_duplicate=True),
        Input("univariate-save-selection", "n_clicks"),
        State("pf-browser-state", "data"),
        prevent_initial_call=True,
    )
    def _save_univariate_selection(  # pyright: ignore[reportUnusedFunction]
        n_clicks: int | None, store: object
    ) -> dict[str, object] | object:
        if not n_clicks:
            return no_update
        return execute_action(
            service, BrowserState.from_store(store), action="univariate-save-selection"
        ).to_store()

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        Output("pf-browser-state", "data", allow_duplicate=True),
        Input("bivariate-compute", "n_clicks"),
        State("pf-browser-state", "data"),
        prevent_initial_call=True,
    )
    def _compute_bivariate(  # pyright: ignore[reportUnusedFunction]
        n_clicks: int | None, store: object
    ) -> dict[str, object] | object:
        if not n_clicks:
            return no_update
        return execute_action(
            service, BrowserState.from_store(store), action="bivariate-compute"
        ).to_store()

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        Output("pf-browser-state", "data", allow_duplicate=True),
        Input("multivariate-optimize", "n_clicks"),
        State("pf-browser-state", "data"),
        State("multivariate-objective", "value"),
        prevent_initial_call=True,
    )
    def _optimize_multivariate(  # pyright: ignore[reportUnusedFunction]
        n_clicks: int | None, store: object, objective: str | None
    ) -> dict[str, object] | object:
        if not n_clicks:
            return no_update
        return execute_action(
            service,
            BrowserState.from_store(store),
            action="multivariate-optimize",
            objective=objective or "return_risk",
        ).to_store()

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        Output("pf-job-poll", "disabled"),
        Input("pf-browser-state", "data"),
    )
    def _polling_disabled(store: object) -> bool:  # pyright: ignore[reportUnusedFunction]
        return BrowserState.from_store(store).job.status not in {"queued", "running"}

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        Output("metadata-filter-exchange", "value"),
        Output("metadata-filter-instrument-type", "value"),
        Output("metadata-filter-country", "value"),
        Output("metadata-filter-currency", "value"),
        Input("metadata-reset-filters", "n_clicks"),
        prevent_initial_call=True,
    )
    def _reset_metadata_filters(  # pyright: ignore[reportUnusedFunction]
        n_clicks: int | None,
    ) -> tuple[None, None, None, None] | object:
        return (None, None, None, None) if n_clicks else no_update


__all__ = [
    "execute_action",
    "persisted_browser_state",
    "refresh_job_presentation",
    "register_callbacks",
]
