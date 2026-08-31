from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from portfell.app_state.contracts import (
    DecisionArtifactRecord,
    ListingIdentity,
)
from portfell.app_state.errors import (
    APP_STATE_CONFLICT,
    APP_STATE_INVALID_TRANSITION,
    APP_STATE_NOT_FOUND,
    APP_STATE_PERSISTENCE_FAILED,
    AppStateError,
)
from portfell.app_state.repository import PostgresAppStateRepository

NOW = datetime(2026, 8, 31, 20, 0, tzinfo=UTC)
RUN_ROW = (
    "run-a",
    "univariate",
    "succeeded",
    "snapshot-a",
    "universe-a",
    "logical-a",
    "algo-a",
    None,
    NOW,
    NOW,
    NOW,
)
ARTIFACT_ROW = ("artifact-a", "run-a", "summary", "hash-a", {"value": 1}, NOW)
DECISION_ROW = (
    "decision-a",
    "run-m",
    "return_risk",
    "candidate-a",
    "Mean Variance",
    "Mean Variance",
    True,
    True,
    None,
    {"score": 1},
    NOW,
)


class Cursor:
    def __init__(self, rows: list[Sequence[object]]) -> None:
        self.rows = rows

    def fetchone(self) -> Sequence[object] | None:
        return self.rows[0] if self.rows else None

    def fetchall(self) -> list[Sequence[object]]:
        return list(self.rows)


class Connection:
    def __init__(self, rows: list[list[Sequence[object]]], fail_at: int | None = None) -> None:
        self.rows = list(rows)
        self.fail_at = fail_at
        self.executed: list[tuple[str, Sequence[object] | None]] = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, query: str, params: Sequence[object] | None = None) -> Cursor:
        self.executed.append((query, params))
        if self.fail_at == len(self.executed):
            raise RuntimeError("private database detail")
        rows = self.rows.pop(0) if self.rows else []
        return Cursor(rows)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def make_repo(
    rows: list[list[Sequence[object]]], fail_at: int | None = None
) -> tuple[PostgresAppStateRepository, Connection]:
    connection = Connection(rows, fail_at)
    return PostgresAppStateRepository(connection), connection


def code(error: pytest.ExceptionInfo[AppStateError]) -> str:
    return error.value.code


def test_snapshot_existing_create_missing_and_failure() -> None:
    repository, connection = make_repo([[("snap-a", "fp-a", NOW, NOW)]])
    existing = repository.put_market_source_snapshot(
        snapshot_id="ignored", source_fingerprint="fp-a", observed_at=NOW
    )
    assert existing.snapshot_id == "snap-a"
    assert connection.commits == 0

    repository, connection = make_repo([[], [], [("snap-b", "fp-b", NOW, NOW)]])
    created = repository.put_market_source_snapshot(
        snapshot_id="snap-b", source_fingerprint="fp-b", observed_at=NOW
    )
    assert created.source_fingerprint == "fp-b"
    assert connection.commits == 1

    repository, _ = make_repo([[]])
    with pytest.raises(AppStateError) as error:
        repository.get_market_source_snapshot("missing")
    assert code(error) == APP_STATE_NOT_FOUND

    repository, connection = make_repo([[], []], fail_at=2)
    with pytest.raises(AppStateError) as error:
        repository.put_market_source_snapshot(
            snapshot_id="snap-c",
            source_fingerprint="fp-c",
            observed_at=NOW,
        )
    assert code(error) == APP_STATE_PERSISTENCE_FAILED
    assert connection.rollbacks == 1
    assert "private database detail" not in str(error.value)


def test_universe_reads_limits_and_member_validation() -> None:
    universe_row = ("u1", "s1", 2, "h1", NOW, NOW)
    repository, _ = make_repo([[universe_row], [("DE0001", "XETRA", "AAA")]])
    listed = repository.list_metadata_universes(limit=1)
    assert listed[0].members == (ListingIdentity("DE0001", "XETRA", "AAA"),)

    repository, _ = make_repo([[]])
    with pytest.raises(AppStateError) as error:
        repository.get_metadata_universe("missing")
    assert code(error) == APP_STATE_NOT_FOUND

    for limit in (0, 501):
        repository, _ = make_repo([])
        with pytest.raises(AppStateError) as error:
            repository.list_metadata_universes(limit=limit)
        assert code(error) == APP_STATE_CONFLICT

    member = ListingIdentity("DE0001", "XETRA", "AAA")
    invalid_members = (
        (member, member),
        (ListingIdentity(" ", "XETRA", "AAA"),),
    )
    for members in invalid_members:
        repository, _ = make_repo([[]])
        with pytest.raises(AppStateError) as error:
            repository.create_metadata_universe(
                universe_id="invalid",
                source_snapshot_id="snap",
                version=1,
                content_hash="hash",
                members=members,
            )
        assert code(error) == APP_STATE_CONFLICT


