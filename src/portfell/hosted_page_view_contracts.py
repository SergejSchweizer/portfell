"""Versioned, compact page-view envelopes for hosted module entry routes."""

from __future__ import annotations

import base64
import json
from typing import Any, cast

from portfell.hosted_api_service_support import stable_hash

JsonRow = dict[str, Any]

PAGE_VIEW_CONTRACT_VERSION = 1
MAX_LAZY_SECTION_BYTES = 2 * 1024 * 1024

_ANALYTICAL_SECTIONS: dict[str, tuple[str, ...]] = {
    "univariate_statistics": ("results", "selection_results"),
    "bivariate_statistics": (
        "results",
        "summary",
        "covariance_matrix",
        "correlation_matrix",
        "tail_risk_scatter",
    ),
    "multivariate_statistics": (
        "summary",
        "structure",
        "candidates",
        "candidate_detail",
        "risk_contributions",
        "income_evidence",
        "components",
        "validation",
        "artifacts",
        "performance",
    ),
}


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


def analytical_page_view(
    *, module: str, project_id: str, workflow: JsonRow
) -> tuple[JsonRow, str]:
    """Return a compact analytical entry view without reading result payloads."""

    if module not in _ANALYTICAL_SECTIONS:
        raise ValueError("page_view_module_invalid")
    stages_value = workflow.get("stages")
    if not isinstance(stages_value, dict):
        raise ValueError("page_view_workflow_invalid")
    stages = cast(JsonRow, stages_value)
    stage_value = stages.get(module)
    if not isinstance(stage_value, dict):
        raise ValueError("page_view_workflow_stage_missing")
    stage = cast(JsonRow, stage_value)
    status = stage.get("status")
    if not isinstance(status, str):
        raise ValueError("page_view_workflow_status_invalid")
    workflow_etag = workflow.get("projection_etag")
    if workflow_etag is not None and not isinstance(workflow_etag, str):
        raise ValueError("page_view_workflow_etag_invalid")
    run_id = stage.get(f"{module.removesuffix('_statistics')}_run_id")
    if run_id is not None and not isinstance(run_id, str):
        raise ValueError("page_view_run_id_invalid")
    revision_seed: JsonRow = {
        "module": module,
        "project_id": project_id,
        "workflow_etag": workflow_etag,
        "stage": stage,
    }
    available = status == "complete"
    unavailable = None if available else {"code": "stage_not_complete", "status": status}
    sections: JsonRow = {
        key: _section_row(
            available=available,
            revision=stable_hash({**revision_seed, "section": key}),
            unavailable=unavailable,
        )
        for key in _ANALYTICAL_SECTIONS[module]
    }
    payload: JsonRow = {
        "contract_version": PAGE_VIEW_CONTRACT_VERSION,
        "module": module,
        "project_id": project_id,
        "workflow_etag": workflow_etag,
        "run_id": run_id,
        "status": status,
        "sections": sections,
    }
    return payload, stable_hash(payload)


def _section_row(*, available: bool, revision: str, unavailable: JsonRow | None) -> JsonRow:
    row: JsonRow = {"available": available, "revision": revision}
    if unavailable is not None:
        row["unavailable"] = unavailable
    return row


def encode_section_cursor(*, revision: str, offset: int) -> str:
    """Encode one immutable section page position without exposing its structure."""

    payload = json.dumps({"offset": offset, "revision": revision}, sort_keys=True).encode()
    return base64.urlsafe_b64encode(payload).decode().rstrip("=")


def decode_section_cursor(*, cursor: str, revision: str) -> int:
    """Resolve an opaque cursor only when it belongs to the requested revision."""

    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        value = json.loads(base64.urlsafe_b64decode(padded).decode())
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("section_cursor_invalid") from error
    if not isinstance(value, dict):
        raise ValueError("section_cursor_invalid")
    cursor_value = cast(JsonRow, value)
    offset = cursor_value.get("offset")
    cursor_revision = cursor_value.get("revision")
    if not isinstance(offset, int) or offset < 0 or not isinstance(cursor_revision, str):
        raise ValueError("section_cursor_invalid")
    if cursor_revision != revision:
        raise ValueError("section_revision_mismatch")
    return offset


def bounded_detail_section(*, revision: str, payload: JsonRow) -> JsonRow:
    """Attach a revision and reject indivisible responses above the documented limit."""

    row: JsonRow = {"revision": revision, "data": payload}
    encoded = json.dumps(row, sort_keys=True, separators=(",", ":")).encode()
    if len(encoded) > MAX_LAZY_SECTION_BYTES:
        raise ValueError("section_too_large")
    return row
