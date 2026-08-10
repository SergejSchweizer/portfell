from __future__ import annotations

import pytest

from portfell.shared_bivariate_artifacts import (
    InMemorySharedBivariateCatalog,
    SharedBivariateArtifactError,
    UnavailablePair,
    build_bivariate_manifest,
    verify_bucket_payload,
)


def test_bivariate_manifest_has_canonical_universe_pairs_and_buckets() -> None:
    manifest = build_bivariate_manifest(
        univariate_artifact_ids=("uni-c", "uni-a", "uni-b"),
        bucket_count=2,
        calendar_policy_version="calendar-v1",
        algorithm_version="algorithm-v1",
    )

    assert manifest.univariate_artifact_ids == ("uni-a", "uni-b", "uni-c")
    assert manifest.pair_count == 3
    assert tuple(sorted(pair for bucket in manifest.buckets for pair in bucket.pairs)) == (
        ("uni-a", "uni-b"),
        ("uni-a", "uni-c"),
        ("uni-b", "uni-c"),
    )
    assert (
        manifest.manifest_id
        == build_bivariate_manifest(
            univariate_artifact_ids=("uni-b", "uni-c", "uni-a"),
            bucket_count=2,
            calendar_policy_version="calendar-v1",
            algorithm_version="algorithm-v1",
        ).manifest_id
    )


def test_bivariate_manifest_rejects_pair_count_over_budget_before_planning() -> None:
    with pytest.raises(SharedBivariateArtifactError, match="bivariate_pair_budget_exceeded"):
        build_bivariate_manifest(
            univariate_artifact_ids=("uni-a", "uni-b", "uni-c"),
            bucket_count=2,
            calendar_policy_version="calendar-v1",
            algorithm_version="algorithm-v1",
            maximum_pair_count=2,
        )


def test_bucket_payload_checksum_fails_closed_on_corruption() -> None:
    payload = b'{"pairs":[["uni-a","uni-b"]]}'
    manifest = build_bivariate_manifest(
        univariate_artifact_ids=("uni-a", "uni-b"),
        bucket_count=1,
        calendar_policy_version="calendar-v1",
        algorithm_version="algorithm-v1",
        bucket_payloads={0: payload},
    )

    assert verify_bucket_payload(manifest, bucket=0, payload=payload) == payload
    with pytest.raises(SharedBivariateArtifactError, match="bivariate_bucket_checksum_mismatch"):
        verify_bucket_payload(manifest, bucket=0, payload=b"corrupt")


def test_bivariate_manifest_preserves_typed_unavailable_pair_outcomes() -> None:
    manifest = build_bivariate_manifest(
        univariate_artifact_ids=("uni-a", "uni-b", "uni-c"),
        bucket_count=2,
        calendar_policy_version="calendar-v1",
        algorithm_version="algorithm-v1",
        unavailable_pairs=(UnavailablePair("uni-c", "uni-a", "insufficient_observations"),),
    )

    assert manifest.unavailable_pairs == (
        UnavailablePair("uni-a", "uni-c", "insufficient_observations"),
    )


def test_shared_bivariate_catalog_publishes_one_immutable_manifest_per_identity() -> None:
    catalog = InMemorySharedBivariateCatalog()
    manifest = build_bivariate_manifest(
        univariate_artifact_ids=("uni-a", "uni-b"),
        bucket_count=1,
        calendar_policy_version="calendar-v1",
        algorithm_version="algorithm-v1",
    )

    assert catalog.publish(manifest) == manifest
    assert catalog.publish(manifest) == manifest
    assert catalog.manifest_count == 1
