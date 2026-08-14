from __future__ import annotations

import pytest

from portfell.hosted_page_view_contracts import (
    MAX_LAZY_SECTION_BYTES,
    analytical_page_view,
    bounded_detail_section,
    decode_section_cursor,
    encode_section_cursor,
    metadata_builder_page_view,
)


def test_metadata_builder_page_view_is_versioned_compact_and_deterministic() -> None:
    criteria = {"project_id": "project-1", "selected_count": 2, "exchange": "XETRA"}
    initial_fill = {"status": "ready", "completed_units": 2, "total_units": 2}
    workflow = {"stages": {"metadata_builder": {"status": "complete"}}}

    first, first_etag = metadata_builder_page_view(
        project_id="project-1", criteria=criteria, initial_fill=initial_fill, workflow=workflow
    )
    second, second_etag = metadata_builder_page_view(
        project_id="project-1", criteria=criteria, initial_fill=initial_fill, workflow=workflow
    )

    assert first == second
    assert first_etag == second_etag
    assert first["contract_version"] == 1
    assert first["module"] == "metadata_builder"
    assert first["sections"]["criteria"]["available"] is True


def test_metadata_builder_page_view_marks_missing_initial_fill_as_unavailable() -> None:
    page_view, _ = metadata_builder_page_view(
        project_id="project-1",
        criteria={"project_id": "project-1"},
        initial_fill=None,
        workflow={"stages": {}},
    )

    assert page_view["summary"]["initial_fill"] is None
    assert page_view["sections"]["initial_fill"] == {
        "available": False,
        "unavailable": {"code": "initial_fill_not_found"},
    }


@pytest.mark.parametrize(
    ("module", "section"),
    (
        ("univariate_statistics", "results"),
        ("bivariate_statistics", "correlation_matrix"),
        ("multivariate_statistics", "performance"),
    ),
)
def test_analytical_page_view_defers_large_sections_until_the_stage_completes(
    module: str, section: str
) -> None:
    workflow = {
        "projection_etag": "workflow-revision",
        "stages": {module: {"status": "running"}},
    }

    page_view, etag = analytical_page_view(
        module=module, project_id="project-1", workflow=workflow
    )

    assert page_view["contract_version"] == 1
    assert page_view["workflow_etag"] == "workflow-revision"
    assert page_view["sections"][section] == {
        "available": False,
        "revision": page_view["sections"][section]["revision"],
        "unavailable": {"code": "stage_not_complete", "status": "running"},
    }
    assert etag


def test_analytical_page_view_exposes_section_revisions_after_completion() -> None:
    workflow = {
        "projection_etag": "workflow-revision",
        "stages": {"bivariate_statistics": {"status": "complete", "bivariate_run_id": "run-1"}},
    }

    page_view, _ = analytical_page_view(
        module="bivariate_statistics", project_id="project-1", workflow=workflow
    )

    assert page_view["run_id"] == "run-1"
    assert all(section["available"] is True for section in page_view["sections"].values())


def test_section_cursor_is_opaque_and_bound_to_one_revision() -> None:
    cursor = encode_section_cursor(revision="revision-1", offset=200)

    assert decode_section_cursor(cursor=cursor, revision="revision-1") == 200
    with pytest.raises(ValueError, match="section_revision_mismatch"):
        decode_section_cursor(cursor=cursor, revision="revision-2")
    with pytest.raises(ValueError, match="section_cursor_invalid"):
        decode_section_cursor(cursor="not a cursor", revision="revision-1")


def test_detail_section_retains_its_payload_or_rejects_an_indivisible_oversize_value() -> None:
    result = bounded_detail_section(revision="revision-1", payload={"pair_count": 3})

    assert result == {"revision": "revision-1", "data": {"pair_count": 3}}
    with pytest.raises(ValueError, match="section_too_large"):
        bounded_detail_section(
            revision="revision-1", payload={"values": "x" * MAX_LAZY_SECTION_BYTES}
        )
