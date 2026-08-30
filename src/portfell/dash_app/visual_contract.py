"""Deterministic visual QA dimensions and shared presentation-only formatting."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Viewport:
    name: str
    width: int
    height: int


VISUAL_VIEWPORTS = (
    Viewport("desktop", 1440, 900),
    Viewport("tablet", 1024, 768),
    Viewport("mobile", 390, 844),
)

PAGE_ROUTES = ("/metadata", "/univariate", "/bivariate", "/multivariate")
REFERENCE_URL = "https://financial-dashboard-example.plotly.app/"


def display_number(value: object, *, digits: int = 4) -> str:
    """Presentation-only numeric formatter; missing data is never encoded as zero."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def display_percent(value: object, *, digits: int = 2) -> str:
    """Format an already-computed decimal metric without changing its analytical value."""
    if value is None:
        return "—"
    if not isinstance(value, int | float) or isinstance(value, bool):
        return str(value)
    return f"{100 * float(value):.{digits}f}%"


__all__ = ["PAGE_ROUTES", "REFERENCE_URL", "VISUAL_VIEWPORTS", "Viewport", "display_number", "display_percent"]
