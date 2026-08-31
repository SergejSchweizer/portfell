"""Immutable identifier-only browser state and deterministic stage readiness."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Literal, cast

JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


@dataclass(frozen=True, slots=True)
class StageReadiness:
    metadata: bool
    univariate: bool
    bivariate: bool
    multivariate: bool


@dataclass(frozen=True, slots=True)
class JobPresentation:
    stage: str | None = None
    run_id: str | None = None
    status: JobStatus | None = None
    progress: float | None = None

    @property
    def terminal(self) -> bool:
        return self.status in {None, "succeeded", "failed", "cancelled"}


@dataclass(frozen=True, slots=True)
class BrowserState:
    """Identifiers/presentation state only; never market or analytical result authority."""

    workspace_id: str = "default"
    universe_id: str | None = None
    universe_version: int | None = None
    source_snapshot_id: str | None = None
    univariate_run_id: str | None = None
    selection_id: str | None = None
    selection_version: int | None = None
    selected_count: int | None = None
    bivariate_run_id: str | None = None
    multivariate_run_id: str | None = None
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
            stage=_string(job_raw.get("stage")) if job_raw is not None else None,
            run_id=_string(job_raw.get("run_id")) if job_raw is not None else None,
            status=cast(JobStatus | None, status if status in allowed_statuses else None),
            progress=_float(job_raw.get("progress")) if job_raw is not None else None,
        )
        return cls(
            workspace_id=_string(root.get("workspace_id")) or "default",
            universe_id=_string(root.get("universe_id")),
            universe_version=_integer(root.get("universe_version")),
            source_snapshot_id=_string(root.get("source_snapshot_id")),
            univariate_run_id=_string(root.get("univariate_run_id")),
            selection_id=_string(root.get("selection_id")),
            selection_version=_integer(root.get("selection_version")),
            selected_count=_integer(root.get("selected_count")),
            bivariate_run_id=_string(root.get("bivariate_run_id")),
            multivariate_run_id=_string(root.get("multivariate_run_id")),
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

    running = next(
        (
            (stage_name, row)
            for stage_name, row in (
                ("univariate", univariate),
                ("bivariate", bivariate),
                ("multivariate", multivariate),
            )
            if row is not None and row.get("status") in {"queued", "running"}
        ),
        None,
    )
    terminal = next(
        (
            (stage_name, row)
            for stage_name, row in (
                ("multivariate", multivariate),
                ("bivariate", bivariate),
                ("univariate", univariate),
            )
            if row is not None and row.get("status") in {"succeeded", "failed", "cancelled"}
        ),
        None,
    )
    job_source = running or terminal
    job = (
        JobPresentation()
        if job_source is None
        else JobPresentation(
            stage=job_source[0],
            run_id=_field(job_source[1], "run_id"),
            status=cast(JobStatus, job_source[1].get("status")),
            progress=_float(job_source[1].get("progress")),
        )
    )
    return BrowserState(
        workspace_id=_string(workflow.get("workspace_id")) or "default",
        universe_id=universe_id,
        universe_version=_integer(None if universe is None else universe.get("version")),
        source_snapshot_id=_source_snapshot(universe, univariate, bivariate, multivariate),
        univariate_run_id=univariate_id,
        selection_id=selection_id,
        selection_version=_integer(None if selection is None else selection.get("version")),
        selected_count=_integer(None if selection is None else selection.get("member_count")),
        bivariate_run_id=bivariate_id,
        multivariate_run_id=multivariate_id,
        readiness=StageReadiness(
            metadata=metadata_ready,
            univariate=univariate_ready,
            bivariate=bivariate_ready,
            multivariate=multivariate_ready,
        ),
        job=job,
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


def _float(value: object) -> float | None:
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


__all__ = [
    "BrowserState",
    "JobPresentation",
    "StageReadiness",
    "browser_state_from_workflow",
    "invalidate_for_new_bivariate",
    "invalidate_for_new_selection",
    "invalidate_for_new_universe",
]
