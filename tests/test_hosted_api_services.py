from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import portfell.hosted_api as hosted_api
import portfell.hosted_api_local_runtime as local_runtime_module
from portfell.entitlements import ProviderDownloadRun
from portfell.hosted_api_errors import HostedApplicationError, HostedRuntimeError
from portfell.hosted_api_local_runtime import LocalHostedRuntime
from portfell.hosted_api_service_support import (
    current_project,
    idempotent_response,
    opaque_id,
    page,
    project_context_row,
    project_data_loaded,
    remember_idempotency,
    require_user_row,
    selection_for_project,
    set_current_project,
    stable_hash,
    workflow_row,
)
from portfell.hosted_api_state import (
    HostedApiState,
    LocalWorkspaceUserProvider,
    ProjectRecord,
    SelectionRecord,
)
from portfell.hosted_credential_project_service import CredentialProjectService
from portfell.hosted_quote_run_service import QuoteRunService
from portfell.hosted_research_workflow import FilterSelection, ResearchRun
from portfell.hosted_workspace import LocalWorkspaceStore
from portfell.hosted_workspace_repository import persist_local_workspace, restore_local_workspace
from portfell.paths import LakePaths
from portfell.selection_filters import Predicate
from portfell.table_io import JsonRow

INVALID_WORKSPACE_PAYLOADS: tuple[dict[str, object], ...] = (
    {"projects": {}},
    {"projects": ["invalid"]},
    {"projects": [{"project_id": "", "user_id": "user-a", "name": "Name"}]},
    {"selections": ["invalid"]},
    {
        "selections": [
            {
                "selection_id": "selection-1",
                "user_id": "user-a",
                "project_id": "project-1",
                "name": "Name",
                "member_ids": {},
            }
        ]
    },
    {
        "selections": [
            {
                "selection_id": "selection-1",
                "user_id": "user-a",
                "project_id": "project-1",
                "name": "Name",
                "member_ids": [1],
            }
        ]
    },
    {"current_project_id_by_user": []},
    {"current_project_id_by_user": {"user-a": 1}},
)


def _empty_workflow(**_kwargs: Any) -> dict[str, Any]:
    return {}


def _permission_denied_workflow(**_kwargs: Any) -> dict[str, Any]:
    raise PermissionError("lake is read-only")


def _discard_progress(_completed: int, _total: int, _skipped: int) -> None:
    return None


def _one_isin_row(_path: Path) -> list[JsonRow]:
    return [{"isin": "IE1"}]


def test_workspace_repository_round_trips_durable_state(tmp_path: Path) -> None:
    store = LocalWorkspaceStore(tmp_path / "workspace.json")
    state = HostedApiState(workspace_store=store)
    state.projects_by_id["project-1"] = ProjectRecord("project-1", "user-a", "Income")
    state.selections_by_id["selection-1"] = SelectionRecord(
        "selection-1", "user-a", "project-1", "UCITS", ("IE1", "IE2")
    )
    state.current_project_id_by_user["user-a"] = "project-1"
    state.current_metadata_selection_by_user["user-a"] = "selection-1"
    state.metadata_revisions_by_user["user-a"] = "revision-1"
    quote_run = ProviderDownloadRun(
        "quote-run-1", "user-a", "credential-1", "eodhd", "succeeded", ("IE1",), "hash-1"
    )
    state.downloads_by_id[quote_run.download_run_id] = quote_run
    state.download_summaries_by_id[quote_run.download_run_id] = {
        "total": 1,
        "completed": 1,
        "failed": 0,
        "percent": 100,
    }
    state.quote_rows_by_run_id[quote_run.download_run_id] = (
        {"isin": "IE1", "exchange": "XETRA", "code": "AAA", "date": "2026-08-08"},
    )
    univariate = ResearchRun(
        "univariate-1",
        "user-a",
        "source-1",
        "complete",
        ({"isin": "IE1", "distribution_frequency": "annual"},),
        1,
        1,
    )
    state.univariate_runs_by_id[univariate.run_id] = univariate
    state.quote_run_by_univariate_run_id[univariate.run_id] = quote_run.download_run_id
    remember_idempotency(state, "user-a", "fetch-all-quotes:project-1", "request-1", "quote-run-1")

    persist_local_workspace(state)
    restored = HostedApiState()
    restore_local_workspace(restored, store.load())

    assert restored.projects_by_id == state.projects_by_id
    assert restored.selections_by_id == state.selections_by_id
    assert restored.current_project_id_by_user == {"user-a": "project-1"}
    assert restored.current_metadata_selection_by_user == {"user-a": "selection-1"}
    assert restored.metadata_revisions_by_user == {"user-a": "revision-1"}
    assert restored.downloads_by_id == state.downloads_by_id
    assert restored.download_summaries_by_id == state.download_summaries_by_id
    assert restored.quote_rows_by_run_id == state.quote_rows_by_run_id
    assert restored.univariate_runs_by_id == state.univariate_runs_by_id
    assert restored.quote_run_by_univariate_run_id == state.quote_run_by_univariate_run_id
    assert restored.idempotency_refs == state.idempotency_refs
    assert json.loads((tmp_path / "workspace.json").read_text(encoding="utf-8"))["projects"]


