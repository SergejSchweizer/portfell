"""Pure route-facing readers for compact project workflow projections."""

from __future__ import annotations

import json
from collections.abc import Callable
from time import monotonic
from typing import cast

from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_project_workflow_projection_repository import (
    ABSENT_PROJECT,
    PostgresProjectWorkflowProjection,
)
from portfell.hosted_workflow_read_metrics import WorkflowReadMetrics, WorkflowReadObservation
from portfell.table_io import JsonRow
from portfell.workflow_state import resolve_workflow


class PostgresProjectedWorkflowReader:
    """Serve workflow status only from RLS-bound compact projections."""

    def __init__(
        self,
        projections: PostgresProjectWorkflowProjection,
        *,
        metrics: WorkflowReadMetrics | None = None,
        statement_count: Callable[[], int | None] | None = None,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._projections = projections
        self._metrics = metrics
        self._statement_count = statement_count
        self._clock = clock

    def __call__(self, user_id: str, project_id: str | None) -> JsonRow:
        started = self._clock()
        before = None if self._statement_count is None else self._statement_count()
        if project_id is None:
            row = self._projections.read_current(user_id=user_id)
            result = _empty_workflow() if row is None else _row(row)
            self._record("workflow", result, before, started)
            return result
        row = self._projections.read_owned(user_id=user_id, project_id=project_id)
        if row is ABSENT_PROJECT:
            raise HostedApplicationError(404, "not_found")
        result = _empty_workflow() if row is None else _row(cast(tuple[JsonRow, str], row))
        self._record("project_workflow", result, before, started)
        return result

    def _record(self, route: str, result: JsonRow, before: int | None, started: float) -> None:
        if self._metrics is None:
            return
        after = None if self._statement_count is None else self._statement_count()
        statements = None if before is None or after is None else after - before
        encoded = json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
        self._metrics.record(
            WorkflowReadObservation(
                route=route,
                statement_count=statements,
                response_bytes=len(encoded),
                shared_file_reads=0,
                elapsed_seconds=max(0.0, self._clock() - started),
            )
        )


def _row(row: tuple[JsonRow, str]) -> JsonRow:
    payload, etag = row
    return {**payload, "projection_etag": etag}


def _empty_workflow() -> JsonRow:
    return {
        "schema_version": 1,
        "stages": resolve_workflow(
            metadata_revision_id=None, metadata_selection_id=None, quote_run_id=None
        ),
        "process_overview": {"metadata_downloaded_isins": None},
        "projection_etag": None,
    }
