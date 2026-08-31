"""Frozen route and presentation contracts for the Plotly Dash replacement."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PageSpec:
    route: str
    page_id: str
    label: str
    title: str
    subtitle: str


PAGE_SPECS = (
    PageSpec(
        route="/metadata",
        page_id="metadata",
        label="Metadata",
        title="Metadata",
        subtitle="Build the active Xetra instrument universe.",
    ),
    PageSpec(
        route="/univariate",
        page_id="univariate",
        label="Univariate",
        title="Univariate",
        subtitle=(
            "Inspect single-instrument return and risk statistics, then persist the "
            "downstream selection."
        ),
    ),
    PageSpec(
        route="/bivariate",
        page_id="bivariate",
        label="Bivariate",
        title="Bivariate",
        subtitle=(
            "Inspect pairwise diversification evidence for the persisted Univariate selection."
        ),
    ),
    PageSpec(
        route="/multivariate",
        page_id="multivariate",
        label="Multivariate",
        title="Multivariate",
        subtitle=(
            "Optimize candidate portfolios and select the final portfolio from "
            "out-of-sample evidence."
        ),
    ),
)

PAGE_BY_ROUTE = {item.route: item for item in PAGE_SPECS}
DEFAULT_ROUTE = "/metadata"
MULTIVARIATE_OBJECTIVES = ("return_risk", "return_drawdown", "minimum_risk")
SHARED_PRIMITIVES = (
    "PageHeader",
    "ControlBar",
    "KpiCard",
    "ChartCard",
    "TableCard",
    "StatusBanner",
    "HistoryCard",
    "StageFooter",
)

__all__ = [
    "DEFAULT_ROUTE",
    "MULTIVARIATE_OBJECTIVES",
    "PAGE_BY_ROUTE",
    "PAGE_SPECS",
    "SHARED_PRIMITIVES",
    "PageSpec",
]
