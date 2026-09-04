"""Shared Dash callback orchestration over identifier-only browser state."""

# Dash callback payloads and ``no_update`` are dynamically typed by the
# framework; this adapter boundary is checked by browser/contract tests.
# pyright: reportUnknownMemberType=false, reportUnknownArgumentType=false, reportUnknownVariableType=false, reportArgumentType=false, reportReturnType=false, reportAssignmentType=false, reportUnusedFunction=false, reportAttributeAccessIssue=false, reportGeneralTypeIssues=false

from __future__ import annotations

from collections.abc import Mapping, Sequence
from contextlib import suppress
from dataclasses import replace
from typing import Protocol, cast

from dash import ALL, Dash, Input, Output, State, ctx, no_update

from portfell.dash_app.components import JobProgress
from portfell.dash_app.state import BrowserState, browser_state_from_workflow, with_job_status
from portfell.modules.runtime import ModuleRegistry
from portfell.modules.univariate.ui import data_regions as univariate_data_regions


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

    def metadata_date_range(
        self,
        *,
        exchange: str | None = None,
        instrument_type: str | None = None,
        country: str | None = None,
        currency: str | None = None,
    ) -> dict[str, object] | None: ...

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


def _checked_categories(values: Sequence[object], ids: Sequence[Mapping[str, object]]) -> list[str]:
    return [
        str(item.get("category"))
        for value, item in zip(values, ids, strict=False)
        if (
            (isinstance(value, list) and value)
            or (
                isinstance(value, Mapping)
                and isinstance(value.get("value"), list)
                and value.get("value")
            )
        )
        and item.get("category")
    ]


def univariate_checkbox_predicates(
    dividend_values: Sequence[object],
    dividend_ids: Sequence[Mapping[str, object]],
    age_values: Sequence[object],
    age_ids: Sequence[Mapping[str, object]],
    monthly_values: Sequence[object] = (),
    monthly_ids: Sequence[Mapping[str, object]] = (),
) -> list[dict[str, object]]:
    """Translate the two checklist groups into the exclusive filter contract.

    No checked value means no restriction for that group.  This is important
    on initial page load because Dash's local checklist persistence can briefly
    provide empty values while the durable selection still contains an older
    filter result.
    """
    dividend_allowed: list[str] = []
    for category in _checked_categories(dividend_values, dividend_ids):
        dividend_allowed.extend(["none", "unknown"] if category == "none / unknown" else [category])
    age_allowed = _checked_categories(age_values, age_ids)
    monthly_allowed = _checked_categories(monthly_values, monthly_ids)
    predicates: list[dict[str, object]] = []
    if dividend_allowed:
        predicates.append(
            {
                "metric": "distribution_frequency",
                "operator": "in",
                "allowed": dividend_allowed,
            }
        )
    if age_allowed:
        predicates.append({"metric": "history_age_group", "operator": "in", "allowed": age_allowed})
    if monthly_allowed:
        predicates.append(
            {"metric": "monthly_return_group", "operator": "in", "allowed": monthly_allowed}
        )
    return predicates


def _filter_trigger_is_mounted(
    triggered_id: object,
    *id_groups: Sequence[Mapping[str, object]],
) -> bool:
    """Reject pattern callbacks caused only by removing dynamic components."""
    if not isinstance(triggered_id, Mapping):
        return triggered_id is not None
    return any(dict(triggered_id) == dict(item) for group in id_groups for item in group)


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


def _selected_date_range(
    service: CallbackService, filters: Mapping[str, str | None]
) -> str | None:
    reader = getattr(service, "metadata_date_range", None)
    if not callable(reader):
        return None
    try:
        row = reader(**dict(filters))
    except Exception:
        return None
    if not isinstance(row, Mapping):
        return None
    start, end = row.get("start"), row.get("end")
    if not isinstance(start, str) or not isinstance(end, str):
        return None
    return start if start == end else f"{start} – {end}"


