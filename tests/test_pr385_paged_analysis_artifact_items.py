from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from portfell.app_state.contracts import AnalysisArtifactItem
from portfell.app_state.errors import (
    APP_STATE_CONFLICT,
    APP_STATE_PERSISTENCE_FAILED,
    AppStateError,
)
from portfell.app_state.migration import APP_STATE_MIGRATIONS
from portfell.app_state.migrations.v003_analysis_artifact_items import MIGRATION_V003
from portfell.app_state.repository import PostgresAppStateRepository
from portfell.app_state.schema import APP_STATE_TABLES

NOW = datetime(2026, 9, 1, tzinfo=UTC)
MANIFEST = {"schema": "univariate.rows@v2", "storage": "row_items", "item_count": 2}
ARTIFACT = ("artifact-a", "run-a", "univariate.rows@v2", "hash-a", MANIFEST, NOW)


class Cursor:
    def __init__(self, rows: list[Sequence[object]]) -> None:
        self.rows = rows

    def fetchone(self) -> Sequence[object] | None:
        return self.rows[0] if self.rows else None

    def fetchall(self) -> list[Sequence[object]]:
        return list(self.rows)


class Connection:
    def __init__(self, rows: list[list[Sequence[object]]], *, fail_at: int | None = None) -> None:
        self.rows = list(rows)
        self.fail_at = fail_at
        self.executed: list[tuple[str, Sequence[object] | None]] = []
        self.commits = 0
        self.rollbacks = 0

    def execute(self, query: str, params: Sequence[object] | None = None) -> Cursor:
        self.executed.append((query, params))
        if self.fail_at == len(self.executed):
            raise RuntimeError("database detail must be redacted")
        return Cursor(self.rows.pop(0) if self.rows else [])

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def items(count: int = 2) -> tuple[AnalysisArtifactItem, ...]:
    return tuple(AnalysisArtifactItem(f"key-{index}", {"value": index}) for index in range(count))


def test_v3_migration_declares_immutable_row_items_and_bounded_page_index() -> None:
    assert APP_STATE_MIGRATIONS[-1] is MIGRATION_V003
    assert "analysis_artifact_items" in APP_STATE_TABLES
    assert "primary key (artifact_id, ordinal)" in MIGRATION_V003.sql
    assert "jsonb_typeof(document) = 'object'" in MIGRATION_V003.sql
    assert "analysis_artifact_items_page_idx" in MIGRATION_V003.sql
    assert "before update or delete" in MIGRATION_V003.sql


def test_row_backed_publish_writes_compact_manifest_and_bounded_batches() -> None:
    created = (*ARTIFACT[:4], {**MANIFEST, "item_count": 501}, NOW)
    connection = Connection([[], [], [created], [], []])
    record = PostgresAppStateRepository(connection).publish_row_backed_analysis_artifact(
        artifact_id="artifact-a",
        run_id="run-a",
        artifact_type="univariate.rows@v2",
        content_hash="hash-a",
        document={**MANIFEST, "item_count": 501},
        items=items(501),
    )
    assert record.document == {**MANIFEST, "item_count": 501}
    writes = [entry for entry in connection.executed if "analysis_artifact_items" in entry[0]]
    assert len(writes) == 2
    assert all("values" in query and params is not None for query, params in writes)
    assert len(writes[0][1] or ()) == 500 * 4
    assert len(writes[1][1] or ()) == 4
    assert connection.commits == 1
    assert connection.rollbacks == 0


def test_row_backed_publish_is_idempotent_only_for_identical_manifest_and_items() -> None:
    connection = Connection([[ARTIFACT], [("key-0", {"value": 0}), ("key-1", {"value": 1})]])
    record = PostgresAppStateRepository(connection).publish_row_backed_analysis_artifact(
        artifact_id="artifact-a",
        run_id="run-a",
        artifact_type="univariate.rows@v2",
        content_hash="hash-a",
        document=MANIFEST,
        items=items(),
    )
    assert record.artifact_id == "artifact-a"
    assert connection.commits == 1
    insert_statement = "insert into portfell.analysis_artifact_items"
    item_writes = [query for query, _ in connection.executed if insert_statement in query]
    assert item_writes == []


def test_row_backed_publish_fails_closed_and_rolls_back_partial_publication() -> None:
    connection = Connection([], fail_at=3)
    repository = PostgresAppStateRepository(connection)
    with pytest.raises(AppStateError) as captured:
        repository.publish_row_backed_analysis_artifact(
            artifact_id="artifact-a",
            run_id="run-a",
            artifact_type="univariate.rows@v2",
            content_hash="hash-a",
            document=MANIFEST,
            items=items(),
        )
    assert captured.value.code == APP_STATE_PERSISTENCE_FAILED
    assert connection.rollbacks == 1

    repository = PostgresAppStateRepository(Connection([]))
    with pytest.raises(AppStateError) as invalid:
        repository.publish_row_backed_analysis_artifact(
            artifact_id="artifact-a",
            run_id="run-a",
            artifact_type="univariate.rows@v2",
            content_hash="hash-a",
            document={"storage": "row_items", "item_count": 2, "items": []},
            items=items(),
        )
    assert invalid.value.code == APP_STATE_CONFLICT


def test_page_and_count_reads_are_bounded_and_do_not_request_all_rows() -> None:
    connection = Connection([[(100_000,)], [("artifact-a", 100, "key-100", {"value": 100})]])
    repository = PostgresAppStateRepository(connection)
    assert repository.count_analysis_artifact_items("artifact-a") == 100_000
    page = repository.list_analysis_artifact_items("artifact-a", offset=100, limit=1)
    assert page[0].ordinal == 100
    query, params = connection.executed[1]
    assert "offset %s limit %s" in query
    assert params == ("artifact-a", 100, 1)
    with pytest.raises(AppStateError) as invalid:
        repository.list_analysis_artifact_items("artifact-a", offset=-1)
    assert invalid.value.code == APP_STATE_CONFLICT
