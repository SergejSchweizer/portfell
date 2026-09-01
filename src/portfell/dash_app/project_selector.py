"""Identifier-only project selector models for the shared sidebar."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import cast


def project_options(universes: Sequence[Mapping[str, object]]) -> list[dict[str, str]]:
    """Return every persisted universe, newest first, with collision-safe IDs."""
    ordered = sorted(
        universes,
        key=lambda row: (
            int(cast(int | str, row.get("version", 0))),
            str(row.get("universe_id", "")),
        ),
        reverse=True,
    )
    return [
        {
            "label": (
                str(row.get("project_name"))
                if row.get("project_name")
                else f"Universe v{row.get('version', '—')} · {str(row.get('universe_id', ''))[:12]}"
            ),
            "value": str(row.get("universe_id", "")),
        }
        for row in ordered
        if row.get("universe_id")
    ]


def select_project(
    universes: Sequence[Mapping[str, object]], selected_id: str | None = None
) -> Mapping[str, object] | None:
    options = project_options(universes)
    value = selected_id or (options[0]["value"] if options else None)
    return next((row for row in universes if row.get("universe_id") == value), None)


__all__ = ["project_options", "select_project"]
