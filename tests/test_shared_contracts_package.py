"""PR408 contract tests: pure imports, strict validation and stable documents."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from portfell_contracts import (
    ArtifactManifest,
    ArtifactStatus,
    BivariateRunId,
    JobProgress,
    JobStatus,
    MetadataUniverseId,
    MultivariateRunId,
    PublicError,
    Stage,
    UnivariateRunId,
    UnivariateSelectionId,
    WorkflowProjection,
)


def test_ids_are_distinct_to_static_type_checkers() -> None:
    # NewType values intentionally have the same runtime representation as
    # their wire value; the distinct constructors are what strict Pyright
    # uses to prevent accidental ID interchange.
    assert MetadataUniverseId.__supertype__ is str  # type: ignore[attr-defined]
    assert MetadataUniverseId is not UnivariateRunId
    assert UnivariateSelectionId is not BivariateRunId
    assert MultivariateRunId("v-1") == "v-1"


def test_manifest_serialization_is_deterministic_and_json_safe() -> None:
    manifest = ArtifactManifest(
        artifact_id="a-1",
        owner=Stage.UNIVARIATE,
        schema_version="univariate.metrics.v1",
        content_hash="sha256:abc",
        relative_path="univariate/a-1.parquet",
        byte_size=12,
        row_count=3,
    )
    document = manifest.to_document()
    assert json.dumps(document, sort_keys=True) == json.dumps(
        manifest.to_document(), sort_keys=True
    )
    assert document["owner"] == "univariate"


def test_progress_allows_unknown_total_for_running_jobs() -> None:
    progress = JobProgress(Stage.BIVARIATE, JobStatus.RUNNING, "pairing", current=2)
    assert progress.to_document()["total"] is None


def test_projection_contains_only_ids_counts_and_status() -> None:
    projection = WorkflowProjection(
        metadata_universe_id=MetadataUniverseId("m-1"),
        univariate_run_id=UnivariateRunId("u-1"),
        bivariate_run_id=BivariateRunId("b-1"),
        multivariate_run_id=MultivariateRunId("v-1"),
        metadata_count=10,
        univariate_count=4,
        bivariate_candidate_pairs=6,
        status=JobStatus.SUCCEEDED,
    )
    assert set(projection.to_document()) == {
        "bivariate_candidate_pairs",
        "bivariate_run_id",
        "contract_version",
        "metadata_count",
        "metadata_universe_id",
        "multivariate_run_id",
        "status",
        "univariate_count",
        "univariate_run_id",
        "univariate_selection_id",
    }


@pytest.mark.parametrize(
    "factory",
    [
        lambda: ArtifactManifest("a", Stage.METADATA, "v1", "h", "../escape", 0, 0),
        lambda: ArtifactManifest(
            "a", Stage.METADATA, "v2", "h", "metadata/a", 0, 0, contract_version="2"
        ),
        lambda: JobProgress(Stage.METADATA, JobStatus.RUNNING, "x", current=3, total=2),
        lambda: PublicError("bad", "oops", (("password", "secret"),)),
        lambda: WorkflowProjection(metadata_count=-1),
    ],
)
def test_malformed_contracts_fail_closed(factory: object) -> None:
    with pytest.raises(ValueError):
        factory()  # type: ignore[operator]


def test_package_has_no_forbidden_runtime_imports() -> None:
    root = Path(__file__).parents[1] / "src" / "portfell_contracts"
    forbidden = {"dash", "fastapi", "numpy", "polars", "psycopg", "sqlalchemy"}
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text())
        imported = {
            node.names[0].name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
        }
        imported.update(
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        )
        assert not imported & forbidden


def test_public_error_rejects_nested_sensitive_key() -> None:
    with pytest.raises(ValueError):
        PublicError("failed", "safe", (("access_token_value", "x"),))


def test_status_enums_are_stable_strings() -> None:
    assert [item.value for item in ArtifactStatus] == ["staged", "published", "invalid"]
    assert [item.value for item in Stage] == [
        "gateway",
        "metadata",
        "univariate",
        "bivariate",
        "multivariate",
    ]
