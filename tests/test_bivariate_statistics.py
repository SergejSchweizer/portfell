import json
import os
from pathlib import Path
from statistics import correlation, covariance, variance

import pytest

from portfell.bivariate_statistics import (
    build_bivariate_statistics,
    resolve_worker_count,
    write_bivariate_statistics,
)
from portfell.bivariate_views import (
    build_bivariate_summary,
    build_correlation_matrix,
    build_tail_risk_scatter,
)
from portfell.gold_pair_stats import correlation_value
from portfell.hosted_page_view_contracts import MAX_LAZY_SECTION_BYTES, bounded_detail_section
from portfell.paths import LakePaths
from portfell.run_state import read_job_manifest
from portfell.table_io import read_rows, write_rows


def _return(isin: str, exchange: str, code: str, date: str, value: float) -> dict[str, object]:
    return {
        "isin": isin,
        "exchange": exchange,
        "code": code,
        "date": date,
        "return": value,
    }


def test_bivariate_statistics_use_pairwise_dates_and_metrics(tmp_path: Path) -> None:
    paths = LakePaths(root=tmp_path / "lake")
    returns = [
        _return("IE1", "XETRA", "AAA", "2026-01-01", 0.01),
        _return("IE1", "XETRA", "AAA", "2026-01-02", 0.02),
        _return("IE1", "XETRA", "AAA", "2026-01-03", 0.03),
        _return("IE2", "AS", "BBB", "2026-01-01", 0.03),
        _return("IE2", "AS", "BBB", "2026-01-02", 0.02),
        _return("IE2", "AS", "BBB", "2026-01-03", 0.01),
        _return("IE3", "XETRA", "CCC", "2026-01-02", 0.10),
        _return("IE3", "XETRA", "CCC", "2026-01-03", 0.11),
    ]

    statistics = build_bivariate_statistics(returns)
    written = write_bivariate_statistics(paths, returns, version="v1")

    assert len(statistics) == 3
    row = statistics[0]
    assert row["left_isin"] == "IE1"
    assert row["right_isin"] == "IE2"
    assert row["left_listing_key"] == "XETRA__IE1__AAA"
    assert row["right_listing_key"] == "AS__IE2__BBB"
    assert row["pair_key"] == "XETRA__IE1__AAA___AS__IE2__BBB"
    assert row["date_start"] == "2026-01-01"
    assert row["date_end"] == "2026-01-03"
    assert row["n_observations"] == 3
    assert row["pearson_correlation"] == pytest.approx(-1.0)
    assert row["covariance"] == pytest.approx(-0.0001)
    assert row["left_variance"] == pytest.approx(0.0001)
    assert row["right_variance"] == pytest.approx(0.0001)
    assert row["left_beta_to_right"] == pytest.approx(-1.0)
    assert row["right_beta_to_left"] == pytest.approx(-1.0)
    assert "spearman_correlation" in row
    assert "tail_joint_loss_severity" in row
    assert "rolling_tail_dependence_stability" in row
    assert {k: v for k, v in written[0].items() if k not in {"version", "bucket"}} == statistics[0]
    written_row = next(item for item in written if item["pair_key"] == row["pair_key"])
    assert written_row["version"] == "v1"
    assert written_row["bucket"] == written_row["left_id"] % 128
    bucket_path = paths.gold_bivariate_statistics_bucket("v1", int(written_row["bucket"]))
    assert any(item["pair_key"] == row["pair_key"] for item in read_rows(bucket_path))

    manifest = read_job_manifest(paths, "bivariate-statistics-plan", "v1")
    assert manifest["status"] == "completed"
    assert manifest["row_counts"]["listing_count"] == 3
    assert {
        (item["date_start"], item["date_end"], item["n_observations"]) for item in statistics
    } == {
        ("2026-01-01", "2026-01-03", 3),
        ("2026-01-02", "2026-01-03", 2),
    }
    summary = build_bivariate_summary(tuple(statistics))
    assert summary["date_start"] == "2026-01-01"
    assert summary["date_end"] == "2026-01-03"
    assert summary["observation_count_min"] == 2
    assert summary["observation_count_max"] == 3
    tail_diagnostics = summary["tail_dependence_diagnostics"]
    assert tail_diagnostics["high_30_pairs"] >= 0
    assert tail_diagnostics["worst_pair"] is not None
    assert tail_diagnostics["best_diversifier_pair"] is not None
    assert tail_diagnostics["median_joint_tail_events"] is not None
    coexceedance_diagnostics = build_bivariate_summary(tuple(statistics))[
        "coexceedance_diagnostics"
    ]
    assert coexceedance_diagnostics["independence_baseline"] == pytest.approx(0.0025)
    assert coexceedance_diagnostics["high_1_pairs"] >= 0
    assert coexceedance_diagnostics["worst_pair"] is not None
    scatter_diagnostics = build_tail_risk_scatter(tuple(statistics))["diagnostics"]
    assert scatter_diagnostics["pareto_best_pair_count"] >= 1
    assert scatter_diagnostics["tail_independence_baseline"] == pytest.approx(0.05)
    drawdown_matrix = build_correlation_matrix(tuple(statistics), "drawdown_overlap")
    assert drawdown_matrix["labels"]
    assert drawdown_matrix["values"][0][1] == statistics[0]["drawdown_overlap_rate"]
    assert drawdown_matrix["observation_count_min"] == 2
    assert drawdown_matrix["observation_count_max"] == 3
    rolling_matrix = build_correlation_matrix(tuple(statistics), "rolling_stability")
    assert rolling_matrix["values"][0][1] == statistics[0]["rolling_correlation_stability"]
    scatter = build_tail_risk_scatter(tuple(statistics))
    assert len(scatter["labels"]) == 3
    assert scatter["points"][0]["left"] == 0
    assert scatter["points"][0]["right"] == 1
    assert scatter["observation_count_min"] == 2
    assert scatter["observation_count_max"] == 3


