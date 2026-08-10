from __future__ import annotations

from portfell.shared_bivariate_artifacts import build_bivariate_manifest


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
