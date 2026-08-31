from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from portfell.app_state.contracts import ListingIdentity
from portfell.app_state.errors import (
    APP_STATE_CONFLICT,
    APP_STATE_PERSISTENCE_FAILED,
    AppStateError,
)
from portfell.app_state.repository import PostgresAppStateRepository


class ScriptedCursor:
    def __init__(self, rows: list[Sequence[object]]) -> None:
        self._rows = rows

    def fetchone(self) -> Sequence[object] | None:
        return None if not self._rows else self._rows[0]

    def fetchall(self) -> list[Sequence[object]]:
        return list(self._rows)


class ScriptedConnection:
    def __init__(self, rows: list[list[Sequence[object]]], *, fail_at: int | None = None) -> None:
        self._rows = list(rows)
        self._fail_at = fail_at
        self.executed: list[tuple[str, Sequence[object] | None]] = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, query: str, params: Sequence[object] | None = None) -> ScriptedCursor:
        self.executed.append((query, params))
        if self._fail_at is not None and len(self.executed) == self._fail_at:
            raise RuntimeError("database detail that must stay redacted")
        rows = self._rows.pop(0) if self._rows else []
        return ScriptedCursor(rows)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def test_metadata_universe_write_is_parameterized_canonical_and_single_transaction() -> None:
    created = datetime(2026, 8, 30, tzinfo=UTC)
    connection = ScriptedConnection(
        [
            [],
            [],
            [],
            [],
            [("universe-a", "snapshot-a", 1, "hash-a", created, created)],
            [
                ("DE000B", "XETRA", "BBB"),
                ("DE000A", "XETRA", "AAA"),
            ],
        ]
    )
    repository = PostgresAppStateRepository(connection)
    record = repository.create_metadata_universe(
        universe_id="universe-a",
        source_snapshot_id="snapshot-a",
        version=1,
        content_hash="hash-a",
        members=(
            ListingIdentity("DE000B", "XETRA", "BBB"),
            ListingIdentity("DE000A", "XETRA", "AAA"),
        ),
    )
    assert record.universe_id == "universe-a"
    assert record.members == (
        ListingIdentity("DE000B", "XETRA", "BBB"),
        ListingIdentity("DE000A", "XETRA", "AAA"),
    )
    member_writes = [
        entry for entry in connection.executed if "metadata_universe_members" in entry[0]
    ]
    assert member_writes[0][1] == ("universe-a", "DE000A", "XETRA", "AAA", 0)
    assert member_writes[1][1] == ("universe-a", "DE000B", "XETRA", "BBB", 1)
    assert all("DE000A" not in query and "DE000B" not in query for query, _ in connection.executed)
    assert connection.commits == 1
    assert connection.rollbacks == 0


def test_content_identity_converges_to_existing_immutable_universe() -> None:
    created = datetime(2026, 8, 30, tzinfo=UTC)
    connection = ScriptedConnection(
        [
            [("existing-universe",)],
            [("existing-universe", "snapshot-a", 3, "same-hash", created, created)],
            [("DE000A", "XETRA", "AAA")],
        ]
    )
    repository = PostgresAppStateRepository(connection)
    record = repository.create_metadata_universe(
        universe_id="different-request-id",
        source_snapshot_id="snapshot-a",
        version=9,
        content_hash="same-hash",
        members=(ListingIdentity("DE000A", "XETRA", "AAA"),),
    )
    assert record.universe_id == "existing-universe"
    assert connection.commits == 0
    assert all(
        "insert into portfell.metadata_universes" not in query
        for query, _ in connection.executed
    )


def test_write_failure_rolls_back_and_exposes_only_typed_error() -> None:
    connection = ScriptedConnection([[], []], fail_at=2)
    repository = PostgresAppStateRepository(connection)
    with pytest.raises(AppStateError) as captured:
        repository.create_univariate_selection(
            selection_id="selection-a",
            source_run_id="run-a",
            version=1,
            content_hash="hash-a",
            members=(ListingIdentity("DE000A", "XETRA", "AAA"),),
        )
    assert captured.value.code == APP_STATE_PERSISTENCE_FAILED
    assert "database detail" not in str(captured.value)
    assert connection.rollbacks == 1
    assert connection.commits == 0


def test_existing_artifact_with_different_content_is_typed_conflict() -> None:
    created = datetime(2026, 8, 30, tzinfo=UTC)
    connection = ScriptedConnection(
        [[("artifact-a", "run-a", "summary", "old-hash", {"value": 1}, created)]]
    )
    repository = PostgresAppStateRepository(connection)
    with pytest.raises(AppStateError) as captured:
        repository.put_analysis_artifact(
            artifact_id="artifact-b",
            run_id="run-a",
            artifact_type="summary",
            content_hash="new-hash",
            document={"value": 2},
        )
    assert captured.value.code == APP_STATE_CONFLICT
    assert connection.commits == 0


def test_repository_module_has_no_legacy_or_market_sql_dependency() -> None:
    source = (
        Path(__file__).resolve().parents[1] / "src" / "portfell" / "app_state" / "repository.py"
    ).read_text(encoding="utf-8")
    assert "portfell.hosted_" not in source
    assert "xetra_loader" not in source
    assert "market_source." not in source
    assert " user_id " not in source
    assert " project_id " not in source