def test_tail_risk_scatter_keeps_all_201_listing_pairs_bounded() -> None:
    rows = tuple(
        {
            "left_isin": f"IE{left:010d}",
            "left_exchange": "XETRA",
            "left_code": f"ETF{left:03d}",
            "right_isin": f"IE{right:010d}",
            "right_exchange": "XETRA",
            "right_code": f"ETF{right:03d}",
            "date_start": "2025-01-01",
            "date_end": "2026-01-01",
            "n_observations": 252,
            "lower_tail_dependence": 0.1234567890123456,
            "tail_coexceedance_rate": 0.0098765432109876,
        }
        for left in range(201)
        for right in range(left + 1, 201)
    )

    scatter = build_tail_risk_scatter(rows)
    response = bounded_detail_section(revision="revision-201", payload=scatter)

    assert len(scatter["labels"]) == 201
    assert scatter["pair_count"] == 20_100
    assert len(scatter["points"]) == 20_100
    assert len(json.dumps(response, sort_keys=True, separators=(",", ":")).encode()) < (
        MAX_LAZY_SECTION_BYTES
    )


def test_bivariate_statistics_keep_pairs_with_a_common_calendar() -> None:
    returns = [
        _return("IE1", "XETRA", "AAA", "2026-01-01", 0.01),
        _return("IE2", "AS", "BBB", "2026-01-01", 0.02),
        _return("IE3", "PA", "CCC", "2026-01-02", 0.03),
    ]

    statistics = build_bivariate_statistics(returns)

    assert len(statistics) == 1
    assert statistics[0]["left_isin"] == "IE1"
    assert statistics[0]["right_isin"] == "IE2"
    assert statistics[0]["n_observations"] == 1


