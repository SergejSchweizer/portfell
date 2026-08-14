from __future__ import annotations

from portfell.hosted_page_view_contracts import metadata_builder_page_view


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
