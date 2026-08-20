"""Typed Univariate Statistics page state."""

from __future__ import annotations

from dataclasses import dataclass

from portfell.dash_ui.core.run_control import StatisticsRunControl


@dataclass(frozen=True, slots=True)
class UnivariateView:
    run_control: StatisticsRunControl
    dividend_frequencies: tuple[str, ...]
    selected_dividend_frequencies: tuple[str, ...]
    duration_thresholds: tuple[float, ...]
    metric_tabs: tuple[tuple[str, str], ...]
    active_metric: str
    result_revision: str | None

    def __post_init__(self) -> None:
        allowed = set(self.dividend_frequencies)
        if not set(self.selected_dividend_frequencies) <= allowed:
            raise ValueError("selected dividend frequencies must be server-provided options")
        metric_ids = {metric for metric, _ in self.metric_tabs}
        if self.active_metric not in metric_ids:
            raise ValueError("active metric must exist in metric_tabs")
