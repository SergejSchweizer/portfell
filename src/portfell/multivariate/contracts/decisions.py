"""Immutable DecisionArtifact contracts and idempotent sink semantics."""

from __future__ import annotations

import hashlib
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
    """Small reference sink used by services and tests to enforce conflict semantics."""

    def __init__(self) -> None:
        self._payloads: dict[str, str] = {}

    def put(self, artifact: DecisionArtifact) -> bool:
        """Return True for a new write, False for an identical no-op."""

        decision_id = artifact.decision_id
        payload = canonical_json(artifact)
        previous = self._payloads.get(decision_id)
        if previous is None:
            self._payloads[decision_id] = payload
            return True
        if previous != payload:
            raise DecisionConflictError(f"conflicting decision payload for {decision_id}")
        return False

    def get(self, decision_id: str) -> str | None:
        return self._payloads.get(decision_id)
