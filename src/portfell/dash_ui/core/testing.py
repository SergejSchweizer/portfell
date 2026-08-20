"""Deterministic presentation fixtures shared by weak-agent PRs."""

from __future__ import annotations

from collections.abc import Mapping

from portfell.dash_ui.core.run_control import RunStatus, StatisticsRunControl


def run_control_fixtures() -> Mapping[str, StatisticsRunControl]:
    """Return fixed run-control states without external data."""

    return {
        "idle": StatisticsRunControl("univariate_statistics", RunStatus.IDLE, None, None, None, None, None, True),
        "running": StatisticsRunControl("bivariate_statistics", RunStatus.RUNNING, "pairs", 25, 100, 25.0, "Computing pairs", False),
        "complete": StatisticsRunControl("multivariate_statistics", RunStatus.COMPLETE, "publish_decisions", 7, 7, 100.0, "Complete", True),
        "failed": StatisticsRunControl("univariate_statistics", RunStatus.FAILED, "statistics", 3, 10, 30.0, "Failed", True, "fixture_failure"),
        "stale": StatisticsRunControl("multivariate_statistics", RunStatus.STALE, None, None, None, None, "Previous result", True),
    }


def two_project_fixture() -> Mapping[str, Mapping[str, object]]:
    """Return stable project-separated presentation evidence."""

    return {
        "project-a": {"listing_count": 12, "unique_isin_count": 11, "objective": "return_risk"},
        "project-b": {"listing_count": 7, "unique_isin_count": 7, "objective": "minimum_risk"},
    }