def test_workspace_restore_marks_interrupted_quote_runs_retryable(tmp_path: Path) -> None:
    store = LocalWorkspaceStore(tmp_path / "workspace.json")
    state = HostedApiState(workspace_store=store)
    run = ProviderDownloadRun(
        "quote-run-1", "user-a", "credential-1", "eodhd", "running", ("IE1",), "hash-1"
    )
    state.downloads_by_id[run.download_run_id] = run
    state.download_summaries_by_id[run.download_run_id] = {"total": 10, "completed": 4}
    persist_local_workspace(state)

    restored = HostedApiState()
    restore_local_workspace(restored, store.load())

    assert restored.downloads_by_id[run.download_run_id].status == "failed"
    assert (
        restored.download_summaries_by_id[run.download_run_id]["error_code"]
        == "quote_run_interrupted_by_restart"
    )


def test_local_workspace_principal_rejects_blank_user_id() -> None:
    with pytest.raises(ValueError, match="user id is required"):
        LocalWorkspaceUserProvider(" ")


def test_local_runtime_validates_metadata_manifests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PORTFELL_LAKE_ROOT", str(tmp_path))
    runtime = LocalHostedRuntime(
        quote_workflow=_empty_workflow,
        metadata_workflow=_empty_workflow,
        cpu_count=lambda: 1,
    )
    manifest = LakePaths(root=tmp_path).metadata_filter_manifest("selection-1")

    assert runtime.metadata_filter_predicates("selection-1") == ()
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('{"predicates": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="manifest is invalid"):
        runtime.metadata_filter_predicates("selection-1")
    manifest.write_text('{"predicates": [1]}', encoding="utf-8")
    with pytest.raises(ValueError, match="manifest is invalid"):
        runtime.metadata_filter_predicates("selection-1")
    manifest.write_text('{"predicates": ["country=DE"]}', encoding="utf-8")
    assert runtime.metadata_filter_predicates("selection-1") == (Predicate("country", "=", "DE"),)

    monkeypatch.setattr(local_runtime_module, "read_rows", _one_isin_row)
    assert runtime.all_isins_rows() == ({"isin": "IE1"},)


def test_local_runtime_reports_metadata_lake_permission_errors() -> None:
    runtime = LocalHostedRuntime(
        quote_workflow=_empty_workflow,
        metadata_workflow=_permission_denied_workflow,
        cpu_count=lambda: 1,
    )

    with pytest.raises(HostedRuntimeError, match="lake_write_permission_denied"):
        runtime.run_metadata(provider_key="secret", on_progress=_discard_progress)


def test_quote_fetch_compatibility_hook_delegates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, str]] = []

    def fake_run_quote_fetch(
        _service: object,
        run: ProviderDownloadRun,
        selection_id: str,
        provider_key: str,
    ) -> None:
        calls.append((run.download_run_id, selection_id, provider_key))

    monkeypatch.setattr(hosted_api.QuoteRunService, "run_quote_fetch", fake_run_quote_fetch)
    run = ProviderDownloadRun("run-1", "user-a", "credential-1", "eodhd", "running", (), "hash-1")

    hosted_api._run_quote_fetch(HostedApiState(), run, "selection-1", "secret")

    assert calls == [("run-1", "selection-1", "secret")]


