"""Immutable tenant-neutral Multivariate artifact identity contracts."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


class SharedMultivariateArtifactError(ValueError):
    """Raised for invalid immutable Multivariate artifact identity inputs."""


@dataclass(frozen=True)
class SharedMultivariateArtifact:
    """Exact shared Multivariate artifact identity and complete dependency closure."""

    artifact_id: str
    univariate_artifact_ids: tuple[str, ...]
    bivariate_manifest_id: str
    dependency_ids: tuple[str, ...]
    settings_json: str


class InMemorySharedMultivariateArtifacts:
    """Test double for immutable publication and project-scoped artifact references."""

    def __init__(self) -> None:
        self._artifacts: dict[str, SharedMultivariateArtifact] = {}
        self._references: dict[tuple[str, str], str] = {}

    @property
    def artifact_count(self) -> int:
        return len(self._artifacts)

    def publish(self, artifact: SharedMultivariateArtifact) -> SharedMultivariateArtifact:
        """Publish or return exactly matching immutable Multivariate content."""

        existing = self._artifacts.get(artifact.artifact_id)
        if existing is not None:
            if existing != artifact:
                raise SharedMultivariateArtifactError("multivariate_artifact_id_conflict")
            return existing
        self._artifacts[artifact.artifact_id] = artifact
        return artifact

    def attach(self, *, project_id: str, run_id: str, artifact_id: str) -> None:
        """Attach one immutable cataloged artifact to one project-owned run."""

        if artifact_id not in self._artifacts:
            raise SharedMultivariateArtifactError("multivariate_artifact_not_found")
        reference = (project_id, run_id)
        existing_id = self._references.get(reference)
        if existing_id is not None and existing_id != artifact_id:
            raise SharedMultivariateArtifactError("multivariate_artifact_reference_conflict")
        self._references[reference] = artifact_id

    def resolve(self, *, project_id: str, run_id: str) -> SharedMultivariateArtifact | None:
        """Resolve only the artifact referenced by the supplied project/run pair."""

        artifact_id = self._references.get((project_id, run_id))
        return self._artifacts.get(artifact_id) if artifact_id is not None else None


def build_multivariate_artifact(
    *,
    univariate_artifact_ids: tuple[str, ...],
    bivariate_manifest_id: str,
    settings: Mapping[str, Any],
    schema_version: str,
    algorithm_version: str,
) -> SharedMultivariateArtifact:
    """Build an order-independent identity from exact analytical dependencies and settings."""

    universe = tuple(sorted(set(univariate_artifact_ids)))
    if not bivariate_manifest_id or not schema_version or not algorithm_version:
        raise SharedMultivariateArtifactError("multivariate_artifact_version_required")
    if len(universe) < 2 or not all(universe):
        raise SharedMultivariateArtifactError("multivariate_artifact_universe_invalid")
    dependencies = (bivariate_manifest_id, *universe)
    settings_json = json.dumps(dict(settings), sort_keys=True, separators=(",", ":"))
    payload = {
        "univariate_artifact_ids": universe,
        "bivariate_manifest_id": bivariate_manifest_id,
        "settings": json.loads(settings_json),
        "schema_version": schema_version,
        "algorithm_version": algorithm_version,
    }
    artifact_id = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return SharedMultivariateArtifact(
        artifact_id,
        universe,
        bivariate_manifest_id,
        dependencies,
        settings_json,
    )
