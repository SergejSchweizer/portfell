from __future__ import annotations

import pytest

from portfell.dash_ui.core.availability import AvailabilityState
from portfell.dash_ui.core.navigation import navigation_items, project_switch


def test_pr265_navigation_contains_exactly_four_frozen_workflow_links() -> None:
    items = navigation_items(project_slug="alpha", base_prefix="/dash")
    assert [item.label for item in items] == [
        "Metadata Builder",
        "Univariate Statistics",
        "Bivariate Statistics",
        "Multivariate Statistics",
    ]
    assert [item.href for item in items] == [
        "/dash/projects/alpha/metadata-builder",
        "/dash/projects/alpha/univariate-statistics",
        "/dash/projects/alpha/bivariate-statistics",
        "/dash/projects/alpha/multivariate-statistics",
    ]


def test_pr265_project_switch_clears_old_state_before_reading_new_project() -> None:
    decision = project_switch(
        current_slug="alpha",
        requested_slug="beta",
        available_slugs=("alpha", "beta"),
    )
    assert decision.project_slug == "beta"
    assert decision.clear_presented_state is True
    assert decision.should_read is True
    assert decision.availability.state is AvailabilityState.AVAILABLE


def test_pr265_same_project_is_idempotent_and_emits_no_read_command() -> None:
    decision = project_switch(
        current_slug="alpha",
        requested_slug="alpha",
        available_slugs=("alpha", "beta"),
    )
    assert decision.clear_presented_state is False
    assert decision.should_read is False


def test_pr265_unknown_project_fails_closed_without_fallback() -> None:
    decision = project_switch(
        current_slug="alpha",
        requested_slug="deleted-project",
        available_slugs=("alpha", "beta"),
    )
    assert decision.project_slug is None
    assert decision.clear_presented_state is True
    assert decision.should_read is False
    assert decision.availability.state is AvailabilityState.UNAVAILABLE
    assert decision.availability.reason == "project_unavailable"


def test_pr265_shell_smoke_when_dash_dependency_is_available() -> None:
    pytest.importorskip("dash")
    from portfell.dash_ui.core.shell import build_shell

    shell = build_shell(
        project_slug="alpha",
        projects=({"slug": "alpha", "label": "Alpha"},),
        stage_statuses={},
        page_content="content",
    )
    assert getattr(shell, "id", None) == "shell-root"
