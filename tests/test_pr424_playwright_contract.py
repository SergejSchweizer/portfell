"""PR424 browser QA gate contract."""

from __future__ import annotations

from pathlib import Path

from portfell.dash_app.visual_contract import PAGE_ROUTES, VISUAL_VIEWPORTS


def test_playwright_journey_covers_every_module_and_required_viewports() -> None:
    assert PAGE_ROUTES == ("/metadata", "/univariate", "/bivariate", "/multivariate")
    assert {(view.width, view.height) for view in VISUAL_VIEWPORTS} >= {
        (1440, 900),
        (1024, 768),
        (390, 844),
    }
    source = Path("tests/browser/test_dash_four_page_parity.py").read_text()
    for marker in ("customdata", "page.reload", "bivariate-compute", "multivariate-optimize"):
        assert marker in source


def test_real_stack_journey_is_marked_and_does_not_use_fixture_service() -> None:
    source = Path("tests/browser/test_real_stack_univariate_selection.py").read_text()
    assert "@pytest.mark.real_stack" in source
    assert "PORTFELL_REAL_STACK_URL" in source
    assert "DashParityFixtureService" not in source
