"""Presentation model for the income-first Univariate metric cards."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from portfell.univariate_metric_catalog import CATALOG_BY_ID, METRIC_IDS


def metric_card_models(distributions: Mapping[str, Any]) -> list[dict[str, Any]]:
    metrics_raw = distributions.get("metrics")
    if not isinstance(metrics_raw, dict):
        return []
    metrics = cast(dict[str, Any], metrics_raw)
    groups = {
        "Data quality": METRIC_IDS[:4],
        "Income & distributions": METRIC_IDS[4:20],
        "Return & capital risk": METRIC_IDS[20:31],
        "Risk-adjusted return": METRIC_IDS[31:34],
        "Robustness & distribution shape": METRIC_IDS[34:],
    }
    cards: list[dict[str, Any]] = []
    for group, ids in groups.items():
        for metric_id in ids:
            cards.append(
                {
                    "group": group,
                    "metric_id": metric_id,
                    "title": CATALOG_BY_ID[metric_id].description.title(),
                    "definition": CATALOG_BY_ID[metric_id].description,
                    "distribution": cast(dict[str, Any], metrics.get(metric_id, {})),
                }
            )
    return cards


__all__ = ["metric_card_models"]
