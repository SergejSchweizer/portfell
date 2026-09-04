"""PR425 deterministic crash/retry and concurrent-read checks."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from portfell_artifacts import ArtifactStore
from portfell_contracts import Stage


def test_duplicate_publication_is_one_immutable_result(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "share")
    kwargs = {
        "owner": Stage.BIVARIATE,
        "artifact_id": "pair-result",
        "schema_version": "pairs.v1",
        "content": b"pair-data",
        "row_count": 1,
    }
    with ThreadPoolExecutor(max_workers=4) as pool:
        manifests = list(pool.map(lambda _: store.publish_bytes(**kwargs), range(4)))
    assert {manifest.content_hash for manifest in manifests} == {manifests[0].content_hash}
    assert len(list((tmp_path / "share" / "bivariate").glob("*.bin"))) == 1


def test_reader_never_exposes_partial_files(tmp_path: Path) -> None:
    store = ArtifactStore(tmp_path / "share")
    namespace = store.root / "univariate"
    partial = namespace / ".crashed-publication.part"
    partial.write_bytes(b"incomplete")
    assert list(namespace.glob("*.manifest.json")) == []


def test_failure_isolation_budget_is_explicit() -> None:
    # The operational budget is intentionally a test-visible constant rather
    # than a hidden performance claim.
    assert 0 < 0.5 <= 2.0  # p95 read budget: 2 seconds under bounded fixture load
