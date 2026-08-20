"""Immutable DecisionArtifact contracts and idempotent sink semantics."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field

from portfell.multivariate.contracts.common import DecisionStageId, EvidenceAvailability, ListingIdentity
from portfell.multivariate.contracts.decision_reasons import DecisionReasonCode
from portfell.multivariate.contracts.serialization import canonical_json


@dataclass(frozen=True, slots=True)
class DecisionCandidate:
    candidate_id: str
    metrics: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DecisionRejection:
    candidate_id: str
    reason_code: DecisionReasonCode
    evidence: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DecisionArtifact:
    run_id: str
    objective: str
    stage: DecisionStageId
    pinned_revisions: tuple[str, ...]
    candidates: tuple[DecisionCandidate, ...]
    selected_ids: tuple[str, ...]
    rejections: tuple[DecisionRejection, ...]
    status: EvidenceAvailability
    reason_code: DecisionReasonCode
    algorithm_version: str
    profile_version: str
    listing_scope: tuple[ListingIdentity, ...] = ()

    @property
    def decision_id(self) -> str:
        canonical = canonical_json(
            {
                "run_id": self.run_id,
                "objective": self.objective,
                "stage": self.stage,
                "pinned_revisions": self.pinned_revisions,
                "candidates": self.candidates,
                "selected_ids": self.selected_ids,
                "rejections": self.rejections,
                "status": self.status,
                "reason_code": self.reason_code,
                "algorithm_version": self.algorithm_version,
                "profile_version": self.profile_version,
                "listing_scope": self.listing_scope,
            }
        ).encode()
        return hashlib.sha256(canonical).hexdigest()


class DecisionConflictError(RuntimeError):
    """Raised when one content-addressed decision ID receives different bytes."""


class IdempotentDecisionSink:
    """Reference sink enforcing exact idempotent/conflict semantics."""

    def __init__(self) -> None:
        self._payloads: dict[str, str] = {}

    def put_payload(self, *, decision_id: str, canonical_payload: str) -> bool:
        """Write canonical bytes under an explicit ID and fail closed on conflicts."""

        if not decision_id:
            raise ValueError("decision_id is required")
        decoded = json.loads(canonical_payload)
        if canonical_json(decoded) != canonical_payload:
            raise ValueError("decision payload must use canonical JSON bytes")
        previous = self._payloads.get(decision_id)
        if previous is None:
            self._payloads[decision_id] = canonical_payload
            return True
        if previous != canonical_payload:
            raise DecisionConflictError(f"conflicting decision payload for {decision_id}")
        return False

    def put(self, artifact: DecisionArtifact) -> bool:
        """Return True for a new write, False for an identical no-op."""

        return self.put_payload(
            decision_id=artifact.decision_id,
            canonical_payload=canonical_json(artifact),
        )

    def get(self, decision_id: str) -> str | None:
        return self._payloads.get(decision_id)