def test_analysis_run_create_validation_idempotency_and_failure() -> None:
    repository, connection = make_repo([])
    for stage, status in (
        ("wrong", "queued"),
        ("univariate", "succeeded"),
    ):
        with pytest.raises(AppStateError) as error:
            repository.create_analysis_run(
                run_id="run-x",
                stage=stage,
                status=status,
                input_snapshot_id="s",
                input_ref="u",
                logical_hash="h",
                algorithm_version="a",
            )
        assert code(error) == APP_STATE_INVALID_TRANSITION
    assert connection.executed == []

    repository, connection = make_repo([[("run-a",)], [RUN_ROW]])
    existing = repository.create_analysis_run(
        run_id="different",
        stage="univariate",
        status="queued",
        input_snapshot_id="snapshot-a",
        input_ref="universe-a",
        logical_hash="logical-a",
        algorithm_version="algo-a",
    )
    assert existing.run_id == "run-a"
    assert connection.commits == 0

    running = list(RUN_ROW)
    running[2] = "running"
    running[10] = None
    repository, connection = make_repo([[], [], [tuple(running)]])
    created = repository.create_analysis_run(
        run_id="run-a",
        stage="univariate",
        status="running",
        input_snapshot_id="snapshot-a",
        input_ref="universe-a",
        logical_hash="logical-a",
        algorithm_version="algo-a",
    )
    assert created.status == "running"
    assert connection.commits == 1

    repository, connection = make_repo([[], []], fail_at=2)
    with pytest.raises(AppStateError) as error:
        repository.create_analysis_run(
            run_id="run-f",
            stage="univariate",
            status="queued",
            input_snapshot_id="s",
            input_ref="u",
            logical_hash="h",
            algorithm_version="a",
        )
    assert code(error) == APP_STATE_PERSISTENCE_FAILED
    assert connection.rollbacks == 1


def test_analysis_run_transition_and_read_branches() -> None:
    invalid = (
        ("queued", None),
        ("unknown", None),
        ("failed", None),
        ("succeeded", "unexpected"),
    )
    for status, failure in invalid:
        repository, _ = make_repo([])
        with pytest.raises(AppStateError) as error:
            repository.transition_analysis_run(run_id="run-a", status=status, failure_code=failure)
        assert code(error) == APP_STATE_INVALID_TRANSITION

    running = list(RUN_ROW)
    running[2] = "running"
    running[10] = None
    repository, connection = make_repo([[], [tuple(running)]])
    result = repository.transition_analysis_run(run_id="run-a", status="running")
    assert result.status == "running"
    assert connection.commits == 1

    failed = list(RUN_ROW)
    failed[2] = "failed"
    failed[7] = "calculation_failed"
    repository, connection = make_repo([[], [tuple(failed)]])
    result = repository.transition_analysis_run(
        run_id="run-a", status="failed", failure_code="calculation_failed"
    )
    assert result.failure_code == "calculation_failed"
    assert connection.commits == 1

    repository, connection = make_repo([[]], fail_at=1)
    with pytest.raises(AppStateError) as error:
        repository.transition_analysis_run(run_id="run-a", status="succeeded")
    assert code(error) == APP_STATE_INVALID_TRANSITION
    assert connection.rollbacks == 1

    repository, _ = make_repo([[]])
    with pytest.raises(AppStateError) as error:
        repository.get_analysis_run("missing")
    assert code(error) == APP_STATE_NOT_FOUND

    repository, _ = make_repo([[RUN_ROW]])
    assert repository.list_analysis_runs(limit=1)[0].logical_hash == "logical-a"

    repository, _ = make_repo([[RUN_ROW]])
    staged = repository.list_analysis_runs(stage="univariate", limit=1)
    assert staged[0].stage == "univariate"

    repository, _ = make_repo([])
    with pytest.raises(AppStateError) as error:
        repository.list_analysis_runs(stage="invalid")
    assert code(error) == APP_STATE_NOT_FOUND


def test_analysis_artifact_paths() -> None:
    repository, connection = make_repo([[], [], [ARTIFACT_ROW]])
    created = repository.put_analysis_artifact(
        artifact_id="artifact-a",
        run_id="run-a",
        artifact_type="summary",
        content_hash="hash-a",
        document={"value": 1},
    )
    assert created.document == {"value": 1}
    assert connection.commits == 1

    repository, _ = make_repo([[ARTIFACT_ROW]])
    assert repository.list_analysis_artifacts("run-a")[0].artifact_id == "artifact-a"

    repository, connection = make_repo([[], []], fail_at=2)
    with pytest.raises(AppStateError) as error:
        repository.put_analysis_artifact(
            artifact_id="artifact-b",
            run_id="run-a",
            artifact_type="rows",
            content_hash="hash-b",
            document={"value": 2},
        )
    assert code(error) == APP_STATE_PERSISTENCE_FAILED
    assert connection.rollbacks == 1

    invalid_row = ("a", "r", "t", "h", [1, 2], NOW)
    repository, _ = make_repo([[invalid_row]])
    with pytest.raises(AppStateError) as error:
        repository.list_analysis_artifacts("r")
    assert code(error) == APP_STATE_PERSISTENCE_FAILED


