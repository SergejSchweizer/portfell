from __future__ import annotations

from migration_evidence import dash_cutover_evidence
from test_dash_multivariate_page import Service

from portfell.dash_app.pages.multivariate import build_page, optimize_portfolio


def test_all_objectives_are_forwarded_without_substitution() -> None:
    service = Service()
    results = {}
    for objective in ("return_risk", "return_drawdown", "minimum_risk"):
        result = optimize_portfolio(
            service, selection_id="selection-1", bivariate_run_id="run-b", objective=objective
        )
        results[objective] = result["objective"] == objective
    assert all(results.values())
    evidence = dash_cutover_evidence(
        sha="test-sha",
        objective_results=results,
        focused_tests=["test_pr478_selection_v2_browser_qa.py"],
    )
    assert evidence["all_objectives_reached"] and evidence["status"] == "PASS"


def test_page_contains_selection_evidence_boundary() -> None:
    page = build_page(Service())
    rendered = str(page)
    assert "Selection Evidence" in rendered
    assert "current-sample diagnostics are descriptive" in rendered
    assert "multivariate-objective" in rendered


def test_stale_bivariate_readiness_blocks_run_button() -> None:
    class StaleService(Service):
        def workflow_state(self):
            state = super().workflow_state()
            state["stages"]["bivariate"]["input_ref"] = "different-selection"
            return state

    page = build_page(StaleService())
    assert "different selection" in str(page).lower()
