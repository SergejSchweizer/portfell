"""Apply persisted project filters to completed univariate result rows."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from portfell.table_io import JsonRow


def apply_univariate_selection_settings(
    rows: tuple[JsonRow, ...], settings: JsonRow
) -> tuple[JsonRow, ...]:
    """Apply project dropdown selections to the completed univariate universe."""

    frequencies = settings.get("dividend_frequencies", [])
    ranges_by_metric = settings.get("statistic_ranges", {})
    selected_frequencies: set[str] = set()
    if isinstance(frequencies, list):
        selected_frequencies = {
            value for value in cast(list[object], frequencies) if isinstance(value, str)
        }
    selected_ranges: dict[str, tuple[Mapping[str, object], ...]] = {}
    if isinstance(ranges_by_metric, Mapping):
        for raw_metric, raw_ranges in cast(Mapping[object, object], ranges_by_metric).items():
            if not isinstance(raw_metric, str) or not isinstance(raw_ranges, list):
                continue
            selected_ranges[raw_metric] = tuple(
                cast(Mapping[str, object], item)
                for item in cast(list[object], raw_ranges)
                if isinstance(item, Mapping)
            )

    def includes_value(item: Mapping[str, object], value: float) -> bool:
        minimum = item.get("minimum")
        maximum = item.get("maximum")
        return (
            not isinstance(minimum, bool)
            and not isinstance(maximum, bool)
            and isinstance(minimum, int | float)
            and isinstance(maximum, int | float)
            and float(minimum) <= value <= float(maximum)
        )

    def matches(row: JsonRow) -> bool:
        frequency = str(row.get("distribution_frequency", "accumulating"))
        if frequency not in {"monthly", "quarterly", "semiannual", "annual", "irregular"}:
            frequency = "accumulating"
        if selected_frequencies and frequency not in selected_frequencies:
            return False
        for metric, ranges in selected_ranges.items():
            if not ranges:
                continue
            value = row.get(metric)
            if isinstance(value, bool) or not isinstance(value, int | float):
                return False
            if not any(includes_value(item, float(value)) for item in ranges):
                return False
        return True

    return tuple(row for row in rows if matches(row))
