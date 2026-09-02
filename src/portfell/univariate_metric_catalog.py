"""Authoritative income-first Univariate metric registry."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    metric_id: str
    unit: str
    kind: str
    filter_type: str
    description: str


_DATA_QUALITY = (
    "history_years",
    "distribution_history_years",
    "observation_count",
    "missing_ratio",
)
_INCOME = (
    "distribution_frequency",
    "distributions_per_year",
    "ttm_distribution",
    "ttm_distribution_yield",
    "distribution_cagr_3y",
    "distribution_cagr_5y",
    "distribution_cv",
    "distribution_regularity",
    "distribution_cut_ratio",
    "max_distribution_cut",
    "rolling_12m_distribution_yield_median",
    "rolling_12m_distribution_yield_min",
    "rolling_12m_distribution_yield_max",
    "rolling_12m_distribution_yield_std",
    "distribution_growth_positive_year_ratio",
    "distribution_drawdown",
)
_RISK = (
    "total_return_cagr",
    "annualized_volatility",
    "downside_deviation",
    "max_drawdown",
    "current_drawdown",
    "max_drawdown_duration",
    "current_drawdown_duration",
    "max_drawdown_recovery_days",
    "var_95",
    "cvar_95",
    "ulcer_index",
)
_ADJUSTED = ("sharpe", "sortino", "calmar")
_ROBUST = (
    "rolling_3y_cagr_median",
    "rolling_3y_cagr_min",
    "rolling_3y_sharpe_median",
    "rolling_3y_sharpe_min",
    "skewness",
    "excess_kurtosis",
    "positive_month_ratio",
    "worst_month",
    "best_month",
    "worst_3m_return",
    "worst_12m_return",
    "rolling_1y_return_median",
    "rolling_1y_return_min",
    "rolling_1y_return_std",
    "rolling_1y_vol_median",
    "rolling_1y_vol_max",
    "gain_loss_ratio",
    "autocorrelation",
)
METRIC_IDS = _DATA_QUALITY + _INCOME + _RISK + _ADJUSTED + _ROBUST


def metric_catalog() -> tuple[MetricDefinition, ...]:
    categorical = {"distribution_frequency"}
    integer = {
        "observation_count",
        "max_drawdown_duration",
        "current_drawdown_duration",
        "max_drawdown_recovery_days",
    }
    definitions: list[MetricDefinition] = []
    for metric_id in METRIC_IDS:
        kind = "categorical" if metric_id in categorical else "continuous"
        filter_type = "include" if kind == "categorical" else "range"
        unit = (
            "category" if kind == "categorical" else ("count" if metric_id in integer else "ratio")
        )
        definitions.append(
            MetricDefinition(metric_id, unit, kind, filter_type, metric_id.replace("_", " "))
        )
    return tuple(definitions)


CATALOG_BY_ID = {item.metric_id: item for item in metric_catalog()}

__all__ = ["CATALOG_BY_ID", "METRIC_IDS", "MetricDefinition", "metric_catalog"]
