"""Project-scoped repositories for canonical Multivariate evidence."""

from __future__ import annotations

import json
from dataclasses import dataclass

from portfell.hosted_catalog_ports import CatalogConnection


class EvidenceConflictError(RuntimeError):
    """Raised when one logical evidence ID is reused with different canonical bytes."""


@dataclass(frozen=True, slots=True)
class StoredEvidence:
    evidence_id: str
    run_id: str
    stage: str
    canonical_payload: str


def _existing_payload(
    connection: CatalogConnection,
    *,
    table: str,
    id_column: str,
    evidence_id: str,
) -> str | None:
    row = connection.execute(
        f"select canonical_payload::text from portfell_app.{table} where {id_column} = %s",
        (evidence_id,),
    ).fetchone()
    return None if row is None else str(row[0])


def _canonical_json_text(payload: str) -> str:
    value = json.loads(payload)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def put_decision(
    connection: CatalogConnection,
    *,
    user_id: str,
    project_id: str,
    evidence: StoredEvidence,
) -> bool:
    """Insert an immutable decision; identical replay is a no-op and conflict fails closed."""

    payload = _canonical_json_text(evidence.canonical_payload)
    previous = _existing_payload(
        connection,
        table="multivariate_decisions",
        id_column="decision_id",
        evidence_id=evidence.evidence_id,
    )
    if previous is not None:
        if _canonical_json_text(previous) != payload:
            raise EvidenceConflictError(f"conflicting decision payload: {evidence.evidence_id}")
        return False
    connection.execute(
        """
insert into portfell_app.multivariate_decisions
(decision_id, user_id, project_id, run_id, stage, canonical_payload)
values (%s, %s::uuid, %s::uuid, %s, %s, %s::jsonb)
""",
        (evidence.evidence_id, user_id, project_id, evidence.run_id, evidence.stage, payload),
    )
    return True


def put_snapshot(
    connection: CatalogConnection,
    *,
    user_id: str,
    project_id: str,
    evidence: StoredEvidence,
) -> bool:
    """Insert an immutable ResearchUniverseSnapshot with the same conflict semantics."""

    payload = _canonical_json_text(evidence.canonical_payload)
    previous = _existing_payload(
        connection,
        table="research_universe_snapshots",
        id_column="snapshot_id",
        evidence_id=evidence.evidence_id,
    )
    if previous is not None:
        if _canonical_json_text(previous) != payload:
            raise EvidenceConflictError(f"conflicting snapshot payload: {evidence.evidence_id}")
        return False
    connection.execute(
        """
insert into portfell_app.research_universe_snapshots
(snapshot_id, user_id, project_id, run_id, stage, canonical_payload)
values (%s, %s::uuid, %s::uuid, %s, %s, %s::jsonb)
""",
        (evidence.evidence_id, user_id, project_id, evidence.run_id, evidence.stage, payload),
    )
    return True


def put_current_selection(
    connection: CatalogConnection,
    *,
    user_id: str,
    project_id: str,
    selection_revision: str,
    canonical_payload: str,
) -> None:
    """Upsert only the current project-scoped pointer; immutable evidence remains append-only."""

    payload = _canonical_json_text(canonical_payload)
    connection.execute(
        """
insert into portfell_app.multivariate_current_selections
(user_id, project_id, selection_revision, canonical_payload)
values (%s::uuid, %s::uuid, %s, %s::jsonb)
on conflict (user_id, project_id) do update
set selection_revision = excluded.selection_revision,
    canonical_payload = excluded.canonical_payload,
    updated_at = now()
where portfell_app.multivariate_current_selections.selection_revision <> excluded.selection_revision
""",
        (user_id, project_id, selection_revision, payload),
    )


def list_run_evidence(
    connection: CatalogConnection,
    *,
    project_id: str,
    run_id: str,
    kind: str,
) -> tuple[StoredEvidence, ...]:
    """Read stored evidence only; no analytical calculation is performed."""

    if kind == "decision":
        table, id_column = "multivariate_decisions", "decision_id"
    elif kind == "snapshot":
        table, id_column = "research_universe_snapshots", "snapshot_id"
    else:
        raise ValueError("kind must be decision or snapshot")
    rows = connection.execute(
        f"""
select {id_column}, run_id, stage, canonical_payload::text
from portfell_app.{table}
where project_id = %s::uuid and run_id = %s
order by stage, {id_column}
""",
        (project_id, run_id),
    ).fetchall()
    return tuple(StoredEvidence(str(row[0]), str(row[1]), str(row[2]), str(row[3])) for row in rows)
