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


def build_bivariate_manifest(
    *,
    univariate_artifact_ids: tuple[str, ...],
    bucket_count: int,
    calendar_policy_version: str,
    algorithm_version: str,
) -> BivariateManifest:
    """Build an order-independent immutable Bivariate manifest without pair rows in a catalog."""

    if bucket_count < 1:
        raise SharedBivariateArtifactError("bivariate_bucket_count_invalid")
    universe = tuple(sorted(set(univariate_artifact_ids)))
    if len(universe) < 2 or not all(universe):
        raise SharedBivariateArtifactError("bivariate_universe_invalid")
    if not calendar_policy_version or not algorithm_version:
        raise SharedBivariateArtifactError("bivariate_version_required")
    grouped: dict[int, list[tuple[str, str]]] = {}
    for pair in combinations(universe, 2):
        grouped.setdefault(_bucket(pair, bucket_count), []).append(pair)
    buckets = tuple(
        BivariateBucket(bucket, tuple(sorted(pairs))) for bucket, pairs in sorted(grouped.items())
    )
    payload = {
        "univariate_artifact_ids": universe,
        "bucket_count": bucket_count,
        "calendar_policy_version": calendar_policy_version,
        "algorithm_version": algorithm_version,
        "buckets": [(bucket.bucket, bucket.pairs) for bucket in buckets],
    }
    manifest_id = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return BivariateManifest(
        manifest_id,
        universe,
        sum(len(bucket.pairs) for bucket in buckets),
        buckets,
    )


def _bucket(pair: tuple[str, str], bucket_count: int) -> int:
    digest = hashlib.sha256(":".join(pair).encode()).hexdigest()
    return int(digest[:16], 16) % bucket_count