@pytest.mark.parametrize(
    "payload",
    INVALID_WORKSPACE_PAYLOADS,
)
def test_workspace_repository_rejects_invalid_payloads(payload: dict[str, object]) -> None:
    with pytest.raises(ValueError, match="local workspace"):
        restore_local_workspace(HostedApiState(), payload)


def test_service_support_enforces_scope_paging_and_idempotency() -> None:
    state = HostedApiState()
    project = ProjectRecord("project-1", "user-a", "Income")
    state.projects_by_id[project.project_id] = project

    assert require_user_row(state.projects_by_id, "project-1", "user-a") == project
    with pytest.raises(HostedApplicationError, match="not_found"):
        require_user_row(state.projects_by_id, "project-1", "user-b")
    assert page([{"value": 1}, {"value": 2}], limit=1, offset=1) == [{"value": 2}]
    with pytest.raises(HostedApplicationError, match="invalid_limit"):
        page([], limit=0, offset=0)
    with pytest.raises(HostedApplicationError, match="invalid_offset"):
        page([], limit=1, offset=-1)

    assert (
        idempotent_response(state, user_id="user-a", operation="create", idempotency_key=None)
        is None
    )
    remember_idempotency(state, "user-a", "create", None, "project-1")
    remember_idempotency(state, "user-a", "create", "request-1", "project-1")
    assert (
        idempotent_response(
            state, user_id="user-a", operation="create", idempotency_key="request-1"
        )
        == "project-1"
    )


def test_services_fail_closed_without_credentials_or_quote_selection() -> None:
    state = HostedApiState()
    credentials = CredentialProjectService(state)
    runtime = LocalHostedRuntime(
        quote_workflow=_empty_workflow,
        metadata_workflow=_empty_workflow,
        cpu_count=lambda: 1,
    )

    with pytest.raises(HostedApplicationError, match="credential_not_found"):
        credentials.credential_status("user-a")
    with pytest.raises(HostedApplicationError, match="credential_not_found"):
        credentials.credential_value("user-a")
    with pytest.raises(HostedApplicationError, match="metadata_selection_required"):
        QuoteRunService(state, runtime).start(
            "user-a", project_id=None, selection_id=None, idempotency_key=None
        )


def test_quote_run_reuses_an_active_run_without_an_idempotency_key() -> None:
    state = HostedApiState()
    state.projects_by_id["project-1"] = ProjectRecord("project-1", "user-a", "Income")
    state.selections_by_id["selection-1"] = SelectionRecord(
        "selection-1", "user-a", "project-1", "Income", ("IE1",)
    )
    state.credential_vault().set_credential(user_id="user-a", provider_key="test-key")
    runtime = LocalHostedRuntime(
        quote_workflow=_empty_workflow,
        metadata_workflow=_empty_workflow,
        cpu_count=lambda: 4,
    )
    service = QuoteRunService(state, runtime)

    first, first_task = service.start(
        "user-a", project_id="project-1", selection_id=None, idempotency_key=None
    )
    second, second_task = service.start(
        "user-a", project_id="project-1", selection_id=None, idempotency_key=None
    )

    assert first["status"] == "running"
    assert first_task is not None
    assert second["download_run_id"] == first["download_run_id"]
    assert second["status"] == "running"
    assert second_task is None


