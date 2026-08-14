"""Versioned, compact page-view envelopes for hosted module entry routes."""

from __future__ import annotations

from typing import Any

from portfell.hosted_api_service_support import stable_hash

JsonRow = dict[str, Any]

PAGE_VIEW_CONTRACT_VERSION = 1


def metadata_builder_page_view(
    *, project_id: str, criteria: JsonRow, initial_fill: JsonRow | None, workflow: JsonRow
) -> tuple[JsonRow, str]:
    """Return one small, deterministic Metadata Builder entry contract and ETag."""

    payload: JsonRow = {
        "contract_version": PAGE_VIEW_CONTRACT_VERSION,
        "module": "metadata_builder",
        "project_id": project_id,
        "workflow": workflow,
        "summary": {"criteria": criteria, "initial_fill": initial_fill},
        "sections": {
            "criteria": {"available": True, "revision": stable_hash(criteria)},
            "initial_fill": (
                {"available": True, "revision": stable_hash(initial_fill)}
                if initial_fill is not None
                else {
                    "available": False,
                    "unavailable": {"code": "initial_fill_not_found"},
                }
            ),
        },
    }
    return payload, stable_hash(payload)
