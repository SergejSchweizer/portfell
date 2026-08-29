from __future__ import annotations

import pytest

from portfell.project_selection_bootstrap import BootstrapError, InMemoryBootstrapService


def test_bootstrap_freezes_exact_selection_members_and_is_idempotent() -> None:
    service = InMemoryBootstrapService()

    first = service.start(
        user_id="user-a",
        project_id="project-1",
        selection_id="selection-1",
        member_ids=("IE2:XETRA:BBB", "IE1:XETRA:AAA", "IE1:XETRA:AAA"),
    )
    repeated = service.start(
        user_id="user-a",
        project_id="project-1",
        selection_id="selection-1",
        member_ids=("IE1:XETRA:AAA",),
    )

    assert repeated == first
    assert first.member_ids == ("IE1:XETRA:AAA", "IE2:XETRA:BBB")
    assert first.selected_listing_count == 2


def test_bootstrap_rejects_empty_or_cross_user_project_requests() -> None:
    service = InMemoryBootstrapService()

    with pytest.raises(BootstrapError, match="bootstrap_members_required"):
        service.start(
            user_id="user-a", project_id="project-1", selection_id="selection-1", member_ids=()
        )

    service.start(
        user_id="user-a",
        project_id="project-1",
        selection_id="selection-1",
        member_ids=("IE1:XETRA:AAA",),
    )
    with pytest.raises(BootstrapError, match="bootstrap_project_not_owned"):
        service.start(
            user_id="user-b",
            project_id="project-1",
            selection_id="selection-1",
            member_ids=("IE1:XETRA:AAA",),
        )


def test_bootstrap_lifecycle_preserves_frozen_members_and_terminal_state() -> None:
    service = InMemoryBootstrapService()
    bootstrap = service.start(
        user_id="user-a",
        project_id="project-1",
        selection_id="selection-1",
        member_ids=("IE1:XETRA:AAA",),
    )

    running = service.update_status(user_id="user-a", project_id="project-1", status="running")
    ready = service.update_status(user_id="user-a", project_id="project-1", status="ready")

    assert running.member_ids == bootstrap.member_ids
    assert ready.status == "ready"
    with pytest.raises(BootstrapError, match="bootstrap_terminal"):
        service.update_status(user_id="user-a", project_id="project-1", status="running")
