from __future__ import annotations

import pytest

from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_project_workflow_projection_repository import ABSENT_PROJECT
from portfell.hosted_project_workflow_reader import PostgresProjectedWorkflowReader


class _Projections:
    def __init__(self, current: object, owned: object) -> None:
        self._current = current
        self._owned = owned
        self.calls: list[tuple[str, str, str | None]] = []

    def read_current(self, *, user_id: str) -> object:
        self.calls.append(("current", user_id, None))
        return self._current

    def read_owned(self, *, user_id: str, project_id: str) -> object:
        self.calls.append(("owned", user_id, project_id))
        return self._owned


def test_projected_workflow_reader_returns_only_current_projection_payload() -> None:
    payload: dict[str, object] = {"schema_version": 1, "stages": {}}
    projections = _Projections((payload, "etag-1"), None)

    row = PostgresProjectedWorkflowReader(projections)("user-1", None)  # type: ignore[arg-type]

    assert row == {"schema_version": 1, "stages": {}, "projection_etag": "etag-1"}
    assert projections.calls == [("current", "user-1", None)]


def test_projected_workflow_reader_has_explicit_empty_and_not_found_responses() -> None:
    empty = PostgresProjectedWorkflowReader(_Projections(None, None))  # type: ignore[arg-type]
    assert empty("user-1", None)["projection_etag"] is None
    assert empty("user-1", "project-1")["projection_etag"] is None

    missing = PostgresProjectedWorkflowReader(_Projections(None, ABSENT_PROJECT))  # type: ignore[arg-type]
    with pytest.raises(HostedApplicationError, match="not_found"):
        missing("user-1", "guessed-project")
