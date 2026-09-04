"""PR410 artifact publication, verification and isolation tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from portfell_artifacts import ArtifactIdentityConflict, ArtifactStore, ArtifactStoreError
from portfell_contracts import Stage


def test_publish_and_read_verifies_manifest(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "share")
    manifest = store.publish_bytes(
        owner=Stage.UNIVARIATE,
        artifact_id="run-1",
        schema_version="metrics.v1",
        content=b"isin,value\nAAA,1\n",
        row_count=1,
    )
    assert manifest.relative_path == "univariate/run-1.bin"
    assert store.read(owner=Stage.UNIVARIATE, artifact_id="run-1") == manifest
    assert list((tmp_path / "share" / "univariate").glob("*.part")) == []


def test_identical_publication_is_idempotent_and_different_bytes_conflict(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "share")
    kwargs = dict(
        owner=Stage.BIVARIATE,
        artifact_id="pair-1",
        schema_version="pairs.v1",
        content=b"same",
        row_count=1,
    )
    first = store.publish_bytes(**kwargs)
    assert store.publish_bytes(**kwargs).content_hash == first.content_hash
    with pytest.raises(ArtifactIdentityConflict, match="artifact_identity_conflict"):
        store.publish_bytes(**{**kwargs, "content": b"different"})


def test_wrong_owner_corruption_and_path_escape_fail_closed(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "share")
    store.publish_bytes(
        owner=Stage.METADATA,
        artifact_id="universe-1",
        schema_version="universe.v1",
        content=b"abc",
        row_count=1,
    )
    with pytest.raises(ArtifactStoreError, match="artifact_not_published"):
        store.read(owner=Stage.UNIVARIATE, artifact_id="universe-1")
    with pytest.raises(ArtifactStoreError, match="artifact_id_invalid"):
        store.publish_bytes(
            owner=Stage.METADATA,
            artifact_id="../escape",
            schema_version="v1",
            content=b"x",
            row_count=0,
        )
    (tmp_path / "share" / "market" / "universe-1.bin").write_bytes(b"xyz")
    with pytest.raises(ArtifactStoreError, match="artifact_hash_mismatch"):
        store.read(owner=Stage.METADATA, artifact_id="universe-1")


def test_manifest_unknown_version_or_status_is_rejected(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "share")
    store.publish_bytes(
        owner=Stage.MULTIVARIATE,
        artifact_id="portfolio-1",
        schema_version="portfolio.v1",
        content=b"x",
        row_count=0,
    )
    path = tmp_path / "share" / "multivariate" / "portfolio-1.manifest.json"
    document = json.loads(path.read_text())
    document["contract_version"] = "99"
    path.write_text(json.dumps(document))
    with pytest.raises(ArtifactStoreError, match="artifact_manifest_invalid"):
        store.read(owner=Stage.MULTIVARIATE, artifact_id="portfolio-1")


def test_gateway_cannot_publish_and_only_final_namespaces_are_created(tmp_path: Path) -> None:
    store_root = tmp_path / "share"
    store = ArtifactStore(store_root)
    assert {path.name for path in store_root.iterdir()} == {
        "market",
        "univariate",
        "bivariate",
        "multivariate",
    }
    with pytest.raises(ArtifactStoreError, match="gateway_cannot_publish_artifacts"):
        store.publish_bytes(
            owner=Stage.GATEWAY,
            artifact_id="x",
            schema_version="v1",
            content=b"x",
            row_count=0,
        )
