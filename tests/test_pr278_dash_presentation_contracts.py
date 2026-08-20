from __future__ import annotations

import ast
import inspect

import pytest

from portfell.dash_ui import core
from portfell.dash_ui.core.availability import Availability, AvailabilityState
from portfell.dash_ui.core.plot_contracts import PROFESSIONAL_PLOTS
from portfell.dash_ui.core.run_control import RunStatus, StatisticsRunControl, normalize_progress
from portfell.dash_ui.core.testing import run_control_fixtures, two_project_fixture


def test_pr278_run_status_registry_and_progress_contract_are_exact() -> None:
    assert tuple(status.value for status in RunStatus) == (
        "idle",
        "starting",
        "running",
        "complete",
        "failed",
        "stale",
    )
    assert normalize_progress(None, 10) is None
    assert normalize_progress(0, 0) is None
    assert normalize_progress(25, 100) == 25.0
    assert normalize_progress(120, 100) == 100.0
    with pytest.raises(ValueError):
        StatisticsRunControl(
            "univariate_statistics",
            RunStatus.FAILED,
            None,
            None,
            None,
            None,
            "Failed",
            True,
        )


def test_pr278_fixed_fixtures_cover_progress_failure_stale_and_unavailable() -> None:
    fixtures = run_control_fixtures()
    assert {
        "zero_total",
        "partial",
        "failed",
        "complete",
        "stale",
        "unavailable_progress",
    } <= set(fixtures)
    assert fixtures["zero_total"].percent is None
    assert fixtures["partial"].percent == 25.0
    assert fixtures["failed"].failure_reason == "fixture_failure"
    assert fixtures["complete"].percent == 100.0
    assert fixtures["stale"].status is RunStatus.STALE
    assert fixtures["unavailable_progress"].percent is None


def test_pr278_professional_plot_contracts_are_unique_accessible_and_formula_free() -> None:
    assert tuple(plot.title for plot in PROFESSIONAL_PLOTS) == (
        "Univariate Return / Risk Universe",
        "Bivariate Return / Diversification Universe",
        "Portfolio Candidate OOS Return / Risk",
    )
    ids = [plot.figure_id for plot in PROFESSIONAL_PLOTS]
    assert len(ids) == len(set(ids))
    assert all(plot.responsive and plot.accessible_description for plot in PROFESSIONAL_PLOTS)


def test_pr278_availability_requires_reason_for_non_available_state() -> None:
    assert Availability(AvailabilityState.AVAILABLE).reason is None
    with pytest.raises(ValueError):
        Availability(AvailabilityState.BLOCKED)
    assert Availability(AvailabilityState.BLOCKED, "upstream_failed").reason == "upstream_failed"


def test_pr278_two_project_fixture_is_isolated_and_covers_all_objectives() -> None:
    projects = two_project_fixture()
    assert set(projects) == {"project-a", "project-b"}
    objectives = ("return_risk", "return_drawdown", "minimum_risk")
    assert projects["project-a"]["available_objectives"] == objectives
    assert projects["project-b"]["available_objectives"] == objectives
    assert projects["project-a"]["winner"] == "project-a-candidate-1"
    assert projects["project-b"]["winner"] is None
    assert projects["project-a"]["candidates"] != projects["project-b"]["candidates"]


def test_pr278_dash_core_contracts_import_no_runtime_authority() -> None:
    source = inspect.getsource(core)
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported |= {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    forbidden = ("postgres", "database", "eodhd", "provider", "storage", "lake", "risk_model")
    assert not any(token in name for name in imported for token in forbidden)
