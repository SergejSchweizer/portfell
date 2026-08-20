"""Deterministic presentation fixtures shared by weak-agent PRs."""

from __future__ import annotations

from collections.abc import Mapping

from portfell.dash_ui.core.run_control import RunStatus, StatisticsRunControl

_OBJECTIVES = ("return_risk", "return_drawdown", "minimum_risk")


def run_control_fixtures() -> Mapping[str, StatisticsRunControl]:
    """Return fixed run-control states without external data."""

    return {
        "idle": StatisticsRunControl(
            "univariate_statistics", RunStatus.IDLE, None, None, None, None, None, True
        ),
        "zero_total": StatisticsRunControl(
            "univariate_statistics",
            RunStatus.RUNNING,
            "statistics",
            0,
            0,
            None,
            "Preparing statistics",
            False,
        ),
        "partial": StatisticsRunControl(
            "bivariate_statistics",
            RunStatus.RUNNING,
            "pairs",
            25,
            100,
            25.0,
            "Computing pairs",
            False,
        ),
        "running": StatisticsRunControl(
            "multivariate_statistics",
            RunStatus.RUNNING,
            "optimize",
            4,
            7,
            None,
            "Optimizing portfolio",
            False,
        ),
        "complete": StatisticsRunControl(
            "multivariate_statistics",
            RunStatus.COMPLETE,
            "publish_decisions",
            7,
            7,
            100.0,
            "Complete",
            True,
        ),
        "failed": StatisticsRunControl(
            "univariate_statistics",
            RunStatus.FAILED,
            "statistics",
            3,
            10,
            30.0,
            "Failed",
            True,
            "fixture_failure",
        ),
        "stale": StatisticsRunControl(
            "multivariate_statistics",
            RunStatus.STALE,
            None,
            None,
            None,
            None,
            "Previous result",
            True,
        ),
        "unavailable_progress": StatisticsRunControl(
            "bivariate_statistics",
            RunStatus.STARTING,
            None,
            None,
            None,
            None,
            "Waiting for persisted progress",
            False,
        ),
    }


def two_project_fixture() -> Mapping[str, Mapping[str, object]]:
    """Return stable project-separated presentation evidence."""

    return {
        "project-a": {
            "listing_count": 12,
            "unique_isin_count": 11,
            "available_objectives": _OBJECTIVES,
            "objective": "return_risk",
            "run_status": {
                "univariate": "complete",
                "bivariate": "complete",
                "multivariate": "complete",
            },
            "history": {
                "metadata": "available",
                "univariate": "available",
                "bivariate": "available",
                "multivariate": "available",
                "final_portfolio": "available",
            },
            "candidates": ("project-a-candidate-1", "project-a-candidate-2"),
            "winner": "project-a-candidate-1",
            "decision_sections": ("eligibility", "pareto", "winner_selection"),
        },
        "project-b": {
            "listing_count": 7,
            "unique_isin_count": 7,
            "available_objectives": _OBJECTIVES,
            "objective": "minimum_risk",
            "run_status": {
                "univariate": "complete",
                "bivariate": "failed",
                "multivariate": "idle",
            },
            "history": {
                "metadata": "available",
                "univariate": "available",
                "bivariate": "unavailable",
                "multivariate": "not_run",
                "final_portfolio": "blocked",
            },
            "candidates": (),
            "winner": None,
            "decision_sections": (),
        },
    }
