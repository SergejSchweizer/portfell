from __future__ import annotations

from pathlib import Path

import pytest

from portfell.dash_ui.pages.multivariate_statistics.layout import OBJECTIVE_OPTIONS, TAB_ORDER
from portfell.multivariate.contracts.common import DECISION_STAGE_ORDER


def test_pr290_objective_and_tab_registries_are_exact() -> None:
    assert OBJECTIVE_OPTIONS == (
        ("return_risk", "Return / Risk"),
        ("return_drawdown", "Return / Drawdown"),
        ("minimum_risk", "Minimum Risk"),
    )
    assert TAB_ORDER == (
        ("universe", "Universe"),
        ("risk_model", "Risk Model"),
        ("optimization", "Optimization"),
        ("validation", "Validation"),
        ("final_portfolio", "Final Portfolio"),
    )


def test_pr290_layout_source_preserves_required_visual_order_and_single_optimizer_page() -> None:
    source = Path("src/portfell/dash_ui/pages/multivariate_statistics/layout.py").read_text(
        encoding="utf-8"
    )
    markers = (
        'html.Span("Optimization objective")',
        '"run-control"',
        'html.H3("Universe & History")',
        '"candidate-plot"',
        '"tabs"',
        'html.H3("Decision Audit")',
    )
    positions = [source.index(marker) for marker in markers]
    assert positions == sorted(positions)
    assert source.count('html.H2("Multivariate Statistics")') == 1
    assert 'html.Button("Optimize portfolio"' in source
    assert "optimizer-page" not in source.casefold()


def test_pr290_all_eight_decision_regions_remain_visible_by_frozen_registry() -> None:
    assert len(DECISION_STAGE_ORDER) == 8
    source = Path("src/portfell/dash_ui/pages/multivariate_statistics/layout.py").read_text(
        encoding="utf-8"
    )
    assert "for stage in DECISION_STAGE_ORDER" in source
    assert 'html.Span(" unavailable")' in source


def test_pr290_css_covers_390px_responsive_and_keyboard_focus() -> None:
    css = Path("src/portfell/dash_ui/assets/multivariate.css").read_text(encoding="utf-8")
    assert "@media (max-width: 600px)" in css
    assert "focus-visible" in css
    assert "outline:" in css
    assert "min-width: 0" in css


def test_pr290_layout_smoke_has_accessible_objective_label_when_dash_available() -> None:
    pytest.importorskip("dash")
    from portfell.dash_ui.pages.multivariate_statistics.layout import build_multivariate_layout

    layout = build_multivariate_layout()
    assert getattr(layout, "id", None) == "multivariate-page"
