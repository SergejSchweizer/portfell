"""Shared Dash callback orchestration over identifier-only browser state."""

from __future__ import annotations

from dataclasses import replace
from typing import Protocol, cast

from dash import Dash, Input, Output, State, ctx, no_update

from portfell.dash_app.state import BrowserState, browser_state_from_workflow


class CallbackService(Protocol):
    def workflow_state(self) -> dict[str, object]: ...

    def create_metadata_universe(self, **filters: object) -> object: ...

    def run_univariate(self, universe_id: str) -> dict[str, object]: ...

    def create_univariate_selection(self, run_id: str, *, predicates=None) -> object: ...

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
        elif action in {"pf-location", "pf-job-poll"}:
            pass
        else:
            return state
        return persisted_browser_state(service)
    except Exception as error:
        code = getattr(error, "code", None)
        return replace(
            persisted_browser_state(service),
            message_code=str(code) if isinstance(code, str) else "action_failed",
        )


def register_callbacks(app: Dash, services: object | None) -> None:
    """Register one shared mutation callback; route renders themselves remain read-only."""
    if services is None:
        return
    service = cast(CallbackService, services)

    @app.callback(
        Output("pf-browser-state", "data"),
        Input("pf-location", "pathname"),
        Input("pf-job-poll", "n_intervals"),
        Input("metadata-create-universe", "n_clicks"),
        Input("univariate-compute", "n_clicks"),
        Input("univariate-save-selection", "n_clicks"),
        Input("bivariate-compute", "n_clicks"),
        Input("multivariate-optimize", "n_clicks"),
        State("pf-browser-state", "data"),
        State("metadata-filter-exchange", "value"),
        State("metadata-filter-instrument-type", "value"),
        State("metadata-filter-country", "value"),
        State("metadata-filter-currency", "value"),
        State("multivariate-objective", "value"),
        prevent_initial_call=False,
    )
    def _shared_action(
        _pathname: str | None,
        _poll: int,
        _metadata_create: int | None,
        _univariate_compute: int | None,
        _univariate_save: int | None,
        _bivariate_compute: int | None,
        _multivariate_optimize: int | None,
        store: object,
        exchange: str | None,
        instrument_type: str | None,
        country: str | None,
        currency: str | None,
        objective: str | None,
    ) -> dict[str, object]:
        state = BrowserState.from_store(store)
        action = str(ctx.triggered_id or "pf-location")
        updated = execute_action(
            service,
            state,
            action=action,
            filters={
                "exchange": exchange,
                "instrument_type": instrument_type,
                "country": country,
                "currency": currency,
            },
            objective=objective or "return_risk",
        )
        return updated.to_store()

    @app.callback(
        Output("pf-job-poll", "disabled"),
        Input("pf-browser-state", "data"),
    )
    def _polling_disabled(store: object) -> bool:
        return BrowserState.from_store(store).job.terminal

    @app.callback(
        Output("metadata-filter-exchange", "value"),
        Output("metadata-filter-instrument-type", "value"),
        Output("metadata-filter-country", "value"),
        Output("metadata-filter-currency", "value"),
        Input("metadata-reset-filters", "n_clicks"),
        prevent_initial_call=True,
    )
    def _reset_metadata_filters(n_clicks: int | None) -> tuple[None, None, None, None] | object:
        return (None, None, None, None) if n_clicks else no_update


__all__ = ["execute_action", "persisted_browser_state", "register_callbacks"]
