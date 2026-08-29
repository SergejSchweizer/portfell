from portfell.hosted_status_event_repository import PostgresStatusEventRepository


class Cursor:
    def __init__(
        self,
        rows: list[tuple[object, ...]] | None = None,
        row: tuple[object, ...] | None = None,
    ) -> None:
        self.rows = rows or []
        self.row = row

    def fetchall(self) -> list[tuple[object, ...]]:
        return self.rows

    def fetchone(self) -> tuple[object, ...] | None:
        return self.row


class Connection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.authenticated_user_id: str | None = None

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> Cursor:
        self.calls.append((sql, parameters))
        if "select event_id" in sql:
            return Cursor([(3, "workflow.changed", "project:p1", "etag", None)])
        if "select min(event_id)" in sql:
            return Cursor(row=(3, 7))
        if "select exists(" in sql:
            return Cursor(row=(True,))
        if "delete from portfell_app.status_events" in sql:
            return Cursor(rows=[(1,), (2,)])
        return Cursor()


def test_status_events_bind_rls_append_and_replay_a_bounded_page() -> None:
    connection = Connection()
    repository = PostgresStatusEventRepository(connection)

    repository.append(
        user_id="00000000-0000-5000-8000-000000000001",
        project_id="00000000-0000-5000-8000-000000000011",
        event_type="workflow.changed",
        aggregate_ref="project:p1",
        projection_revision="etag",
    )
    events = repository.replay(user_id="00000000-0000-5000-8000-000000000001", after_event_id=0)

    assert "set_config" in connection.calls[0][0]
    assert "insert into portfell_app.status_events" in connection.calls[1][0]
    assert events[0].event_id == 3
    assert events[0].projection_revision == "etag"


def test_status_event_replay_rejects_unbounded_or_negative_cursors() -> None:
    repository = PostgresStatusEventRepository(Connection())

    for after_event_id, limit in ((-1, 1), (0, 0), (0, 1_001)):
        try:
            repository.replay(
                user_id="00000000-0000-5000-8000-000000000001",
                after_event_id=after_event_id,
                limit=limit,
            )
        except ValueError as error:
            assert str(error) == "status_event_replay_invalid"
        else:
            raise AssertionError("expected bounded replay validation")


def test_status_event_replay_bounds_are_always_scoped_to_the_authenticated_user() -> None:
    repository = PostgresStatusEventRepository(Connection())
    user_id = "00000000-0000-5000-8000-000000000001"

    assert repository.bounds(user_id=user_id) == (3, 7)
    assert repository.has_more(user_id=user_id, after_event_id=6)


def test_status_event_retention_deletes_only_expired_compact_rows() -> None:
    repository = PostgresStatusEventRepository(Connection())

    assert repository.prune_expired() == 2
