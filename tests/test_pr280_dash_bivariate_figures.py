from __future__ import annotations

from portfell.dash_ui.figures.bivariate_statistics.detail import (
    DETAIL_TITLES,
    detail_matrix_figure,
    pair_history_figure,
)
from portfell.dash_ui.figures.bivariate_statistics.models import (
    BivariateUniversePoint,
    PairHistoryPoint,
)
from portfell.dash_ui.figures.bivariate_statistics.universe import (
    METRIC_LABELS,
    WEBGL_LISTING_THRESHOLD,
    diversification_figure,
)


def _point(index: int, *, value: float | None = 0.2) -> BivariateUniversePoint:
    return BivariateUniversePoint(
        isin=f"ISIN-{index:04d}",
        exchange="XETRA",
        code=f"C{index:04d}",
        annualized_geometric_return=0.05 + index / 100000,
        median_pearson=value,
        median_spearman=0.18,
        median_downside=0.22,
        median_lower_tail=0.12,
        median_co_exceedance=0.08,
        median_drawdown_overlap=0.15,
        usable_pair_count=200,
    )


def test_pr280_metric_registry_and_dynamic_axis_are_exact() -> None:
    assert tuple(METRIC_LABELS) == (
        "median_pearson",
        "median_spearman",
        "median_downside",
        "median_lower_tail",
        "median_co_exceedance",
        "median_drawdown_overlap",
    )
    figure = diversification_figure((_point(1),), metric_id="median_downside")
    assert figure["layout"]["title"] == "Bivariate Return / Diversification Universe"
    assert figure["layout"]["xaxis"]["title"] == METRIC_LABELS["median_downside"]


def test_pr280_webgl_threshold_is_deterministic() -> None:
    assert WEBGL_LISTING_THRESHOLD == 200
    small = diversification_figure(tuple(_point(index) for index in range(200)))
    large = diversification_figure(tuple(_point(index) for index in range(201)))
    assert small["data"][0]["type"] == "scatter"
    assert large["data"][0]["type"] == "scattergl"


def test_pr280_unavailable_metrics_remain_typed_not_zero() -> None:
    figure = diversification_figure((_point(1, value=None), _point(2, value=0.0)))
    assert figure["data"][0]["x"] == [0.0]
    assert figure["layout"]["meta"]["unavailable_listing_ids"] == ["ISIN-0001|XETRA|C0001"]


def test_pr280_nine_authorized_detail_views_are_frozen() -> None:
    assert len(DETAIL_TITLES) == 9
    for view_id, title in DETAIL_TITLES.items():
        figure = detail_matrix_figure(
            view_id=view_id,
            labels=("A|X|A", "B|X|B"),
            matrix=((1.0, 0.2), (0.2, 1.0)),
        )
        assert figure["layout"]["title"] == title


def test_pr280_201_listing_fixture_has_exact_20100_pairs_and_stable_history() -> None:
    labels = tuple(f"ISIN-{index:04d}|XETRA|C{index:04d}" for index in range(201))
    pairs = tuple(
        PairHistoryPoint(labels[left], labels[right], 252, "2020-01-02", "2026-08-19")
        for left in range(len(labels))
        for right in range(left + 1, len(labels))
    )
    assert len(pairs) == 20_100
    forward = pair_history_figure(pairs)
    reverse = pair_history_figure(reversed(pairs))
    assert forward == reverse
    assert forward["layout"]["meta"]["pair_count"] == 20_100
    assert forward["layout"]["meta"]["unavailable_pair_ids"] == []