def test_project_context_cleans_discontinued_projects_and_tracks_loaded_data() -> None:
    state = HostedApiState()
    state.projects_by_id = {
        "removed": ProjectRecord("removed", "user-a", "Statistics Smoke"),
        "project-b": ProjectRecord("project-b", "user-a", "Beta"),
        "project-a": ProjectRecord("project-a", "user-a", "alpha"),
        "other": ProjectRecord("other", "user-b", "Statistics Smoke"),
    }
    state.selections_by_id = {
        "removed-selection": SelectionRecord(
            "removed-selection", "user-a", "removed", "Old", ("IE0",)
        ),
        "selection-a": SelectionRecord(
            "selection-a", "user-a", "project-a", "Current", ("IE1", "IE2")
        ),
        "selection-a-new": SelectionRecord(
            "selection-a-new", "user-a", "project-a", "Current", ("IE3",)
        ),
    }
    state.current_metadata_selection_by_user["user-a"] = "selection-a-new"
    run = ProviderDownloadRun(
        download_run_id="run-1",
        user_id="user-a",
        credential_id="credential-1",
        provider="eodhd",
        status="succeeded",
        returned_observation_ids=("observation-1",),
        request_hash="hash-1",
    )
    state.downloads_by_id[run.download_run_id] = run
    state.idempotency_refs[("user-a", "fetch-all-quotes:project-a", "request-1")] = (
        run.download_run_id
    )

    context = project_context_row(state, "user-a")

    assert context["current_project_id"] == "project-a"
    assert [row["project_id"] for row in context["projects"]] == ["project-a", "project-b"]
    assert context["projects"][0]["selected_count"] == 1
    assert context["projects"][0]["data_loaded"] is True
    assert "removed" not in state.projects_by_id
    assert "other" in state.projects_by_id
    assert project_data_loaded(state, "project-b", "user-a") is False
    assert selection_for_project(state, "project-a", "user-a").selection_id == "selection-a-new"
    with pytest.raises(HostedApplicationError, match="not_found"):
        selection_for_project(state, "project-b", "user-a")

    set_current_project(state, "user-a", "project-b")
    selected_project = current_project(state, "user-a")
    assert selected_project is not None
    assert selected_project.project_id == "project-b"
    assert current_project(HostedApiState(), "user-a") is None


def test_workflow_row_resolves_completed_research_chain() -> None:
    state = HostedApiState()
    selection = SelectionRecord("selection-1", "user-a", "project-1", "UCITS", ("IE1",))
    state.selections_by_id[selection.selection_id] = selection
    quote_run = ProviderDownloadRun(
        "quote-1", "user-a", "credential-1", "eodhd", "succeeded", ("row-1",), "hash-1"
    )
    state.downloads_by_id[quote_run.download_run_id] = quote_run
    state.idempotency_refs[("user-a", "fetch-all-quotes:project-1", "request-1")] = "quote-1"
    univariate = ResearchRun("univariate-1", "user-a", "quote-1", "complete", (), 0, 0)
    state.univariate_runs_by_id[univariate.run_id] = univariate
    state.quote_run_by_univariate_run_id[univariate.run_id] = "quote-1"
    filtered = FilterSelection(
        "filter-1",
        "user-a",
        univariate.run_id,
        ("IE1",),
        (Predicate("mean", ">", "0"),),
        (),
        1,
    )
    state.filter_selections_by_id[filtered.selection_id] = filtered
    state.current_filter_selection_by_user["user-a"] = filtered.selection_id

    stages = workflow_row(state, "user-a", "project-1")["stages"]

    assert stages["metadata_filter"]["status"] == "complete"
    assert stages["univariate_statistics"]["status"] == "complete"
    assert stages["univariate_filter"]["status"] == "complete"
    assert workflow_row(state, "user-a", None)["stages"]["metadata_filter"]["status"] == "ready"


def test_workflow_row_exposes_an_active_quote_run_for_the_current_selection() -> None:
    state = HostedApiState()
    selection = SelectionRecord("selection-1", "user-a", "project-1", "UCITS", ("IE1",))
    state.selections_by_id[selection.selection_id] = selection
    request_hash = stable_hash(
        {
            "project_id": selection.project_id,
            "selection_id": selection.selection_id,
            "member_ids": list(selection.member_ids),
        }
    )
    run_id = opaque_id("fetch-all-quotes", f"user-a:{request_hash}")
    state.downloads_by_id[run_id] = ProviderDownloadRun(
        run_id, "user-a", "credential-1", "eodhd", "running", selection.member_ids, request_hash
    )

    stages = workflow_row(state, "user-a", selection.project_id)["stages"]

    assert stages["metadata_filter"]["quote_run_id"] == run_id
    assert stages["univariate_statistics"]["status"] == "ready"
