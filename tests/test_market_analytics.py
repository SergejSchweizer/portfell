"""Regression coverage for analytics retained after medallion deletion."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from portfell.market_analytics import (
    build_asset_features,
    build_correlation_and_covariance,
    build_correlation_edges,
    build_returns,
    covariance,
)


def _quote(isin: str, date: str, close: float) -> dict[str, object]:
    return {
        "isin": isin,
        "exchange": "XETRA",
        "code": isin,
        "date": date,
        "adjusted_close": close,
    }


def test_medallion_modules_are_removed_and_analytics_is_storage_free() -> None:
    package = Path(__file__).resolve().parents[1] / "src" / "portfell"

    assert not (package / "bronze.py").exists()
    assert not (package / "silver.py").exists()
    assert not (package / "gold.py").exists()
    assert not (package / "pipeline.py").exists()
    assert importlib.util.find_spec("portfell.market_analytics") is not None


def test_retained_analytics_preserves_return_pair_and_feature_semantics() -> None:
    quotes = [
        _quote("IE1", "2026-01-01", 100.0),
        _quote("IE1", "2026-01-02", 110.0),
        _quote("IE2", "2026-01-01", 50.0),
        _quote("IE2", "2026-01-02", 55.0),
    ]

    returns = build_returns(quotes)
    correlations, covariances = build_correlation_and_covariance(returns)
    features = build_asset_features(quotes, returns)

    assert len(returns) == 2
    assert correlations and covariances
    assert {row["isin"] for row in features} == {"IE1", "IE2"}
    assert covariance((1.0, 2.0), (1.0, 2.0)) == pytest.approx(0.5)


def test_retained_correlation_edges_keep_pair_count_guard() -> None:
    returns = [
        {"isin": f"IE{index}", "exchange": "XETRA", "code": "ETF", "date": "2026-01-01", "return": 0.1}
        for index in range(40)
    ]

    with pytest.raises(ValueError, match="correlation edges build rejected"):
        build_correlation_edges(returns, version="v1", max_pair_count=100)
