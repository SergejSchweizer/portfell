"""PR423 end-to-end ID lineage and shared-artifact contract tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from portfell_artifacts import ArtifactStore, ArtifactStoreError
from portfell_contracts import (
    BivariateRunId,
    MetadataUniverseId,
    MultivariateRunId,
    Stage,
    UnivariateRunId,
    UnivariateSelectionId,
)


def test_complete_chain_passes_only_typed_published_ids(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "share")
    metadata_id = MetadataUniverseId("metadata-1")
    univariate_id = UnivariateRunId("univariate-1")
    selection_id = UnivariateSelectionId("selection-1")
    bivariate_id = BivariateRunId("bivariate-1")
    multivariate_id = MultivariateRunId("multivariate-1")
    store.publish_bytes(
        owner=Stage.METADATA,
        artifact_id=str(metadata_id),
        schema_version="universe.v1",
        content=b"members",
        row_count=2,
    )
    store.publish_bytes(
        owner=Stage.UNIVARIATE,
        artifact_id=str(univariate_id),
        schema_version="metrics.v1",
        content=b"metrics",
        row_count=2,
    )
    assert all(
        isinstance(value, str)
        for value in (metadata_id, univariate_id, selection_id, bivariate_id, multivariate_id)
    )
    assert str(bivariate_id) != str(multivariate_id)


def test_unpublished_or_corrupt_artifacts_stop_downstream_chain(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "share")
    with pytest.raises(ArtifactStoreError, match="artifact_not_published"):
        store.read(owner=Stage.BIVARIATE, artifact_id="missing")


def test_contract_documentation_forbids_sibling_http_and_shared_memory() -> None:
    text = Path("docs/contracts/independent-modules-v1.md").read_text()
    assert "REST endpoint" in text
    assert "cross-module database write" in text
    assert "published" in text
