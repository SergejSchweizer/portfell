"""Typed Bivariate Statistics page state."""

from __future__ import annotations

from dataclasses import dataclass

from portfell.dash_ui.core.run_control import StatisticsRunControl

DETAIL_VIEWS: tuple[tuple[str, str], ...] = (
    ("covariance", "Covariance"),
    ("pearson", "Pearson"),
    ("spearman", "Spearman"),
    ("downside", "Downside"),
    ("tail_dependence", "Tail Dependence"),
    ("co_exceedance", "Co-exceedance"),
    ("rolling_correlation", "Rolling-Correlation"),
    ("drawdown_overlap", "Drawdown Overlap"),
    ("tail_risk_scatter", "Tail-Risk Scatter"),
)

DEPENDENCE_METRICS: tuple[tuple[str, str], ...] = (
    ("median_pearson", "Median Pearson"),
    ("median_spearman", "Median Spearman"),
    ("median_downside", "Median Downside Correlation"),
    ("median_lower_tail", "Median Lower-Tail Dependence"),
    ("median_co_exceedance", "Median Co-exceedance"),
    ("median_drawdown_overlap", "Median Drawdown Overlap"),
)


@dataclass(frozen=True, slots=True)
class BivariateView:
    run_control: StatisticsRunControl
    upstream_revision: str | None
    detail_views: tuple[tuple[str, str], ...] = DETAIL_VIEWS
    active_view: str = "pearson"
    dependence_metrics: tuple[tuple[str, str], ...] = DEPENDENCE_METRICS
    selected_dependence_metric: str = "median_pearson"

    def __post_init__(self) -> None:
        if self.detail_views != DETAIL_VIEWS:
            raise ValueError("Bivariate detail view registry is frozen")
        if self.active_view not in {value for value, _ in self.detail_views}:
            raise ValueError("active Bivariate view is not registered")
        if self.selected_dependence_metric not in {value for value, _ in self.dependence_metrics}:
            raise ValueError("selected dependence metric is not registered")
