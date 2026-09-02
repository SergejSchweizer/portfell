"""Shared Dash callback orchestration over identifier-only browser state."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Protocol, cast

from dash import Dash, Input, Output, State, no_update

from portfell.dash_app.components import JobProgress
from portfell.dash_app.pages.univariate import data_regions as univariate_data_regions
from portfell.dash_app.state import BrowserState, browser_state_from_workflow, with_job_status


class CallbackService(Protocol):
    def workflow_state(self) -> dict[str, object]: ...

    def active_listings(
        self,
        *,
        exchange: str | None = None,
        instrument_type: str | None = None,
        country: str | None = None,
        currency: str | None = None,
    ) -> tuple[dict[str, object], ...]: ...

    def active_analysis_job(self) -> dict[str, object] | None: ...

    def analysis_job_status(self, job_id: str) -> dict[str, object]: ...

    def create_universe_and_start_univariate(self, **filters: object) -> object: ...

    def create_metadata_universe(self, **filters: object) -> object: ...

    def delete_project(self, universe_id: str) -> None: ...

    def create_univariate_selection(
        self, run_id: str, *, predicates: Sequence[Mapping[str, object]] | None = None
    ) -> object: ...

    def create_selection_and_start_downstream(
        self, run_id: str, *, predicates: Sequence[Mapping[str, object]] | None = None
    ) -> object: ...

    def run_bivariate(self, selection_id: str) -> dict[str, object]: ...

    def run_multivariate(
        self,
        *,
        selection_id: str,
        bivariate_run_id: str,
        objective: str = "return_risk",
    ) -> dict[str, object]: ...


def _integer_value(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _selected_isin_count(service: CallbackService, filters: Mapping[str, str | None]) -> int | None:
    """Return the unique selected ISIN count, retaining compatibility with test fakes."""
    reader = getattr(service, "active_listings", None)
    if not callable(reader):
        return None
    try:
        rows = reader(**dict(filters))
    except Exception:
        return None
    return len({str(row.get("isin")) for row in rows if row.get("isin")})


def persisted_browser_state(service: CallbackService) -> BrowserState:
    return browser_state_from_workflow(service.workflow_state())


def execute_action(
    service: CallbackService,
    state: BrowserState,
    *,
    action: str,
    filters: dict[str, str | None] | None = None,
    predicates: Sequence[Mapping[str, object]] | None = None,
    objective: str = "return_risk",
) -> BrowserState:
    """Execute one explicit command and reconstruct state from persistence afterwards."""
    try:
        if action == "metadata-create-universe":
            service.create_universe_and_start_univariate(**dict(filters or {}))
        elif action == "metadata-delete-project":
            if state.universe_id is None:
                return replace(state, message_code="project_not_selected")
            service.delete_project(state.universe_id)
        elif action == "univariate-save-selection":
            if state.univariate_run_id is None:
                return replace(state, message_code="univariate_not_ready")
            if hasattr(service, "create_selection_and_start_downstream"):
                service.create_selection_and_start_downstream(
                    state.univariate_run_id, predicates=predicates
                )
            else:
                # Compatibility for isolated page fixtures; production service owns
                # the atomic selection-to-downstream transition above.
                service.create_univariate_selection(state.univariate_run_id, predicates=predicates)
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
        Output("pf-browser-state", "data", allow_duplicate=True),
        Input("sidebar-project-selection", "value"),
        State("pf-browser-state", "data"),
        prevent_initial_call=True,
    )
    def _select_project(  # pyright: ignore[reportUnusedFunction]
        selected_id: str | None, store: object
    ) -> dict[str, object] | object:
        state = BrowserState.from_store(store)
        if not selected_id:
            return no_update
        project = next(
            (row for row in state.project_records if row.get("universe_id") == selected_id),
            None,
        )
        if project is None:
            return no_update
        return replace(
            state,
            universe_id=selected_id,
            universe_version=_integer_value(project.get("version")),
            metadata_member_count=_integer_value(project.get("member_count")),
            metadata_created_at=(
                str(project.get("created_at")) if project.get("created_at") else None
            ),
            source_snapshot_id=(
                str(project.get("source_snapshot_id"))
                if project.get("source_snapshot_id")
                else None
            ),
            metadata_filters={},
        ).to_store()

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        Output("pf-browser-state", "data", allow_duplicate=True),
        Input("metadata-filter-exchange", "value"),
        Input("metadata-filter-instrument-type", "value"),
        Input("metadata-filter-country", "value"),
        Input("metadata-filter-currency", "value"),
        State("pf-browser-state", "data"),
        prevent_initial_call=True,
    )
    def _update_metadata_filters(
        exchange: str | None,
        instrument_type: str | None,
        country: str | None,
        currency: str | None,
        store: object,
    ) -> dict[str, object]:
        normalized = {
            "exchange": exchange,
            "instrument_type": instrument_type,
            "country": country,
            "currency": currency,
        }
        state = BrowserState.from_store(store)
        selected_count = _selected_isin_count(service, normalized)
        persisted = getattr(service, "create_metadata_universe", None)
        if callable(persisted):
            try:
                universe = persisted(**normalized)
                universe_id = getattr(universe, "universe_id", None)
                version = getattr(universe, "version", None)
                snapshot_id = getattr(universe, "source_snapshot_id", None)
                if isinstance(universe, Mapping):
                    universe_id = universe.get("universe_id")
                    version = universe.get("version")
                    snapshot_id = universe.get("source_snapshot_id")
                if isinstance(universe_id, str):
                    state = replace(
                        state,
                        universe_id=universe_id,
                        universe_version=_integer_value(version),
                        source_snapshot_id=(
                            str(snapshot_id)
                            if snapshot_id is not None
                            else state.source_snapshot_id
                        ),
                    )
            except Exception:
                # Keep the last coherent state if persistence fails; the UI can
                # still display the current selection and retry on the next change.
                pass
        return replace(
            state,
            metadata_member_count=(
                selected_count if selected_count is not None else state.metadata_member_count
            ),
            metadata_filters=normalized,
        ).to_store()

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        Output("pf-browser-state", "data"),
        Input("pf-location", "pathname"),
        State("pf-browser-state", "data"),
        prevent_initial_call=False,
    )
    def _refresh_state(  # pyright: ignore[reportUnusedFunction]
        _pathname: str | None, store: object,
    ) -> dict[str, object]:
        refreshed = execute_action(service, BrowserState(), action="refresh")
        existing = BrowserState.from_store(store)
        selected_count = _selected_isin_count(service, existing.metadata_filters)
        return replace(
            refreshed,
            metadata_filters=existing.metadata_filters,
            metadata_member_count=(
                selected_count
                if selected_count is not None
                else existing.metadata_member_count
            ),
        ).to_store()

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
        Output("univariate-data-regions", "children"),
        Input("pf-browser-state", "data"),
    )
    def _refresh_univariate_regions(  # pyright: ignore[reportUnusedFunction]
        _store: object,
    ) -> object:
        return univariate_data_regions(
            service,
            metadata_member_count=BrowserState.from_store(_store).metadata_member_count,
        )

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        Output("bivariate-continue-multivariate", "href"),
        Output("bivariate-continue-multivariate", "aria-disabled"),
        Output("bivariate-continue-multivariate", "className"),
        Input("pf-browser-state", "data"),
    )
    def _refresh_bivariate_continue(  # pyright: ignore[reportUnusedFunction]
        store: object,
    ) -> tuple[str, str, str]:
        ready = BrowserState.from_store(store).readiness.bivariate
        return (
            "/multivariate" if ready else "#",
            "false" if ready else "true",
            "pf-button pf-button-primary" if ready else "pf-button",
        )

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        Output("pf-browser-state", "data", allow_duplicate=True),
        Input("univariate-save-selection", "n_clicks"),
        State("pf-browser-state", "data"),
        prevent_initial_call=True,
    )
    def _save_univariate_selection(  # pyright: ignore[reportUnusedFunction]
        n_clicks: int | None,
        store: object,
    ) -> dict[str, object] | object:
        if not n_clicks:
            return no_update
        return execute_action(
            service,
            BrowserState.from_store(store),
            action="univariate-save-selection",
            predicates=None,
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


__all__ = [
    "execute_action",
    "persisted_browser_state",
    "refresh_job_presentation",
    "register_callbacks",
]