def test_selection_existing_create_list_and_missing() -> None:
    selection = ("sel-a", "run-a", 2, "hash-s", NOW, NOW)
    member = ("DE0001", "XETRA", "AAA")
    identity = ListingIdentity(*member)

    repository, connection = make_repo([[("sel-a",)], [selection], [member]])
    existing = repository.create_univariate_selection(
        selection_id="ignored",
        source_run_id="run-a",
        version=9,
        content_hash="hash-s",
        members=(identity,),
    )
    assert existing.selection_id == "sel-a"
    assert connection.commits == 0

    repository, connection = make_repo([[], [], [], [selection], [member]])
    created = repository.create_univariate_selection(
        selection_id="sel-a",
        source_run_id="run-a",
        version=2,
        content_hash="hash-s",
        members=(identity,),
    )
    assert created.members == (identity,)
    assert connection.commits == 1

    repository, _ = make_repo([[selection], [member]])
    assert repository.list_univariate_selections(limit=1)[0].version == 2

    repository, _ = make_repo([[]])
    with pytest.raises(AppStateError) as error:
        repository.get_univariate_selection("missing")
    assert code(error) == APP_STATE_NOT_FOUND


def put_decision(
    repository: PostgresAppStateRepository, winner: str = "candidate-a"
) -> DecisionArtifactRecord:
    return repository.put_decision_artifact(
        decision_id="decision-a",
        run_id="run-m",
        objective="return_risk",
        winning_candidate_id=winner,
        requested_method="Mean Variance",
        actual_method="Mean Variance",
        available=True,
        production_eligible=True,
        reason=None,
        document={"score": 1},
    )


def test_decision_validation_idempotency_create_and_failure() -> None:
    repository, _ = make_repo([])
    with pytest.raises(AppStateError) as error:
        repository.put_decision_artifact(
            decision_id="d",
            run_id="r",
            objective="invalid",
            winning_candidate_id="c",
            requested_method="m",
            actual_method="m",
            available=True,
            production_eligible=True,
            reason=None,
            document={},
        )
    assert code(error) == APP_STATE_CONFLICT

    repository, connection = make_repo([[DECISION_ROW]])
    assert put_decision(repository).decision_id == "decision-a"
    assert connection.commits == 0

    repository, _ = make_repo([[DECISION_ROW]])
    with pytest.raises(AppStateError) as error:
        put_decision(repository, "candidate-b")
    assert code(error) == APP_STATE_CONFLICT

    repository, connection = make_repo([[], [], [DECISION_ROW]])
    created = put_decision(repository)
    assert created.winning_candidate_id == "candidate-a"
    assert connection.commits == 1

    repository, connection = make_repo([[], []], fail_at=2)
    with pytest.raises(AppStateError) as error:
        repository.put_decision_artifact(
            decision_id="decision-f",
            run_id="run-f",
            objective="minimum_risk",
            winning_candidate_id="candidate-a",
            requested_method="m",
            actual_method="m",
            available=False,
            production_eligible=False,
            reason="unavailable",
            document={},
        )
    assert code(error) == APP_STATE_PERSISTENCE_FAILED
    assert connection.rollbacks == 1

    repository, _ = make_repo([[]])
    with pytest.raises(AppStateError) as error:
        repository.get_decision_artifact("missing")
    assert code(error) == APP_STATE_NOT_FOUND


def test_ui_preference_upsert_reads_lists_and_failures() -> None:
    repository, connection = make_repo([[], [("objective", '"return_risk"', NOW)]])
    record = repository.set_ui_preference("objective", "return_risk")
    assert record.value == "return_risk"
    assert connection.commits == 1

    repository, _ = make_repo([[]])
    assert repository.get_ui_preference("missing") is None

    repository, _ = make_repo([[("a", "1", NOW), ("b", '{"x":2}', NOW)]])
    values = [item.value for item in repository.list_ui_preferences()]
    assert values == [1, {"x": 2}]

    repository, connection = make_repo([[]], fail_at=1)
    with pytest.raises(AppStateError) as error:
        repository.set_ui_preference("x", True)
    assert code(error) == APP_STATE_PERSISTENCE_FAILED
    assert connection.rollbacks == 1

    repository, _ = make_repo([[], []])
    with pytest.raises(AppStateError) as error:
        repository.set_ui_preference("vanishing", None)
    assert code(error) == APP_STATE_NOT_FOUND
