"""End-to-end Univariate selection contract against Docker + PostgreSQL."""

from __future__ import annotations

import os
from typing import Any

import pytest
from playwright.sync_api import Page, expect, sync_playwright

BASE_URL = os.environ.get("PORTFELL_REAL_STACK_URL", "http://127.0.0.1:8080")


@pytest.mark.browser
@pytest.mark.real_stack
def test_univariate_checkbox_selection_is_persisted_and_drives_plot() -> None:
    """Exercise all three checkbox groups and compare DB state with Plotly data."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        try:
            _run_real_stack_flow(page)
        finally:
            browser.close()


def _run_real_stack_flow(page: Page) -> None:
    health = page.request.get(f"{BASE_URL}/api/health")
    if not health.ok:
        pytest.skip("Docker/PostgreSQL stack is not available")

    workflow = page.request.get(f"{BASE_URL}/api/workflow").json()
    universe = workflow.get("metadata_universe") or {}
    if not universe.get("universe_id"):
        created = page.request.post(
            f"{BASE_URL}/api/metadata/universes",
            data={"exchange": "XETRA", "instrument_type": "ETF", "currency": "EUR"},
        )
        if not created.ok:
            pytest.skip("The configured market snapshot has no runnable ETF universe")
        universe = created.json()

    run_id = _succeeded_univariate_run(page, str(universe["universe_id"]))
    if run_id is None:
        pytest.skip("A succeeded Univariate run for the current Metadata universe is required")
    assert isinstance(run_id, str)

    page.goto(f"{BASE_URL}/univariate", wait_until="networkidle")
    expect(page.locator("#univariate-page")).to_be_visible()
    _assert_plot_matches_persisted_selection(page)

    # One category from each independent filter group is selected, then each
    # is removed again.  After every mutation the persisted selection and plot
    # must agree; this catches callback ordering and stale-render regressions.
    for token in (
        "univariate-dividend-frequency-table",
        "univariate-isin-age-table",
        "univariate-monthly-return-table",
    ):
        checkbox = page.locator(f"#{token} input[type=checkbox]:not([disabled])").first
        if checkbox.count() == 0:
            pytest.skip(f"No enabled {token} category in the configured dataset")
        _mutate_checkbox(page, checkbox, checked=True)
        _assert_plot_matches_persisted_selection(page)
        _assert_selection_counts(page)
        _mutate_checkbox(page, checkbox, checked=False)
        _assert_plot_matches_persisted_selection(page)
        _assert_selection_counts(page)


def _mutate_checkbox(page: Page, checkbox: Any, *, checked: bool) -> None:
    with page.expect_response(
        lambda response: (
            "_dash-update-component" in response.url and response.request.method == "POST"
        ),
        timeout=10_000,
    ):
        checkbox.check() if checked else checkbox.uncheck()
    page.wait_for_timeout(300)


def _succeeded_univariate_run(page: Page, universe_id: str) -> str | None:
    workflow = page.request.get(f"{BASE_URL}/api/workflow").json()
    stage = workflow.get("stages", {}).get("univariate", {})
    if (
        isinstance(stage, dict)
        and stage.get("status") == "succeeded"
        and stage.get("input_ref") == universe_id
    ):
        return str(stage["run_id"])
    history = page.request.get(f"{BASE_URL}/api/univariate/runs?limit=500").json()
    for run in history.get("items", []):
        if (
            isinstance(run, dict)
            and run.get("status") == "succeeded"
            and run.get("input_ref") == universe_id
        ):
            return str(run["run_id"])
    return None


def _assert_plot_matches_persisted_selection(page: Page) -> None:
    workflow = page.request.get(f"{BASE_URL}/api/workflow").json()
    selection = workflow.get("univariate_selection") or {}
    selected = {
        str(member["isin"])
        for member in selection.get("members", [])
        if isinstance(member, dict) and member.get("isin")
    }
    plot = page.locator("#univariate-return-risk-chart .js-plotly-plot")
    if plot.count() == 0:
        assert not selected
        return
    plotted = plot.evaluate(
        """node => node.data.flatMap(trace => (trace.customdata || [])
        .map(row => Array.isArray(row) ? String(row[0]) : String(row)))"""
    )
    # The chart intentionally omits selected instruments without valid risk /
    # return metrics, but it must never leak an unselected ISIN.
    if selected:
        assert set(plotted) <= selected
    else:
        assert set(plotted)


def _assert_selection_counts(page: Page) -> None:
    workflow = page.request.get(f"{BASE_URL}/api/workflow").json()
    selection = workflow.get("univariate_selection") or {}
    members = selection.get("members", [])
    unique_isins = {
        str(member["isin"]) for member in members if isinstance(member, dict) and member.get("isin")
    }
    # The persisted backend selection is the source of truth for both cards:
    # Univariate Selected ISINs and the Bivariate candidate-pair plan.
    page.goto(f"{BASE_URL}/bivariate", wait_until="networkidle")
    body = page.locator("#bivariate-kpi-grid").inner_text()
    expected_pairs = len(unique_isins) * (len(unique_isins) - 1) // 2
    # Empty persisted selections are represented consistently as numeric zero
    # across the sidebar and Bivariate KPI cards.
    assert str(len(unique_isins)) in body
    assert str(expected_pairs) in body
    page.goto(f"{BASE_URL}/univariate", wait_until="networkidle")
