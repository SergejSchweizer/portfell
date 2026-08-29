from __future__ import annotations

from portfell.workflow_state import resolve_workflow


def test_workflow_transitions_in_order_with_immutable_identifiers() -> None:
    initial = resolve_workflow(
        metadata_revision_id=None,
        metadata_selection_id=None,
        quote_run_id=None,
    )
    selected = resolve_workflow(
        metadata_revision_id="metadata-revision-1",
        metadata_selection_id="metadata-selection-1",
        quote_run_id=None,
    )
    quoted = resolve_workflow(
        metadata_revision_id="metadata-revision-1",
        metadata_selection_id="metadata-selection-1",
        quote_run_id="quote-run-1",
    )
    completed = resolve_workflow(
        metadata_revision_id="metadata-revision-1",
        metadata_selection_id="metadata-selection-1",
        quote_run_id="quote-run-1",
        univariate_run_id="univariate-run-1",
        univariate_selection_id="univariate-selection-1",
    )

    assert initial == {
        "metadata_builder": {"status": "ready"},
        "univariate_statistics": {"status": "locked"},
        "bivariate_statistics": {"status": "locked"},
        "multivariate_statistics": {"status": "locked"},
    }
    assert selected["metadata_builder"] == {
        "status": "complete",
        "metadata_revision_id": "metadata-revision-1",
        "metadata_selection_id": "metadata-selection-1",
    }
    assert selected["univariate_statistics"] == {"status": "ready"}
    assert quoted["metadata_builder"] == {
        "status": "complete",
        "metadata_revision_id": "metadata-revision-1",
        "metadata_selection_id": "metadata-selection-1",
        "quote_run_id": "quote-run-1",
    }
    assert quoted["univariate_statistics"] == {"status": "ready"}
    assert completed["univariate_statistics"]["univariate_selection_id"] == (
        "univariate-selection-1"
    )
    assert completed["bivariate_statistics"] == {"status": "ready"}
    assert completed["multivariate_statistics"] == {"status": "locked"}


def test_multivariate_statistics_unlocks_only_after_bivariate_completion() -> None:
    running = resolve_workflow(
        metadata_revision_id="metadata-revision-1",
        metadata_selection_id="metadata-selection-1",
        quote_run_id="quote-run-1",
        univariate_run_id="univariate-run-1",
        univariate_selection_id="univariate-selection-1",
        bivariate_run_id="bivariate-run-1",
        bivariate_status="running",
    )
    complete = resolve_workflow(
        metadata_revision_id="metadata-revision-1",
        metadata_selection_id="metadata-selection-1",
        quote_run_id="quote-run-1",
        univariate_run_id="univariate-run-1",
        univariate_selection_id="univariate-selection-1",
        bivariate_run_id="bivariate-run-1",
        bivariate_status="complete",
    )

    assert running["bivariate_statistics"]["status"] == "running"
    assert running["multivariate_statistics"] == {"status": "locked"}
    assert complete["multivariate_statistics"] == {
        "status": "ready",
        "metadata_revision_id": "metadata-revision-1",
        "metadata_selection_id": "metadata-selection-1",
        "quote_run_id": "quote-run-1",
        "univariate_run_id": "univariate-run-1",
        "univariate_selection_id": "univariate-selection-1",
        "bivariate_run_id": "bivariate-run-1",
    }


def test_shared_market_workflow_does_not_require_a_legacy_quote_run() -> None:
    resolved = resolve_workflow(
        metadata_revision_id="shared-market",
        metadata_selection_id="metadata-selection-1",
        quote_run_id=None,
        univariate_run_id="univariate-run-1",
        univariate_selection_id="univariate-selection-1",
        bivariate_run_id="bivariate-run-1",
        bivariate_status="complete",
    )

    assert resolved["univariate_statistics"] == {
        "status": "complete",
        "metadata_revision_id": "shared-market",
        "metadata_selection_id": "metadata-selection-1",
        "univariate_run_id": "univariate-run-1",
        "univariate_selection_id": "univariate-selection-1",
    }
    assert resolved["bivariate_statistics"]["status"] == "complete"
    assert "quote_run_id" not in resolved["bivariate_statistics"]
    assert resolved["multivariate_statistics"]["status"] == "ready"
