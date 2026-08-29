from __future__ import annotations

import pytest

from portfell.shared_multivariate_artifacts import (
    InMemorySharedMultivariateArtifacts,
    SharedMultivariateArtifactError,
    build_multivariate_artifact,
)


def test_multivariate_artifact_identity_is_canonical_and_dependency_pinned() -> None:
    artifact = build_multivariate_artifact(
        univariate_artifact_ids=("uni-b", "uni-a"),
        bivariate_manifest_id="bi-1",
        settings={"solver": "minimum_cvar", "confidence": 0.95},
        schema_version="schema-v1",
        algorithm_version="algorithm-v1",
    )

    assert artifact.univariate_artifact_ids == ("uni-a", "uni-b")
    assert artifact.dependency_ids == ("bi-1", "uni-a", "uni-b")
    assert (
        artifact.artifact_id
        == build_multivariate_artifact(
            univariate_artifact_ids=("uni-a", "uni-b"),
            bivariate_manifest_id="bi-1",
            settings={"confidence": 0.95, "solver": "minimum_cvar"},
            schema_version="schema-v1",
            algorithm_version="algorithm-v1",
        ).artifact_id
    )


def test_multivariate_artifact_identity_changes_with_pinned_dependency_or_settings() -> None:
    first = build_multivariate_artifact(
        univariate_artifact_ids=("uni-a", "uni-b"),
        bivariate_manifest_id="bi-1",
        settings={"solver": "hrp"},
        schema_version="schema-v1",
        algorithm_version="algorithm-v1",
    )
    changed = build_multivariate_artifact(
        univariate_artifact_ids=("uni-a", "uni-b"),
        bivariate_manifest_id="bi-2",
        settings={"solver": "hrp"},
        schema_version="schema-v1",
        algorithm_version="algorithm-v1",
    )

    assert changed.artifact_id != first.artifact_id


def test_multivariate_artifacts_publish_immutably_and_resolve_by_owned_run() -> None:
    catalog = InMemorySharedMultivariateArtifacts()
    artifact = build_multivariate_artifact(
        univariate_artifact_ids=("uni-a", "uni-b"),
        bivariate_manifest_id="bi-1",
        settings={"solver": "hrp"},
        schema_version="schema-v1",
        algorithm_version="algorithm-v1",
    )

    assert catalog.publish(artifact) == artifact
    catalog.attach(project_id="project-1", run_id="run-1", artifact_id=artifact.artifact_id)
    assert catalog.resolve(project_id="project-1", run_id="run-1") == artifact
    assert catalog.resolve(project_id="project-2", run_id="run-1") is None

    conflicting = build_multivariate_artifact(
        univariate_artifact_ids=("uni-a", "uni-b"),
        bivariate_manifest_id="bi-2",
        settings={"solver": "hrp"},
        schema_version="schema-v1",
        algorithm_version="algorithm-v1",
    )
    conflicting = type(conflicting)(
        artifact.artifact_id,
        conflicting.univariate_artifact_ids,
        conflicting.bivariate_manifest_id,
        conflicting.dependency_ids,
        conflicting.settings_json,
    )
    with pytest.raises(SharedMultivariateArtifactError, match="multivariate_artifact_id_conflict"):
        catalog.publish(conflicting)
