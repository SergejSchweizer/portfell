from __future__ import annotations

from contextlib import nullcontext

import pytest

from portfell.hosted_repository_importer import (
    InMemoryProjectRepository,
    InMemoryTenantRepository,
    PostgresProjectRepository,
    PostgresTenantProjectionRepository,
    PostgresTenantRepository,
    TenantImportError,
    TenantProject,
    compare_project_parity,
    import_local_workspace,
)


class _Cursor:
    def __init__(
        self,
        rows: list[tuple[object, ...]] | None = None,
        row: tuple[object, ...] | None = None,
    ) -> None:
        self._rows = rows
        self._row = row

    def fetchone(self) -> tuple[object, ...] | None:
        return self._row

    def fetchall(self) -> list[tuple[object, ...]]:
        return self._rows or []


class _Connection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []
        self.executed = self.calls

    def transaction(self):  # type: ignore[no-untyped-def]
        return nullcontext()

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> _Cursor:
        self.calls.append((sql, parameters))
        if "legacy_imports" in sql and parameters:
            return _Cursor(row=(parameters[0],))
        return _Cursor(rows=[("project-1", "user-a", "Income")])


def test_local_workspace_import_dry_run_does_not_mutate_and_is_deterministic() -> None:
    repository = InMemoryTenantRepository()
    payload = {
        "projects": [
            {"project_id": "project-1", "user_id": "user-a", "name": "Income"},
        ],
        "selections": [
            {
                "selection_id": "selection-1",
                "project_id": "project-1",
                "user_id": "user-a",
                "name": "UCITS",
                "member_ids": ["IE1:XETRA:AAA"],
            }
        ],
        "current_project_id_by_user": {"user-a": "project-1"},
    }

    report = import_local_workspace(repository, payload, dry_run=True)

    assert report.project_count == 1
    assert report.membership_count == 1
    assert repository.projects == ()
    assert repository.import_checksums == ()
    assert import_local_workspace(repository, payload, dry_run=True) == report


def test_local_workspace_import_rejects_duplicate_isin_memberships() -> None:
    repository = InMemoryTenantRepository()
    payload = {
        "projects": [{"project_id": "project-1", "user_id": "user-a", "name": "Income"}],
        "selections": [
            {
                "selection_id": "selection-1",
                "project_id": "project-1",
                "user_id": "user-a",
                "name": "UCITS",
                "member_ids": ["IE1:XETRA:AAA", "IE1:XNAS:BBB"],
            }
        ],
    }

    with pytest.raises(TenantImportError, match="duplicate_selection_isin"):
        import_local_workspace(repository, payload, dry_run=False)

    assert repository.projects == ()


def test_local_workspace_import_is_idempotent_by_completion_checksum() -> None:
    repository = InMemoryTenantRepository()
    payload = {
        "projects": [{"project_id": "project-1", "user_id": "user-a", "name": "Income"}],
        "selections": [],
    }

    first = import_local_workspace(repository, payload, dry_run=False)
    second = import_local_workspace(repository, payload, dry_run=False)

    assert second == first
    assert repository.import_checksums == (first.checksum,)


def test_postgres_projection_binds_transaction_local_user_before_query() -> None:
    connection = _Connection()

    projects = PostgresTenantProjectionRepository(connection).projects_for_user("user-a")

    assert projects == (TenantProject("project-1", "user-a", "Income"),)
    assert connection.calls[0] == (
        "select set_config(%s, %s, true)",
        ("portfell.current_user_id", "user-a"),
    )
    assert "where status = 'active'" in connection.calls[1][0]


def test_project_parity_redacts_project_values() -> None:
    mismatch = compare_project_parity((TenantProject("p1", "user-a", "Income"),), ())

    assert mismatch[0].field == "projects"
    assert mismatch[0].expected_count == 1
    assert mismatch[0].actual_count == 0


def test_project_repository_is_idempotent_and_owner_scoped() -> None:
    repository = InMemoryProjectRepository()
    project = TenantProject("project-1", "user-a", "Income")

    assert repository.create_project(project) == project
    assert repository.create_project(project) == project
    assert repository.list_projects("user-b") == ()
    repository.set_current_project(user_id="user-a", project_id="project-1")
    repository.delete_project(user_id="user-a", project_id="project-1")

    assert repository.list_projects("user-a") == ()
    with pytest.raises(TenantImportError, match="project_not_found"):
        repository.delete_project(user_id="user-b", project_id="project-1")


def test_postgres_project_repository_parameterizes_owned_commands() -> None:
    connection = _Connection()
    repository = PostgresProjectRepository(connection)
    project = TenantProject("project-1", "user-a", "Income")

    repository.create_project(project)
    repository.set_current_project(user_id="user-a", project_id="project-1")

    assert connection.calls[0][1] == ("portfell.current_user_id", "user-a")
    assert connection.calls[1][1] == ("project-1", "user-a", "Income")
    assert connection.calls[3][1] == ("user-a", "project-1")


def test_postgres_importer_maps_legacy_ids_and_seals_membership() -> None:
    connection = _Connection()
    repository = PostgresTenantRepository(connection)
    payload = {
        "projects": [{"project_id": "project-1", "user_id": "user-a", "name": "Income"}],
        "selections": [
            {
                "selection_id": "selection-1",
                "project_id": "project-1",
                "user_id": "user-a",
                "name": "UCITS",
                "member_ids": ["IE1:XETRA:AAA"],
            }
        ],
        "current_project_id_by_user": {"user-a": "project-1"},
    }

    report = import_local_workspace(repository, payload, dry_run=False)

    statements = "\n".join(statement for statement, _ in connection.executed)
    assert connection.executed[0][1] == (report.checksum,)
    assert "insert into portfell_app.users" in statements
    assert "project_selection_members" in statements
    assert "set membership_sealed_at = now()" in statements
    project_parameters = next(
        parameters
        for statement, parameters in connection.executed
        if "insert into portfell_app.projects" in statement
    )
    assert str(project_parameters[0]).count("-") == 4