def persisted_browser_state(service: CallbackService) -> BrowserState:
    return browser_state_from_workflow(service.workflow_state())


def execute_action(
    service: CallbackService,
    state: BrowserState,
    *,
    action: str,
    write_service: CallbackService | None = None,
    filters: dict[str, str | None] | None = None,
    predicates: Sequence[Mapping[str, object]] | None = None,
    objective: str = "return_risk",
) -> BrowserState:
    """Execute one explicit command and reconstruct state from persistence afterwards."""
    submitted_job: Mapping[str, object] | None = None
    writer = write_service or service
    try:
        if action == "metadata-create-universe":
            writer.create_universe_and_start_univariate(**dict(filters or {}))
        elif action == "metadata-delete-project":
            if state.universe_id is None:
                return replace(state, message_code="project_not_selected")
            writer.delete_project(state.universe_id)
        elif action == "univariate-save-selection":
            if state.univariate_run_id is None:
                return replace(state, message_code="univariate_not_ready")
            # Univariate owns only its selection artifact. Downstream Bivariate
            # computation is an explicit action on the Bivariate page.
            writer.create_univariate_selection(state.univariate_run_id, predicates=predicates)
        elif action == "univariate-dividend-selection":
            if state.univariate_run_id is None:
                return replace(state, message_code="univariate_not_ready")
            # Persist an explicit empty selection when every checkbox is
            # cleared.  The page renders the full Metadata universe as the
            # unfiltered preview, while the selected-count field is null.
            writer.create_univariate_selection(state.univariate_run_id, predicates=predicates)
        elif action == "bivariate-compute":
            if state.selection_id is None:
                return replace(state, message_code="univariate_selection_not_ready")
            # Submit production runs to the durable background executor so the
            # Dash request returns immediately and polling can reload the
            # persisted pair artifact when it is ready. Keep a synchronous
            # fallback for isolated service fakes and adapters.
            starter = getattr(writer, "start_bivariate_job", None)
            if callable(starter):
                submitted_job = writer.start_bivariate_job(state.selection_id)
            else:
                writer.run_bivariate(state.selection_id)
        elif action == "multivariate-optimize":
            if state.selection_id is None or state.bivariate_run_id is None:
                return replace(state, message_code="bivariate_not_ready")
            active_reader = getattr(service, "active_analysis_job", None)
            if callable(active_reader):
                active = active_reader()
                if isinstance(active, Mapping) and active.get("status") in {"queued", "running"}:
                    return with_job_status(persisted_browser_state(service), active)
            # Optimisation can be expensive.  Submit it to the same durable
            # executor used by the other analysis stages so the Dash request
            # returns immediately and the persisted result is picked up by
            # the normal job poll.  Keep the synchronous path for isolated
            # adapters/tests that do not expose the job API.
            starter = getattr(writer, "start_multivariate_job", None)
            if callable(starter):
                row = writer.start_multivariate_job(
                    selection_id=state.selection_id,
                    bivariate_run_id=state.bivariate_run_id,
                    objective="return_risk",
                )
                if isinstance(row, Mapping):
                    submitted_job = row
            else:
                writer.run_multivariate(
                    selection_id=state.selection_id,
                    bivariate_run_id=state.bivariate_run_id,
                    objective="return_risk",
                )
        elif action == "refresh":
            pass
        else:
            return state
        persisted = persisted_browser_state(service)
        # A very fast worker can finish between submission and the workflow
        # read. Conversely, a database replica may briefly lag and omit the
        # newly queued job. In either case use the submission response as an
        # immediate UI hint so the lower-right progress window is not skipped.
        if submitted_job is not None and persisted.job.status is None:
            persisted = with_job_status(persisted, submitted_job)
        if action == "univariate-dividend-selection" and predicates is not None:
            saver = getattr(service, "save_univariate_filter_preferences", None)
            if callable(saver):
                with suppress(Exception):
                    saver(predicates)
            persisted = replace(
                persisted,
                univariate_filter_predicates=tuple(dict(predicate) for predicate in predicates),
            )
        return persisted
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
    if isinstance(services, ModuleRegistry):
        service = cast(CallbackService, services.workflow)
        metadata_service = cast(CallbackService, services.metadata)
        univariate_service = cast(CallbackService, services.univariate)
        bivariate_service = cast(CallbackService, services.bivariate)
        multivariate_service = cast(CallbackService, services.multivariate)
    else:
        service = cast(CallbackService, services)
        metadata_service = univariate_service = bivariate_service = multivariate_service = service

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
        # During local-store hydration the dynamic sidebar can briefly emit its
        # selected value while the persisted project records are not available
        # yet.  Do not treat that transient event as a real project switch.
        if not state.project_records:
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
            metadata_date_range=_selected_date_range(metadata_service, state.metadata_filters)
            or state.metadata_date_range,
            # Selecting the already active project during page hydration must
            # not clear metadata filters restored from the local browser store.
            metadata_filters=state.metadata_filters,
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
        # Dynamic metadata controls are mounted after the initial layout.  Dash
        # can invoke this callback once while hydrating them; that invocation
        # has no triggering control and carries only empty values.  It must not
        # replace a persisted filter state with nulls.
        if ctx.triggered_id is None:
            return no_update
        normalized = {
            "exchange": exchange,
            "instrument_type": instrument_type,
            "country": country,
            "currency": currency,
        }
        saver = getattr(metadata_service, "save_metadata_filter_preferences", None)
        if callable(saver):
            with suppress(Exception):
                saver(normalized)
            # Filter persistence is best-effort; retain the in-memory state so
            # a temporary database error does not break the UI.
        state = BrowserState.from_store(store)
        selected_count = _selected_isin_count(metadata_service, normalized)
        selected_date_range = _selected_date_range(metadata_service, normalized)
        persisted = getattr(metadata_service, "create_metadata_universe", None)
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
                    starter = getattr(service, "start_univariate_job", None)
                    if callable(starter):
                        with suppress(Exception):
                            starter(universe_id)
            except Exception:
                # Keep the last coherent state if persistence fails; the UI can
                # still display the current selection and retry on the next change.
                pass
        return replace(
            state,
            metadata_member_count=(
                selected_count if selected_count is not None else state.metadata_member_count
            ),
            metadata_date_range=selected_date_range or state.metadata_date_range,
            metadata_filters=normalized,
        ).to_store()

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        Output("pf-browser-state", "data"),
        Input("pf-location", "pathname"),
        State("pf-browser-state", "data"),
        # The browser store uses local storage.  Running this callback during
        # initial hydration can overwrite persisted metadata filters with the
        # empty layout default before Dash restores the local value.
        prevent_initial_call=True,
    )
    def _refresh_state(  # pyright: ignore[reportUnusedFunction]
        _pathname: str | None,
        store: object,
    ) -> dict[str, object]:
        existing = BrowserState.from_store(store)
        # Ignore the transient default store emitted before Dash hydrates its
        # local-storage value; otherwise a reload erases persisted filters.
        if existing == BrowserState():
            return no_update
        refreshed = execute_action(service, BrowserState(), action="refresh")
        selected_count = _selected_isin_count(service, existing.metadata_filters)
        selected_date_range = _selected_date_range(metadata_service, existing.metadata_filters)
        return replace(
            refreshed,
            metadata_filters=existing.metadata_filters,
            univariate_filter_predicates=(
                existing.univariate_filter_predicates or refreshed.univariate_filter_predicates
            ),
            metadata_member_count=(
                selected_count if selected_count is not None else existing.metadata_member_count
            ),
            metadata_date_range=selected_date_range or existing.metadata_date_range,
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
        state = BrowserState.from_store(store)
        refreshed = refresh_job_presentation(service, state)
        if refreshed.job.status in {"succeeded", "failed", "cancelled"}:
            # Completion changes stage readiness and run identifiers in the
            # durable workflow state; reload those identifiers, not just the
            # progress toast.
            persisted = persisted_browser_state(service)
            return replace(
                persisted,
                metadata_filters=state.metadata_filters,
                metadata_member_count=state.metadata_member_count,
                metadata_date_range=state.metadata_date_range,
                univariate_filter_predicates=(
                    state.univariate_filter_predicates or persisted.univariate_filter_predicates
                ),
            ).to_store()
        return refreshed.to_store()

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
            filter_predicates=BrowserState.from_store(_store).univariate_filter_predicates,
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
        # All three groups are inputs to one callback deliberately. A single
        # atomic snapshot prevents a category change from racing another
        # callback and overwriting its current checks with stale values.
        Input({"type": "univariate-dividend-frequency", "category": ALL}, "value"),
        Input({"type": "univariate-age-group", "category": ALL}, "value"),
        Input({"type": "univariate-monthly-return-group", "category": ALL}, "value"),
        State({"type": "univariate-dividend-frequency", "category": ALL}, "id"),
        State({"type": "univariate-age-group", "category": ALL}, "id"),
        State({"type": "univariate-monthly-return-group", "category": ALL}, "id"),
        State("pf-browser-state", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def _save_univariate_filter_selection(
        dividend_values: list[object],
        age_values: list[object],
        monthly_values: list[object],
        dividend_ids: list[dict[str, object]],
        age_ids: list[dict[str, object]],
        monthly_ids: list[dict[str, object]],
        store: object,
    ) -> dict[str, object] | object:
        # Dynamic checkbox components are mounted after the page callback. Dash
        # may invoke this callback once during that mount with no triggering
        # input and empty values. That hydration pass must not overwrite a
        # persisted selection; an actual click (including clearing all checks)
        # always has a triggering component and is persisted below.
        if not _filter_trigger_is_mounted(
            ctx.triggered_id,
            dividend_ids,
            age_ids,
            monthly_ids,
        ):
            return no_update
        state = BrowserState.from_store(store)
        if state.univariate_run_id is None:
            return no_update
        predicates = univariate_checkbox_predicates(
            dividend_values,
            dividend_ids,
            age_values,
            age_ids,
            monthly_values,
            monthly_ids,
        )
        return execute_action(
            service,
            state,
            action="univariate-dividend-selection",
            predicates=predicates,
            write_service=univariate_service,
        ).to_store()

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        Output("pf-browser-state", "data", allow_duplicate=True),
        Input("bivariate-compute", "n_clicks"),
        State("pf-browser-state", "data"),
        prevent_initial_call=True,
        running=[(Output("bivariate-compute", "disabled"), True, False)],
    )
    def _compute_bivariate(  # pyright: ignore[reportUnusedFunction]
        n_clicks: int | None, store: object
    ) -> dict[str, object] | object:
        if not n_clicks:
            return no_update
        return execute_action(
            service,
            BrowserState.from_store(store),
            action="bivariate-compute",
            write_service=bivariate_service,
        ).to_store()

    @app.callback(  # pyright: ignore[reportUnknownMemberType]
        Output("pf-browser-state", "data", allow_duplicate=True),
        Input("multivariate-optimize", "n_clicks"),
        State("pf-browser-state", "data"),
        prevent_initial_call=True,
        running=[(Output("multivariate-optimize", "disabled"), True, False)],
    )
    def _optimize_multivariate(  # pyright: ignore[reportUnusedFunction]
        n_clicks: int | None, store: object
    ) -> dict[str, object] | object:
        if not n_clicks:
            return no_update
        state = BrowserState.from_store(store)
        # The route can render from durable workflow state before Dash has
        # hydrated its local Store.  Rehydrate identifiers here so an
        # immediately available button cannot become a silent no-op.
        if state.selection_id is None or state.bivariate_run_id is None:
            state = persisted_browser_state(service)
        return execute_action(
            service,
            state,
            action="multivariate-optimize",
            write_service=multivariate_service,
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
