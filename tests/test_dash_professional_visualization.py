from __future__ import annotations

from pathlib import Path

import plotly.graph_objects as go

from portfell.dash_app.figures import PORTFELL_CATEGORICAL_PALETTE, apply_portfell_template
from portfell.dash_app.visual_contract import PAGE_ROUTES, REFERENCE_URL, VISUAL_VIEWPORTS, display_percent


def test_visual_contract_freezes_routes_and_viewports() -> None:
    assert PAGE_ROUTES == ("/metadata", "/univariate", "/bivariate", "/multivariate")
    assert [(item.width, item.height) for item in VISUAL_VIEWPORTS] == [
        (1440, 900),
        (1024, 768),
        (390, 844),
    ]


def test_shared_plotly_template_has_neutral_financial_dashboard_grammar() -> None:
    figure = apply_portfell_template(go.Figure(go.Scatter(x=[1], y=[2])), x_title="X", y_title="Y")
    assert figure.layout.paper_bgcolor == "#ffffff"
    assert figure.layout.plot_bgcolor == "rgba(0,0,0,0)"
    assert tuple(figure.layout.colorway) == PORTFELL_CATEGORICAL_PALETTE
    assert figure.layout.xaxis.title.text == "X"
    assert figure.layout.yaxis.title.text == "Y"


def test_missing_presentation_value_is_not_fabricated_zero() -> None:
    assert display_percent(None) == "—"
    assert display_percent(0.125) == "12.50%"


def test_shared_css_has_sticky_tables_accessible_focus_and_no_reference_copy() -> None:
    assets = Path("src/portfell/dash_app/assets")
    css = "\n".join(path.read_text(encoding="utf-8") for path in sorted(assets.glob("*.css")))
    assert "position: sticky" in css
    assert "focus-visible" in css
    assert "prefers-reduced-motion" in css
    assert "overflow-x: auto" in css
    assert REFERENCE_URL not in css
    for forbidden in ("Price Performance", "Fees & Distributions", "Resources"):
        assert forbidden not in css
