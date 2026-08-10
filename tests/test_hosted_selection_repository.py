from __future__ import annotations

from portfell.hosted_repository_importer import TenantSelection
from portfell.hosted_selection_repository import PostgresSelectionRepository


class _Cursor:
    def __init__(self, rows: list[tuple[object, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows


class _Connection:
    def __init__(self, rows: list[tuple[object, ...]] | None = None) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self._rows = rows or []

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        self.calls.append((sql, parameters))
        return _Cursor(self._rows if "select version.selection_version_id" in sql else [])


def test_selection_repository_reads_owned_sealed_membership_in_canonical_order() -> None:
    connection = _Connection(
        [
            ("selection-1", "project-1", "user-a", "UCITS", "IE1", "XETRA", "AAA"),
            ("selection-1", "project-1", "user-a", "UCITS", "IE2", "XNAS", "BBB"),
        ]
    )

    selection = PostgresSelectionRepository(connection).get(
        project_id="project-1", user_id="user-a"
    )

    assert selection == TenantSelection(
        "selection-1",
        "project-1",
        "user-a",
        "UCITS",
        ("IE1:XETRA:AAA", "IE2:XNAS:BBB"),
    )
    assert connection.calls[0] == (
        "select set_config(%s, %s, true)",
        ("portfell.current_user_id", "user-a"),
    )
    assert "membership_sealed_at is not null" in connection.calls[1][0]


def test_selection_repository_seals_exact_members_after_creation() -> None:
    connection = _Connection()
    selection = TenantSelection("selection-1", "project-1", "user-a", "UCITS", ("IE1:XETRA:AAA",))

    assert PostgresSelectionRepository(connection).create(selection) == selection

    statements = "\n".join(statement for statement, _ in connection.calls)
    assert "project_selection_members" in statements
    assert "set membership_sealed_at = now()" in statements
