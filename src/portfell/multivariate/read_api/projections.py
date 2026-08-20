"""Projection helpers that never invoke analytical calculators."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from portfell.hosted_catalog_ports import CatalogConnection
from portfell.multivariate.persistence.repository import list_run_evidence


@dataclass(frozen=True, slots=True)
class MultivariateEvidenceProjection:
    project_slug: str
    run_id: str
    decisions: tuple[Mapping[str, object], ...]
    history: tuple[Mapping[str, object], ...]


def _decode(payload: str) -> Mapping[str, object]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError("persisted evidence payload must be an object")
    return value


def project_run_evidence(
    connection: CatalogConnection,
    *,
    project_slug: str,
    run_id: str,
    resolve_project_id: Callable[[str], str],
) -> MultivariateEvidenceProjection:
    """Authorize/resolve project before repository access and decode stored bytes only."""

    project_id = resolve_project_id(project_slug)
    decisions = tuple(
        _decode(row.canonical_payload)
        for row in list_run_evidence(connection, project_id=project_id, run_id=run_id, kind="decision")
    )
    history = tuple(
        _decode(row.canonical_payload)
        for row in list_run_evidence(connection, project_id=project_id, run_id=run_id, kind="snapshot")
    )
    return MultivariateEvidenceProjection(project_slug, run_id, decisions, history)


def section_projection(
    projection: MultivariateEvidenceProjection,
    *,
    section_id: str,
) -> Mapping[str, object]:
    """Return one persisted decision stage or a typed unavailable state."""

    for decision in projection.decisions:
        if decision.get("stage") == section_id:
            return decision
    return {"availability": "unavailable", "reason": "section_not_persisted", "section_id": section_id}


def pipeline_projection(projection: MultivariateEvidenceProjection) -> tuple[Mapping[str, object], ...]:
    """Return snapshots in stable research-stage order without recomputing counts/ranges."""

    order = {"metadata": 0, "univariate": 1, "bivariate": 2, "multivariate": 3, "final_portfolio": 4}
    return tuple(sorted(projection.history, key=lambda item: (order.get(str(item.get("stage")), 99), str(item.get("snapshot_id", "")))))
