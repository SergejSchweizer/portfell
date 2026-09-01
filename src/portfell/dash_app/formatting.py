"""Presentation-only numeric formatting for the Dash read plane."""

from __future__ import annotations

import math


def format_float(value: object, *, percent: bool = False, unavailable: str = "—") -> str:
    """Render a finite scalar without changing the value used by analytics."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return unavailable if value is None else str(value)
    numeric = float(value)
    if not math.isfinite(numeric):
        return unavailable
    if percent:
        return f"{numeric:.5%}"
    rendered = f"{numeric:.5f}"
    return "0.00000" if rendered == "-0.00000" else rendered


__all__ = ["format_float"]