def test_bivariate_statistics_reuses_cached_buckets_and_writes_delta(tmp_path: Path) -> None:
    paths = LakePaths(root=tmp_path / "lake")
    first_selection = [
        _return("IE1", "XETRA", "AAA", "2026-01-01", 0.01),
        _return("IE1", "XETRA", "AAA", "2026-01-02", 0.02),
        _return("IE2", "AS", "BBB", "2026-01-01", 0.03),
        _return("IE2", "AS", "BBB", "2026-01-02", 0.02),
    ]
    first = write_bivariate_statistics(paths, first_selection, version="v1")
    bucket_path = paths.gold_bivariate_statistics_bucket("v1", int(first[0]["bucket"]))
    first_mtime = bucket_path.stat().st_mtime_ns

    expanded_selection = [
        *first_selection,
        _return("IE3", "PA", "CCC", "2026-01-01", 0.04),
        _return("IE3", "PA", "CCC", "2026-01-02", 0.05),
    ]
    expanded = write_bivariate_statistics(paths, expanded_selection, version="v1")

    assert len(first) == 1
    assert len(expanded) == 3
    new_pair = next(row for row in expanded if row["right_isin"] == "IE3")
    new_bucket_path = paths.gold_bivariate_statistics_bucket("v1", int(new_pair["bucket"]))
    if new_bucket_path == bucket_path:
        assert bucket_path.stat().st_mtime_ns != first_mtime
    else:
        assert bucket_path.stat().st_mtime_ns == first_mtime
    assert any(row["pair_key"] == new_pair["pair_key"] for row in read_rows(new_bucket_path))


def test_bivariate_statistics_invalidates_cache_when_return_content_changes(
    tmp_path: Path,
) -> None:
    paths = LakePaths(root=tmp_path / "lake")
    returns = [
        _return("IE1", "XETRA", "AAA", "2026-01-01", 0.01),
        _return("IE1", "XETRA", "AAA", "2026-01-02", 0.02),
        _return("IE1", "XETRA", "AAA", "2026-01-03", 0.03),
        _return("IE2", "AS", "BBB", "2026-01-01", 0.03),
        _return("IE2", "AS", "BBB", "2026-01-02", 0.02),
        _return("IE2", "AS", "BBB", "2026-01-03", 0.01),
    ]
    first = write_bivariate_statistics(paths, returns, version="test", concurrency=1)[0]
    revised_returns = [
        {**row, "return": -0.03} if row["isin"] == "IE2" and row["date"] == "2026-01-03" else row
        for row in returns
    ]

    revised = write_bivariate_statistics(paths, revised_returns, version="test", concurrency=1)[0]

    assert revised["pair_input_id"] != first["pair_input_id"]
    assert revised["covariance"] != first["covariance"]


def test_spearman_correlation_uses_exact_average_ranks_for_ties() -> None:
    assert correlation_value([1, 2, 3, 4, 5], [1, 4, 9, 16, 25], "spearman") == pytest.approx(1.0)
    assert correlation_value([1, 2, 2, 4, 5], [10, 20, 20, 30, 40], "spearman") == pytest.approx(
        1.0
    )
    assert correlation_value([1, 2, 3, 4, 5], [25, 16, 9, 4, 1], "spearman") == pytest.approx(-1.0)


def test_bivariate_pair_formulas_match_independent_reference() -> None:
    left = [-0.08, -0.04, 0.01, 0.03, -0.02, 0.05]
    right = [-0.06, -0.03, 0.02, -0.01, -0.04, 0.04]
    returns = [
        _return(isin, exchange, code, f"2026-01-{index:02d}", value)
        for isin, exchange, code, values in (
            ("IE1", "XETRA", "AAA", left),
            ("IE2", "AS", "BBB", right),
        )
        for index, value in enumerate(values, start=1)
    ]
    left_ranks = [1.0, 2.0, 4.0, 5.0, 3.0, 6.0]
    right_ranks = [1.0, 3.0, 5.0, 4.0, 2.0, 6.0]
    downside_pairs = [(a, b) for a, b in zip(left, right, strict=True) if a < 0 and b < 0]
    left_cutoff = sorted(left)[round((len(left) - 1) * 0.05)]
    right_cutoff = sorted(right)[round((len(right) - 1) * 0.05)]
    joint_tail = [
        (a, b) for a, b in zip(left, right, strict=True) if a <= left_cutoff and b <= right_cutoff
    ]

    row = build_bivariate_statistics(returns, concurrency=1)[0]

    assert row["pearson_correlation"] == pytest.approx(correlation(left, right))
    assert row["spearman_correlation"] == pytest.approx(correlation(left_ranks, right_ranks))
    assert row["covariance"] == pytest.approx(covariance(left, right))
    assert row["left_variance"] == pytest.approx(variance(left))
    assert row["right_variance"] == pytest.approx(variance(right))
    assert row["left_beta_to_right"] == pytest.approx(covariance(left, right) / variance(right))
    assert row["right_beta_to_left"] == pytest.approx(covariance(left, right) / variance(left))
    assert row["downside_observation_count"] == len(downside_pairs)
    assert row["downside_correlation"] == pytest.approx(
        correlation([item[0] for item in downside_pairs], [item[1] for item in downside_pairs])
    )
    assert row["lower_tail_dependence"] == pytest.approx(1.0)
    assert row["tail_coexceedance_rate"] == pytest.approx(len(joint_tail) / len(left))
    assert row["tail_joint_event_count"] == len(joint_tail)
    assert row["tail_joint_loss_severity"] == pytest.approx(
        sum(-(a + b) / 2 for a, b in joint_tail) / len(joint_tail)
    )


