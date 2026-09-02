"""Immutable identifier-only browser state and deterministic stage readiness."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, replace
from typing import Literal, cast

from portfell.dash_app.project_selector import project_options as build_project_options

JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


@dataclass(frozen=True, slots=True)
class StageReadiness:
    metadata: bool
    univariate: bool
    bivariate: bool
    multivariate: bool


@dataclass(frozen=True, slots=True)
class JobPresentation:
    job_id: str | None = None
    stage: str | None = None
    run_id: str | None = None
    status: JobStatus | None = None
    progress_current: int | None = None
    progress_total: int | None = None
    progress_phase: str | None = None
    failure_code: str | None = None

    @property
    def terminal(self) -> bool:
        return self.status in {None, "succeeded", "failed", "cancelled"}

    @property
    def percentage(self) -> float | None:
        if self.progress_total is None or self.progress_total <= 0 or self.progress_current is None:
            return None
        return 100 * self.progress_current / self.progress_total


@dataclass(frozen=True, slots=True)
class BrowserState:
    """Identifiers/presentation state only; never market or analytical result authority."""

    workspace_id: str = "default"
    universe_id: str | None = None
    project_options: tuple[dict[str, str], ...] = ()
    project_records: tuple[dict[str, object], ...] = ()
    metadata_filters: dict[str, str | None] = field(default_factory=dict)
    metadata_member_count: int | None = None
    metadata_created_at: str | None = None
    universe_version: int | None = None
    source_snapshot_id: str | None = None
    univariate_run_id: str | None = None
    selection_id: str | None = None
    selection_version: int | None = None
    selected_count: int | None = None
    bivariate_run_id: str | None = None
    multivariate_run_id: str | None = None
    # Revision-safe presentation identifiers.  These are deliberately plain IDs;
    # result payloads never live in browser state.
    current_input_revision: str | None = None
    current_job_id: str | None = None
    current_ready_run: str | None = None
    previous_ready_run: str | None = None
    current_ready_runs: dict[str, str] | None = None
    previous_ready_runs: dict[str, str] | None = None
    readiness: StageReadiness = StageReadiness(False, False, False, False)
    job: JobPresentation = JobPresentation()
    message_code: str | None = None

    def to_store(self) -> dict[str, object]:
        return cast(dict[str, object], asdict(self))

    @classmethod
    def from_store(cls, value: object) -> BrowserState:
        root = _mapping(value)
        if root is None:
            return cls()
        readiness_raw = _mapping(root.get("readiness"))
        readiness = (
            StageReadiness(
                metadata=bool(readiness_raw.get("metadata")),
                univariate=bool(readiness_raw.get("univariate")),
                bivariate=bool(readiness_raw.get("bivariate")),
                multivariate=bool(readiness_raw.get("multivariate")),
            )
            if readiness_raw is not None
            else StageReadiness(False, False, False, False)
        )
        job_raw = _mapping(root.get("job"))
        status = job_raw.get("status") if job_raw is not None else None
        allowed_statuses = {"queued", "running", "succeeded", "failed", "cancelled"}
        job = JobPresentation(
            job_id=_string(job_raw.get("job_id")) if job_raw is not None else None,
            stage=_string(job_raw.get("stage")) if job_raw is not None else None,
            run_id=_string(job_raw.get("run_id")) if job_raw is not None else None,
            status=cast(JobStatus | None, status if status in allowed_statuses else None),
            progress_current=(
                _integer(job_raw.get("progress_current")) if job_raw is not None else None
            ),
            progress_total=_integer(job_raw.get("progress_total")) if job_raw is not None else None,
            progress_phase=_string(job_raw.get("progress_phase")) if job_raw is not None else None,
            failure_code=_string(job_raw.get("failure_code")) if job_raw is not None else None,
        )
        return cls(
            workspace_id=_string(root.get("workspace_id")) or "default",
            universe_id=_string(root.get("universe_id")),
            project_options=_project_options(root.get("project_options")),
            project_records=tuple(
                row for row in _rows(root.get("project_records")) if row.get("universe_id")
            ),
            metadata_filters=_metadata_filters(root.get("metadata_filters")),
            metadata_member_count=_integer(root.get("metadata_member_count")),
            metadata_created_at=_string(root.get("metadata_created_at")),
            universe_version=_integer(root.get("universe_version")),
            source_snapshot_id=_string(root.get("source_snapshot_id")),
            univariate_run_id=_string(root.get("univariate_run_id")),
            selection_id=_string(root.get("selection_id")),
            selection_version=_integer(root.get("selection_version")),
            selected_count=_integer(root.get("selected_count")),
            bivariate_run_id=_string(root.get("bivariate_run_id")),
            multivariate_run_id=_string(root.get("multivariate_run_id")),
            current_input_revision=_string(root.get("current_input_revision")),
            current_job_id=_string(root.get("current_job_id")),
            current_ready_run=_string(root.get("current_ready_run")),
            previous_ready_run=_string(root.get("previous_ready_run")),
            current_ready_runs=_string_map(root.get("current_ready_runs")),
            previous_ready_runs=_string_map(root.get("previous_ready_runs")),
            readiness=readiness,
            job=job,
            message_code=_string(root.get("message_code")),
        )


def browser_state_from_workflow(workflow: Mapping[str, object]) -> BrowserState:
    """Reconstruct browser state only from persisted service identifiers and statuses."""
    universe = _mapping(workflow.get("metadata_universe"))
    selection = _mapping(workflow.get("univariate_selection"))
    stages = _mapping(workflow.get("stages")) or {}
    univariate = _mapping(stages.get("univariate"))
    bivariate = _mapping(stages.get("bivariate"))
    multivariate = _mapping(stages.get("multivariate"))

    universe_id = _field(universe, "universe_id")
    univariate_id = _field(univariate, "run_id")
    selection_id = _field(selection, "selection_id")
    bivariate_id = _field(bivariate, "run_id")
    multivariate_id = _field(multivariate, "run_id")

    # The service supplies bounded stage history.  Select by the exact dependency
    # reference, never by "latest run" alone, so a new revision cannot inherit old
    # analytical evidence while it is computing.
    history = _mapping(workflow.get("history")) or {}
    expected = {
        "univariate": universe_id,
        "bivariate": selection_id,
        "multivariate": bivariate_id,
    }
    current_ready: dict[str, str] = {}
    previous_ready: dict[str, str] = {}
    for stage, input_ref in expected.items():
        candidates = _rows(history.get(stage))
        if not candidates:
            latest = _mapping(stages.get(stage))
            candidates = [] if latest is None else [latest]
        matching = [
            row
            for row in candidates
            if row.get("status") == "succeeded"
            and input_ref is not None
            and _field(row, "input_ref") == input_ref
            and _field(row, "run_id") is not None
        ]
        if matching:
            current_ready[stage] = cast(str, _field(matching[0], "run_id"))
        previous = [
            row
            for row in candidates
            if row.get("status") == "succeeded"
            and _field(row, "run_id") is not None
            and (input_ref is None or _field(row, "input_ref") != input_ref)
        ]
        if previous:
            previous_ready[stage] = cast(str, _field(previous[0], "run_id"))

    metadata_ready = universe_id is not None
    univariate_ready = (
        metadata_ready
        and univariate is not None
        and univariate.get("status") == "succeeded"
        and _field(univariate, "input_ref") == universe_id
        and selection is not None
        and _field(selection, "source_run_id") == univariate_id
    )
    bivariate_ready = (
        univariate_ready
        and bivariate is not None
        and bivariate.get("status") == "succeeded"
        and _field(bivariate, "input_ref") == selection_id
    )
    multivariate_ready = (
        bivariate_ready
        and multivariate is not None
        and multivariate.get("status") == "succeeded"
        and _field(multivariate, "input_ref") == bivariate_id
    )

    job_source = _mapping(workflow.get("active_job"))
    job = (
        JobPresentation()
        if job_source is None
        else JobPresentation(
            job_id=_field(job_source, "job_id"),
            stage=_field(job_source, "stage"),
            run_id=_field(job_source, "run_id"),
            status=cast(JobStatus, job_source.get("status")),
            progress_current=_integer(job_source.get("progress_current")),
            progress_total=_integer(job_source.get("progress_total")),
            progress_phase=_field(job_source, "progress_phase"),
            failure_code=_field(job_source, "failure_code"),
        )
    )
    current_input_revision = (
        None
        if universe_id is None
        else f"universe:{universe_id}|selection:{selection_id or 'none'}"
    )
    current_ready_run = (
        current_ready.get("multivariate")
        or current_ready.get("bivariate")
        or current_ready.get("univariate")
    )
    previous_ready_run = (
        previous_ready.get("multivariate")
        or previous_ready.get("bivariate")
        or previous_ready.get("univariate")
    )
    universe_members = _rows(None if universe is None else universe.get("members"))
    unique_universe_isins = {
        str(member.get("isin"))
        for member in universe_members
        if member.get("isin") not in {None, ""}
    }
    metadata_count = (
        len(unique_universe_isins)
        if universe_members
        else _integer(None if universe is None else universe.get("member_count"))
    )
    return BrowserState(
        workspace_id=_string(workflow.get("workspace_id")) or "default",
        universe_id=universe_id,
        project_options=tuple(
            {
                "label": str(item.get("label", "")),
                "value": str(item.get("value", "")),
            }
            for item in build_project_options(_rows(workflow.get("metadata_universes")))
        ),
        project_records=tuple(_rows(workflow.get("metadata_universes"))),
        metadata_member_count=metadata_count,
        metadata_created_at=_field(universe, "created_at"),
        universe_version=_integer(None if universe is None else universe.get("version")),
        source_snapshot_id=_source_snapshot(universe, univariate, bivariate, multivariate),
        univariate_run_id=univariate_id,
        selection_id=selection_id,
        selection_version=_integer(None if selection is None else selection.get("version")),
        selected_count=_integer(None if selection is None else selection.get("member_count")),
        bivariate_run_id=bivariate_id,
        multivariate_run_id=multivariate_id,
        current_input_revision=current_input_revision,
        current_job_id=job.job_id,
        current_ready_run=current_ready_run,
        previous_ready_run=previous_ready_run,
        current_ready_runs=current_ready or None,
        previous_ready_runs=previous_ready or None,
        readiness=StageReadiness(
            metadata=metadata_ready,
            univariate=univariate_ready,
            bivariate=bivariate_ready,
            multivariate=multivariate_ready,
        ),
        job=job,
    )


def with_job_status(state: BrowserState, row: Mapping[str, object] | None) -> BrowserState:
    """Replace only job presentation fields after a cheap persisted-status poll."""
    if row is None:
        return state
    status = row.get("status")
    allowed_statuses = {"queued", "running", "succeeded", "failed", "cancelled"}
    if status not in allowed_statuses:
        return state
    return replace(
        state,
        current_job_id=_string(row.get("job_id")),
        job=JobPresentation(
            job_id=_string(row.get("job_id")),
            stage=_string(row.get("stage")),
            run_id=_string(row.get("run_id")),
            status=cast(JobStatus, status),
            progress_current=_integer(row.get("progress_current")),
            progress_total=_integer(row.get("progress_total")),
            progress_phase=_string(row.get("progress_phase")),
            failure_code=_string(row.get("failure_code")),
        ),
    )


def invalidate_for_new_universe(
    state: BrowserState, universe_id: str, version: int | None
) -> BrowserState:
    return BrowserState(
        universe_id=universe_id,
        universe_version=version,
        source_snapshot_id=state.source_snapshot_id,
        readiness=StageReadiness(True, False, False, False),
        message_code="metadata_revision_changed",
    )


def invalidate_for_new_selection(
    state: BrowserState, selection_id: str, version: int | None, selected_count: int | None
) -> BrowserState:
    return BrowserState(
        workspace_id=state.workspace_id,
        universe_id=state.universe_id,
        universe_version=state.universe_version,
        source_snapshot_id=state.source_snapshot_id,
        univariate_run_id=state.univariate_run_id,
        selection_id=selection_id,
        selection_version=version,
        selected_count=selected_count,
        readiness=StageReadiness(state.readiness.metadata, True, False, False),
        message_code="univariate_selection_changed",
    )


def invalidate_for_new_bivariate(state: BrowserState, run_id: str) -> BrowserState:
    return BrowserState(
        workspace_id=state.workspace_id,
        universe_id=state.universe_id,
        universe_version=state.universe_version,
        source_snapshot_id=state.source_snapshot_id,
        univariate_run_id=state.univariate_run_id,
        selection_id=state.selection_id,
        selection_version=state.selection_version,
        selected_count=state.selected_count,
        bivariate_run_id=run_id,
        readiness=StageReadiness(True, True, True, False),
        message_code="bivariate_revision_changed",
    )


def _source_snapshot(*rows: dict[str, object] | None) -> str | None:
    for row in reversed(rows):
        if row is None:
            continue
        value = _field(row, "input_snapshot_id") or _field(row, "source_snapshot_id")
        if value:
            return value
    return None


def _mapping(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    return cast(dict[str, object], value)


def _field(row: dict[str, object] | None, name: str) -> str | None:
    return None if row is None else _string(row.get(name))


def _string(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _integer(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _rows(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    rows: list[dict[str, object]] = []
    for item in cast(list[object], value):
        if isinstance(item, dict):
            rows.append(cast(dict[str, object], item))
    return rows


def _string_map(value: object) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    result: dict[str, str] = {}
    for key, item in cast(dict[object, object], value).items():
        if isinstance(item, str):
            result[str(key)] = item
    return result or None


def _project_options(value: object) -> tuple[dict[str, str], ...]:
    rows = _rows(value)
    return tuple(
        {"label": str(row.get("label", "")), "value": str(row.get("value", ""))}
        for row in rows
        if row.get("value")
    )


def _metadata_filters(value: object) -> dict[str, str | None]:
    if not isinstance(value, dict):
        return {}
    return {
        field: value.get(field) if isinstance(value.get(field), str) else None
        for field in ("exchange", "instrument_type", "country", "currency")
    }


__all__ = [
    "BrowserState",
    "JobPresentation",
    "StageReadiness",
    "browser_state_from_workflow",
    "invalidate_for_new_bivariate",
    "invalidate_for_new_selection",
    "invalidate_for_new_universe",
    "with_job_status",
]
