from __future__ import annotations

import pytest

from portfell.shared_univariate_artifacts import (
    InMemorySharedUnivariateArtifacts,
    SharedUnivariateArtifact,
    SharedUnivariateArtifactError,
    verify_payload,
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


def test_payload_verification_fails_closed_when_checksum_differs() -> None:
    payload = b'{"listing":"IE1:XETRA:AAA","status":"unavailable"}'
    artifact = SharedUnivariateArtifact.from_payload("artifact-1", "return-1", payload)

    assert verify_payload(artifact, payload) == payload
    try:
        verify_payload(artifact, b"corrupt")
    except SharedUnivariateArtifactError as error:
        assert str(error) == "univariate_artifact_checksum_mismatch"
    else:
        raise AssertionError("expected checksum mismatch")


def test_univariate_shared_artifact_rejects_invalid_publication_and_references() -> None:
    with pytest.raises(
        SharedUnivariateArtifactError, match="univariate_artifact_identity_required"
    ):
        SharedUnivariateArtifact("", "returns-1", "hash")
    with pytest.raises(SharedUnivariateArtifactError, match="univariate_artifact_payload_required"):
        SharedUnivariateArtifact.from_payload("artifact-1", "returns-1", b"")
    store = InMemorySharedUnivariateArtifacts()
    assert store.resolve(project_id="project-1", run_id="missing") is None
    first = SharedUnivariateArtifact.from_payload("artifact-1", "returns-1", b"payload")
    second = SharedUnivariateArtifact.from_payload("artifact-2", "returns-2", b"other")
    store.publish(first)
    store.publish(second)
    with pytest.raises(SharedUnivariateArtifactError, match="univariate_artifact_id_conflict"):
        store.publish(SharedUnivariateArtifact.from_payload("artifact-1", "returns-1", b"changed"))
    with pytest.raises(SharedUnivariateArtifactError, match="univariate_artifact_not_found"):
        store.attach(project_id="project-1", run_id="run-1", artifact_id="missing")
    store.attach(project_id="project-1", run_id="run-1", artifact_id="artifact-1")
    with pytest.raises(
        SharedUnivariateArtifactError, match="univariate_artifact_reference_conflict"
    ):
        store.attach(project_id="project-1", run_id="run-1", artifact_id="artifact-2")
