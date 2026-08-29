"""Shared immutable Univariate artifact catalog and project-run references."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


class SharedUnivariateArtifactError(ValueError):
    """Raised for stable shared artifact catalog or authorization errors."""


@dataclass(frozen=True)
class SharedUnivariateArtifact:
    """Tenant-neutral immutable Univariate artifact identity and content checksum."""

    artifact_id: str
    return_artifact_id: str
    content_hash: str

    def __post_init__(self) -> None:
        if not all((self.artifact_id, self.return_artifact_id, self.content_hash)):
            raise SharedUnivariateArtifactError("univariate_artifact_identity_required")

    @classmethod
    def from_payload(
        cls, artifact_id: str, return_artifact_id: str, payload: bytes
    ) -> SharedUnivariateArtifact:
        """Build a catalog record for canonical shared payload bytes."""

        if not payload:
            raise SharedUnivariateArtifactError("univariate_artifact_payload_required")
        return cls(artifact_id, return_artifact_id, _payload_hash(payload))


class InMemorySharedUnivariateArtifacts:
    """Test double for immutable publication and project-scoped artifact references."""

    def __init__(self) -> None:
        self._artifacts: dict[str, SharedUnivariateArtifact] = {}
        self._references: dict[tuple[str, str], str] = {}

    @property
    def artifact_count(self) -> int:
        return len(self._artifacts)

    def publish(self, artifact: SharedUnivariateArtifact) -> SharedUnivariateArtifact:
        """Publish or return exactly matching immutable artifact content."""

        existing = self._artifacts.get(artifact.artifact_id)
        if existing is not None:
            if existing != artifact:
                raise SharedUnivariateArtifactError("univariate_artifact_id_conflict")
            return existing
        self._artifacts[artifact.artifact_id] = artifact
        return artifact

    def attach(self, *, project_id: str, run_id: str, artifact_id: str) -> None:
        """Attach one immutable cataloged artifact to one project-owned run."""

        if artifact_id not in self._artifacts:
            raise SharedUnivariateArtifactError("univariate_artifact_not_found")
        reference = (project_id, run_id)
        existing_id = self._references.get(reference)
        if existing_id is not None and existing_id != artifact_id:
            raise SharedUnivariateArtifactError("univariate_artifact_reference_conflict")
        self._references[reference] = artifact_id

    def resolve(self, *, project_id: str, run_id: str) -> SharedUnivariateArtifact | None:
        """Resolve only the artifact referenced by the supplied project/run pair."""

        artifact_id = self._references.get((project_id, run_id))
        return self._artifacts.get(artifact_id) if artifact_id is not None else None


def verify_payload(artifact: SharedUnivariateArtifact, payload: bytes) -> bytes:
    """Return payload only when it matches the immutable catalog checksum."""

    if _payload_hash(payload) != artifact.content_hash:
        raise SharedUnivariateArtifactError("univariate_artifact_checksum_mismatch")
    return payload


def _payload_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
