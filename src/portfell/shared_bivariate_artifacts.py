"""Deterministic tenant-neutral bucketed Bivariate manifest contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from itertools import combinations


class SharedBivariateArtifactError(ValueError):
    """Raised for stable Bivariate manifest planning errors."""


@dataclass(frozen=True)
class BivariateBucket:
    """One deterministic payload bucket containing lexicographically sorted pairs."""

    bucket: int
    pairs: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class BivariateManifest:
    """Tenant-neutral top-level manifest for a bounded bucketed Bivariate run."""

    manifest_id: str
    univariate_artifact_ids: tuple[str, ...]
    pair_count: int
    buckets: tuple[BivariateBucket, ...]
    bucket_payload_hashes: tuple[tuple[int, str], ...]


def build_bivariate_manifest(
    *,
    univariate_artifact_ids: tuple[str, ...],
    bucket_count: int,
    calendar_policy_version: str,
    algorithm_version: str,
    maximum_pair_count: int = 100_000,
    bucket_payloads: dict[int, bytes] | None = None,
) -> BivariateManifest:
    """Build an order-independent immutable Bivariate manifest without pair rows in a catalog."""

    if bucket_count < 1:
        raise SharedBivariateArtifactError("bivariate_bucket_count_invalid")
    universe = tuple(sorted(set(univariate_artifact_ids)))
    if len(universe) < 2 or not all(universe):
        raise SharedBivariateArtifactError("bivariate_universe_invalid")
    pair_count = len(universe) * (len(universe) - 1) // 2
    if maximum_pair_count < 1 or pair_count > maximum_pair_count:
        raise SharedBivariateArtifactError("bivariate_pair_budget_exceeded")
    if not calendar_policy_version or not algorithm_version:
        raise SharedBivariateArtifactError("bivariate_version_required")
    grouped: dict[int, list[tuple[str, str]]] = {}
    for pair in combinations(universe, 2):
        grouped.setdefault(_bucket(pair, bucket_count), []).append(pair)
    buckets = tuple(
        BivariateBucket(bucket, tuple(sorted(pairs))) for bucket, pairs in sorted(grouped.items())
    )
    payloads = bucket_payloads or {}
    expected_buckets = {bucket.bucket for bucket in buckets}
    if set(payloads).difference(expected_buckets):
        raise SharedBivariateArtifactError("bivariate_bucket_payload_invalid")
    bucket_payload_hashes = tuple(
        (bucket.bucket, _payload_hash(payloads[bucket.bucket]))
        for bucket in buckets
        if bucket.bucket in payloads
    )
    payload = {
        "univariate_artifact_ids": universe,
        "bucket_count": bucket_count,
        "calendar_policy_version": calendar_policy_version,
        "algorithm_version": algorithm_version,
        "buckets": [(bucket.bucket, bucket.pairs) for bucket in buckets],
        "bucket_payload_hashes": bucket_payload_hashes,
    }
    manifest_id = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return BivariateManifest(
        manifest_id,
        universe,
        pair_count,
        buckets,
        bucket_payload_hashes,
    )


def _bucket(pair: tuple[str, str], bucket_count: int) -> int:
    digest = hashlib.sha256(":".join(pair).encode()).hexdigest()
    return int(digest[:16], 16) % bucket_count


def verify_bucket_payload(manifest: BivariateManifest, *, bucket: int, payload: bytes) -> bytes:
    """Return a bucket only when its checksum is present and matches the manifest."""

    expected_hash = dict(manifest.bucket_payload_hashes).get(bucket)
    if expected_hash is None:
        raise SharedBivariateArtifactError("bivariate_bucket_not_cataloged")
    if _payload_hash(payload) != expected_hash:
        raise SharedBivariateArtifactError("bivariate_bucket_checksum_mismatch")
    return payload


def _payload_hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
