"""Pure callback projections for persisted Multivariate evidence."""

from __future__ import annotations

from collections.abc import Mapping


def replace_project_state(
    *,
    requested_project_slug: str,
    received_project_slug: str,
    payload: Mapping[str, object],
) -> Mapping[str, object] | None:
    """Drop obsolete reads so old-project evidence cannot paint after a project switch."""

    if requested_project_slug != received_project_slug:
        return None
    return payload


def lazy_section_payload(
    *,
    section_id: str,
    sections: tuple[Mapping[str, object], ...],
) -> Mapping[str, object]:
    """Select one persisted section without analytical reconstruction."""

    for section in sections:
        if section.get("stage") == section_id:
            return section
    return {"availability": "unavailable", "reason": "section_not_persisted", "stage": section_id}
