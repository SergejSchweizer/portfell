from __future__ import annotations

from contextlib import nullcontext

from portfell.hosted_metadata_repository import MetadataRun, PostgresMetadataLifecycleRepository


class _Cursor:
    def fetchone(self) -> tuple[object, ...] | None:
        return None


class _Connection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def transaction(self):
        return nullcontext()

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        self.calls.append((sql, parameters))
        return _Cursor()


class _StatusEvents:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    def append(self, **kwargs: object) -> None:
        self.events.append(kwargs)


def _run() -> MetadataRun:
    return MetadataRun(
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
        "running",
        3,
        1,
        0,
        33,
        {},
    )


def test_metadata_writes_refresh_navigation_in_the_same_connection_scope() -> None:
    connection = _Connection()
    refreshed: list[str] = []
    repository = PostgresMetadataLifecycleRepository(
        connection, navigation_refresher=lambda user_id: refreshed.append(user_id)
    )
    run = _run()

    repository.create(run)
    repository.update(run)
    repository.set_revision(user_id=run.user_id, revision_id="metadata-v1")

    assert refreshed == [run.user_id, run.user_id, run.user_id]
    statements = "\n".join(statement for statement, _ in connection.calls)
    assert "insert into portfell_app.metadata_runs" in statements
    assert "update portfell_app.metadata_runs" in statements
    assert "metadata_revision_pointers" in statements


def test_metadata_lifecycle_publishes_compact_status_and_revision_events() -> None:
    events = _StatusEvents()
    repository = PostgresMetadataLifecycleRepository(
        _Connection(), status_events=events  # type: ignore[arg-type]
    )
    running = _run()
    completed = MetadataRun(
        running.metadata_run_id,
        running.user_id,
        "succeeded",
        running.total,
        running.total,
        0,
        100,
        {},
    )

    repository.create(running)
    repository.update(completed)
    repository.set_revision(user_id=running.user_id, revision_id="metadata-v1")

    assert [event["event_type"] for event in events.events] == [
        "metadata.status",
        "metadata.status",
        "metadata.revision",
    ]
    assert events.events[1]["terminal_status"] == "succeeded"
    assert events.events[2]["projection_revision"] == "metadata-v1"