def test_bivariate_statistics_rejects_universes_above_max_pair_count(tmp_path: Path) -> None:
    paths = LakePaths(root=tmp_path / "lake")
    returns = [_return(f"IE{i}", "XETRA", "AAA", "2026-01-01", 0.01) for i in range(40)]

    with pytest.raises(ValueError, match="exceeds max_pair_count"):
        write_bivariate_statistics(paths, returns, version="v1", max_pair_count=100)

    manifest = read_job_manifest(paths, "bivariate-statistics-plan", "v1")
    assert manifest["status"] == "failed"
    assert manifest["error_summary"][0]["reason"] is not None
    with pytest.raises(ValueError, match="exceeds max_pair_count"):
        build_bivariate_statistics(returns, max_pair_count=100)


def test_bivariate_statistics_discards_corrupt_bucket_cache(tmp_path: Path) -> None:
    paths = LakePaths(root=tmp_path / "lake")
    returns = [
        _return("IE1", "XETRA", "AAA", "2026-01-01", 0.01),
        _return("IE1", "XETRA", "AAA", "2026-01-02", 0.02),
        _return("IE2", "AS", "BBB", "2026-01-01", 0.03),
        _return("IE2", "AS", "BBB", "2026-01-02", 0.02),
    ]
    first = write_bivariate_statistics(paths, returns, version="v1")
    bucket = int(first[0]["bucket"])
    bucket_path = paths.gold_bivariate_statistics_bucket("v1", bucket)
    corrupted_row = dict(first[0])
    corrupted_row["bucket"] = bucket + 1
    write_rows(bucket_path, [corrupted_row])

    rewritten = write_bivariate_statistics(paths, returns, version="v1")

    assert rewritten[0]["bucket"] == bucket
    assert read_rows(bucket_path)[0]["bucket"] == bucket


def test_bivariate_statistics_skip_same_isin_pairs_by_default() -> None:
    returns = [
        _return("IE1", "XETRA", "AAA", "2026-01-01", 0.01),
        _return("IE1", "AS", "BBB", "2026-01-01", 0.02),
    ]

    assert build_bivariate_statistics(returns) == []
    assert len(build_bivariate_statistics(returns, skip_same_isin=False)) == 1


def test_bivariate_statistics_parallel_matches_serial() -> None:
    returns = [
        _return("IE1", "XETRA", "AAA", "2026-01-01", 0.01),
        _return("IE1", "XETRA", "AAA", "2026-01-02", 0.02),
        _return("IE1", "XETRA", "AAA", "2026-01-03", 0.03),
        _return("IE2", "AS", "BBB", "2026-01-01", 0.03),
        _return("IE2", "AS", "BBB", "2026-01-02", 0.02),
        _return("IE2", "AS", "BBB", "2026-01-03", 0.01),
        _return("IE3", "PA", "CCC", "2026-01-01", 0.02),
        _return("IE3", "PA", "CCC", "2026-01-02", 0.03),
        _return("IE3", "PA", "CCC", "2026-01-03", 0.04),
    ]

    serial = build_bivariate_statistics(returns, concurrency=1)
    parallel = build_bivariate_statistics(returns, concurrency=2)

    assert parallel == serial


def test_resolve_worker_count_caps_default_and_honors_explicit_concurrency() -> None:
    assert resolve_worker_count(1) == 1
    assert resolve_worker_count(None, max_workers=4) == min(4, os.cpu_count() or 1)
    assert resolve_worker_count(None, max_workers=1) == 1
