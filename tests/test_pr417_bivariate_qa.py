"""Independent pairwise oracle tests for the Bivariate boundary."""

from __future__ import annotations

from itertools import combinations

import pytest

from portfell.bivariate_statistics import build_bivariate_statistics


def _rows() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for index, isin in enumerate(("A", "B", "C")):
        for day, value in enumerate((0.01 + index * 0.02, -0.01, 0.03), 1):
            result.append(
                {
                    "isin": isin,
                    "exchange": "XETRA",
                    "code": isin,
                    "date": f"2026-01-0{day}",
                    "return": value,
                }
            )
    return result


def test_pair_oracle_has_exact_unique_pairs_and_common_dates() -> None:
    rows = build_bivariate_statistics(_rows(), concurrency=1)
    expected_pairs = {tuple(sorted(pair)) for pair in combinations(("A", "B", "C"), 2)}
    actual_pairs = {tuple(sorted((str(row["left_isin"]), str(row["right_isin"])))) for row in rows}
    assert actual_pairs == expected_pairs
    assert len(rows) == 3
    assert all(row["n_observations"] == 3 for row in rows)


def test_changed_selection_input_cannot_be_confused_with_previous_pair_set() -> None:
    first = build_bivariate_statistics(_rows()[:6], concurrency=1)
    second = build_bivariate_statistics(_rows()[3:], concurrency=1)
    first_ids = {(row["left_isin"], row["right_isin"]) for row in first}
    second_ids = {(row["left_isin"], row["right_isin"]) for row in second}
    assert first_ids == {("A", "B")}
    assert second_ids == {("B", "C")}


@pytest.mark.parametrize("count", [0, 1])
def test_fewer_than_two_listings_produces_no_pairs(count: int) -> None:
    assert build_bivariate_statistics(_rows()[: count * 3], concurrency=1) == []
