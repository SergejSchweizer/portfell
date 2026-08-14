"""Pure route-facing readers for compact project workflow projections."""

from __future__ import annotations

from typing import cast

from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_project_workflow_projection_repository import (
    ABSENT_PROJECT,
    PostgresProjectWorkflowProjection,
)
from portfell.table_io import JsonRow
from portfell.workflow_state import resolve_workflow


class PostgresProjectedWorkflowReader:
    """Serve workflow status only from RLS-bound compact projections."""

    def __init__(self, projections: PostgresProjectWorkflowProjection) -> None:
        self._projections = projections

    def __call__(self, user_id: str, project_id: str | None) -> JsonRow:
        if project_id is None:
            row = self._projections.read_current(user_id=user_id)
            return _empty_workflow() if row is None else _row(row)
        row = self._projections.read_owned(user_id=user_id, project_id=project_id)
        if row is ABSENT_PROJECT:
            raise HostedApplicationError(404, "not_found")
        return _empty_workflow() if row is None else _row(cast(tuple[JsonRow, str], row))


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
