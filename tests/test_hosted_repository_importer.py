from __future__ import annotations

import pytest

from portfell.hosted_repository_importer import (
    InMemoryTenantRepository,
    TenantImportError,
    import_local_workspace,
)


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
