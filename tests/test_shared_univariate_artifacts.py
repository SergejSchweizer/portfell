from __future__ import annotations

from portfell.shared_univariate_artifacts import (
    InMemorySharedUnivariateArtifacts,
    SharedUnivariateArtifact,
)


def test_equal_univariate_artifact_is_shared_with_separate_project_run_references() -> None:
    store = InMemorySharedUnivariateArtifacts()
    artifact = SharedUnivariateArtifact("artifact-1", "return-1", "content-1")

    assert store.publish(artifact) == artifact
    assert store.publish(artifact) == artifact
    store.attach(project_id="project-a", run_id="run-a", artifact_id="artifact-1")
    store.attach(project_id="project-b", run_id="run-b", artifact_id="artifact-1")

    assert store.resolve(project_id="project-a", run_id="run-a") == artifact
    assert store.resolve(project_id="project-b", run_id="run-b") == artifact
    assert store.artifact_count == 1


def test_project_run_reference_cannot_be_rebound_to_another_artifact() -> None:
    store = InMemorySharedUnivariateArtifacts()
    store.publish(SharedUnivariateArtifact("artifact-1", "return-1", "content-1"))
    store.publish(SharedUnivariateArtifact("artifact-2", "return-2", "content-2"))
    store.attach(project_id="project-a", run_id="run-a", artifact_id="artifact-1")

    try:
        store.attach(project_id="project-a", run_id="run-a", artifact_id="artifact-2")
    except ValueError as error:
        assert str(error) == "univariate_artifact_reference_conflict"
    else:
        raise AssertionError("expected immutable project run reference")
