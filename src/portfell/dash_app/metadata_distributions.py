"""Deterministic compact distributions for the Metadata read plane."""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def universe_distributions(
    rows: Iterable[Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    materialized = tuple(rows)
    result: dict[str, list[dict[str, object]]] = {}
    for field in ("instrument_type", "country", "currency"):
        counts: dict[str, int] = {}
        for row in materialized:
            value = row.get(field)
            label = str(value).strip() if value is not None and str(value).strip() else "Unknown"
            counts[label] = counts.get(label, 0) + 1
        result[field] = [
            {"category": label, "count": count}
            for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]
    return result


__all__ = ["universe_distributions"]
