from __future__ import annotations

import json

import pytest

from portfell.multivariate.persistence.repository import (
    EvidenceConflictError,
    StoredEvidence,
    get_current_selection,
    put_decision,
)


class _Cursor:
    def __init__(self, *, one=None, many=()) -> None:
        self._one = one
        self._many = many

    def fetchone(self):
        return self._one

    def fetchall(self):
        return self._many


class _Connection:
    def __init__(self) -> None:
        self.decisions: dict[tuple[str, str, str], str] = {}
        self.current: dict[tuple[str, str], tuple[str, str]] = {}
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        self.calls.append((sql, parameters))
        if "from portfell_app.multivariate_decisions" in sql:
            user_id, project_id, decision_id = map(str, parameters)
            payload = self.decisions.get((user_id, project_id, decision_id))
            return _Cursor(one=None if payload is None else (payload,))
        if "insert into portfell_app.multivariate_decisions" in sql:
            decision_id, user_id, project_id, _run_id, _stage, payload = parameters
            self.decisions[(str(user_id), str(project_id), str(decision_id))] = str(payload)
            return _Cursor()
        if "from portfell_app.multivariate_current_selections" in sql:
            user_id, project_id = map(str, parameters)
            value = self.current.get((user_id, project_id))
            return _Cursor(one=value)
        raise AssertionError(sql)


def _evidence(payload: dict[str, object]) -> StoredEvidence:
    return StoredEvidence(
        evidence_id="decision-1",
        run_id="run-1",
        stage="winner_selection",
        canonical_payload=json.dumps(payload),
    )


def test_pr273_same_evidence_id_is_isolated_by_user_and_project() -> None:
    connection = _Connection()
    evidence = _evidence({"winner": "cfg-a"})
    assert put_decision(
        connection, user_id="user-1", project_id="project-a", evidence=evidence
    ) is True
    assert put_decision(
        connection, user_id="user-1", project_id="project-b", evidence=evidence
    ) is True
    assert len(connection.decisions) == 2


def test_pr273_identical_replay_is_noop_but_conflicting_payload_fails_closed() -> None:
    connection = _Connection()
    first = _evidence({"winner": "cfg-a"})
    assert put_decision(
        connection, user_id="user-1", project_id="project-a", evidence=first
    ) is True
    assert put_decision(
        connection, user_id="user-1", project_id="project-a", evidence=first
    ) is False
    with pytest.raises(EvidenceConflictError, match="conflicting decision payload"):
        put_decision(
            connection,
            user_id="user-1",
            project_id="project-a",
            evidence=_evidence({"winner": "cfg-b"}),
        )


def test_pr273_current_selection_lookup_uses_explicit_user_project_pair() -> None:
    connection = _Connection()
    connection.current[("user-1", "project-a")] = (
        "selection-a",
        '{"project":"a","winner":"cfg-a"}',
    )
    connection.current[("user-1", "project-b")] = (
        "selection-b",
        '{"project":"b","winner":"cfg-b"}',
    )
    alpha = get_current_selection(connection, user_id="user-1", project_id="project-a")
    beta = get_current_selection(connection, user_id="user-1", project_id="project-b")
    assert alpha is not None and alpha.selection_revision == "selection-a"
    assert beta is not None and beta.selection_revision == "selection-b"
    assert alpha.canonical_payload != beta.canonical_payload
