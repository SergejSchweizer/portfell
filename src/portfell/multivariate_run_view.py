"""API-ready persisted Multivariate run view serialization."""

from __future__ import annotations

from time import time

from portfell.hosted_api_state import MultivariateRunRecord
from portfell.table_io import JsonRow


def multivariate_run_row(run: MultivariateRunRecord) -> JsonRow:
    """Render server-owned, monotonic run progress without recalculation."""
    elapsed = max(0, int(time() - run.started_at_epoch)) if run.started_at_epoch else 0
    remaining_units = max(0, run.total_units - run.completed_units)
    per_unit = elapsed / run.completed_units if run.completed_units else 5.0
    return {
        "run_id": run.run_id,
        "project_id": run.project_id,
        "bivariate_run_id": run.bivariate_run_id,
        "input_snapshot_id": run.input_snapshot_id or None,
        "status": run.status,
        "phase": run.phase,
        "completed_units": run.completed_units,
        "total_units": run.total_units,
        "elapsed_seconds": elapsed,
        "estimated_remaining_seconds": 0
        if run.status in {"complete", "failed", "stale"}
        else max(1, int(remaining_units * per_unit)),
        "settings": dict(run.settings),
        "warnings": list(run.warnings),
        "failure_reason": run.failure_reason,
    }


def candidate_row(candidates: tuple[JsonRow, ...], candidate_id: str) -> JsonRow | None:
    """Return one persisted candidate without exposing its backing run."""

    return next(
        (dict(item) for item in candidates if item.get("candidate_id") == candidate_id), None
    )
