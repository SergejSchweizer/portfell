from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from hosted_test_support import InMemoryRuntime

from portfell.entitlements import ProviderDownloadRun
from portfell.hosted_analysis_service import HostedAnalysisService
from portfell.hosted_api_errors import HostedApplicationError
from portfell.hosted_api_service_support import (
    _apply_univariate_selection_settings,
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
from portfell.hosted_audit_event_repository import HostedAuditEvent
from portfell.hosted_credential_project_service import CredentialProjectService
from portfell.hosted_local_audit_event_repository import LocalAuditEventRepository
from portfell.hosted_local_metadata_repository import LocalMetadataLifecycleRepository
from portfell.hosted_local_project_repository import LocalProjectRepository
from portfell.hosted_local_selection_repository import LocalSelectionRepository
from portfell.hosted_metadata_project_service import (
    MetadataProjectService as _MetadataProjectService,
)
from portfell.hosted_metadata_project_service import (
    metadata_source_catalog,
)
from portfell.hosted_navigation_read_model_repository import PostgresNavigationReadModel
from portfell.hosted_repository_importer import (
    InMemoryProjectRepository,
    TenantProject,
    TenantSelection,
)
from portfell.hosted_research_persistence import LocalResearchPersistence
from portfell.hosted_research_repository import HostedResearchRepository
from portfell.hosted_research_workflow import ResearchRun, UnivariateSelection
from portfell.hosted_selection_repository import InMemorySelectionRepository
from portfell.hosted_workspace import LocalWorkspaceStore
from portfell.hosted_workspace_repository import persist_local_workspace, restore_local_workspace
from portfell.market_source.contracts import Listing, ListingKey
from portfell.selection_filters import Predicate
from portfell.table_io import JsonRow


def MetadataProjectService(
    state: HostedApiState, runtime: InMemoryRuntime, **dependencies: Any
) -> _MetadataProjectService:
    return _MetadataProjectService(
        state,
        runtime,
        dependencies.pop("project_repository", LocalProjectRepository(state)),
        dependencies.pop("selection_repository", LocalSelectionRepository(state)),
        dependencies.pop("metadata_repository", LocalMetadataLifecycleRepository(state)),
        dependencies.pop("audit_repository", LocalAuditEventRepository(state)),
        **dependencies,
    )


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


def test_opaque_ids_are_stable_postgres_uuid_values() -> None:
    value = opaque_id("quote-run", "same-input")

    assert value == opaque_id("quote-run", "same-input")
    assert value != opaque_id("metadata-run", "same-input")
    assert str(UUID(value)) == value


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
    state.downloads_by_id["run-1"] = ProviderDownloadRun(
        "run-1",
        "user-a",
        "credential-1",
        "eodhd",
        "succeeded",
        ("observation-1",),
        "request-hash-1",
        {"symbols": ["AAA"]},
    )

    persist_local_workspace(state)
    restored = HostedApiState()
    restore_local_workspace(restored, store.load())

    assert restored.projects_by_id == state.projects_by_id
    assert restored.selections_by_id == state.selections_by_id
    assert restored.current_project_id_by_user == {"user-a": "project-1"}
    assert restored.current_metadata_selection_by_user == {"user-a": "selection-1"}
    assert restored.metadata_revisions_by_user == {"user-a": "revision-1"}
    assert restored.downloads_by_id["run-1"].requested_scope == {"symbols": ["AAA"]}
    assert json.loads((tmp_path / "workspace.json").read_text(encoding="utf-8"))["projects"]


def test_local_workspace_principal_rejects_non_uuid_user_id() -> None:
    with pytest.raises(ValueError, match="user id must be a UUID"):
        LocalWorkspaceUserProvider(" ")


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


def test_project_commands_can_use_an_injected_audit_repository_without_state_authority() -> None:
    class AuditRepository:
        def __init__(self) -> None:
            self.events: list[HostedAuditEvent] = []

        def append(self, event: HostedAuditEvent) -> HostedAuditEvent:
            self.events.append(event)
            return event

    state = HostedApiState()
    audit_repository = AuditRepository()
    service = CredentialProjectService(state, audit_repository=audit_repository)
    user_id = "00000000-0000-5000-8000-000000000001"

    service.create_project(user_id, "Income", idempotency_key=None)

    assert state.audit_events == []
    assert [(event.event_type, event.subject_ref) for event in audit_repository.events] == [
        ("project.create", f"user:{user_id}")
    ]


def test_project_commands_can_use_an_injected_repository_without_state_authority() -> None:
    state = HostedApiState()
    repository = InMemoryProjectRepository()
    service = CredentialProjectService(state, project_repository=repository)
    user_id = "00000000-0000-5000-8000-000000000001"

    created = service.create_project(user_id, "Income", idempotency_key=None)

    assert state.projects_by_id == {}
    assert repository.current_project_id(user_id) == created["project_id"]
    assert service.list_projects(user_id, limit=10, offset=0)["items"] == [
        {
            "project_id": created["project_id"],
            "name": "Income",
            "selected_count": 0,
            "data_loaded": False,
        }
    ]


def test_selection_commands_can_use_an_injected_repository_without_state_authority() -> None:
    state = HostedApiState()
    user_id = "00000000-0000-5000-8000-000000000001"
    project_id = "00000000-0000-5000-8000-000000000002"
    projects = InMemoryProjectRepository()
    projects.create_project(TenantProject(project_id, user_id, "Income"))
    selections = InMemorySelectionRepository()
    service = CredentialProjectService(
        state,
        project_repository=projects,
        selection_repository=selections,
    )

    created = service.create_selection(user_id, project_id, "Income", ["IE1"])

    assert state.selections_by_id == {}
    assert service.selection_detail(user_id, created["selection_id"]) == created
    assert service.list_projects(user_id, limit=10, offset=0)["items"] == [
        {
            "project_id": project_id,
            "name": "Income",
            "selection_id": created["selection_id"],
            "selected_count": 1,
            "data_loaded": False,
        }
    ]


def test_metadata_builder_project_can_use_an_injected_project_repository() -> None:
    state = HostedApiState(
        all_isins_rows=(
            {
                "isin": "IE1",
                "exchange": "XETRA",
                "code": "AAA",
                "name": "Example UCITS ETF",
                "instrument_type": "ETF",
                "country": "IE",
                "currency": "EUR",
            },
        )
    )
    user_id = "00000000-0000-5000-8000-000000000001"
    state.metadata_revisions_by_user[user_id] = "revision-1"
    runtime = InMemoryRuntime(state)
    repository = InMemoryProjectRepository()
    service = MetadataProjectService(state, runtime, project_repository=repository)

    created = service.create_project_from_criteria(
        user_id,
        exchange="XETRA",
        name="UCITS ETF",
        instrument_type="ETF",
        country="IE",
        currency="EUR",
        idempotency_key=None,
    )

    assert state.projects_by_id == {}
    assert repository.current_project_id(user_id) == created["project"]["project_id"]


def test_metadata_builder_options_count_unique_isins_per_value() -> None:
    state = HostedApiState(
        all_isins_rows=(
            {
                "isin": "IE1",
                "exchange": "XETRA",
                "instrument_type": "ETF",
                "country": "IE",
                "currency": "EUR",
            },
            {
                "isin": "IE1",
                "exchange": "XETRA",
                "instrument_type": "ETF",
                "country": "IE",
                "currency": "EUR",
            },
            {
                "isin": "IE2",
                "exchange": "LSE",
                "instrument_type": "FUND",
                "country": "LU",
                "currency": "USD",
            },
        )
    )
    runtime = InMemoryRuntime(state)

    assert MetadataProjectService(state, runtime).options("user-a")["exchange"] == [
        {"value": "LSE", "isin_count": 1},
        {"value": "XETRA", "isin_count": 1},
    ]


def test_metadata_builder_uses_only_active_full_identity_market_catalogue() -> None:
    class Gateway:
        def read_active_listings(self) -> tuple[Listing, ...]:
            return (
                Listing(
                    ListingKey("IE1", "XETRA", "ETF-A"),
                    "Income ETF",
                    "ETF",
                    "DE",
                    "EUR",
                    True,
                ),
                Listing(
                    ListingKey("IE1", "XETRA", "ETF-B"),
                    "Income ETF",
                    "ETF",
                    "DE",
                    "EUR",
                    True,
                ),
            )

    user_id = "00000000-0000-5000-8000-000000000001"
    catalog = metadata_source_catalog(Gateway())  # type: ignore[arg-type]
    state = HostedApiState()
    service = MetadataProjectService(state, InMemoryRuntime(state), market_catalog=lambda: catalog)

    assert service.options(user_id)["metadata_ready"] is True
    fetched, _ = service.start_metadata_fetch(user_id)
    created = service.create_project_from_criteria(
        user_id,
        exchange="XETRA",
        name="Income",
        instrument_type="ETF",
        country="DE",
        currency="EUR",
        idempotency_key=None,
    )

    assert fetched["snapshot_id"] == catalog.snapshot_id
    assert created["selection"]["member_ids"] == ["IE1:XETRA:ETF-A", "IE1:XETRA:ETF-B"]
    assert created["selected_count"] == 1
    assert service.state.metadata_revisions_by_user[user_id] == catalog.snapshot_id


def test_project_context_can_use_durable_data_loaded_projection() -> None:
    state = HostedApiState()
    user_id = "00000000-0000-5000-8000-000000000001"
    project_id = "00000000-0000-5000-8000-000000000002"
    projects = InMemoryProjectRepository()
    projects.create_project(TenantProject(project_id, user_id, "Income"))
    selections = InMemorySelectionRepository()
    selections.create(TenantSelection("selection-1", project_id, user_id, "Income", ("IE1",)))
    service = CredentialProjectService(
        state,
        project_repository=projects,
        selection_repository=selections,
        project_data_loaded_reader=lambda reader_user_id, reader_project_id: (
            (
                reader_user_id,
                reader_project_id,
            )
            == (user_id, project_id)
        ),
    )

    context = service.project_context(user_id)

    assert context["projects"][0]["data_loaded"] is True


def test_project_context_uses_an_injected_navigation_projection() -> None:
    service = CredentialProjectService(
        HostedApiState(),
        navigation_reader=lambda user_id: (
            (
                {"current_project_id": "project-1", "current_project": None, "projects": []},
                "etag",
            )
            if user_id == "user-1"
            else None
        ),
    )

    assert service.project_context("user-1")["current_project_id"] == "project-1"


def test_project_command_writes_navigation_projection() -> None:
    writes: list[tuple[str, JsonRow]] = []
    service = CredentialProjectService(
        HostedApiState(),
        navigation_writer=lambda user_id, payload: (
            writes.append((user_id, payload)) or (payload, "etag")
        ),
    )

    created = service.create_project("user-1", "Income", "request-1")

    assert created["name"] == "Income"
    assert writes == [
        (
            "user-1",
            {
                "current_project_id": created["project_id"],
                "current_project": {
                    "project_id": created["project_id"],
                    "name": "Income",
                    "selected_count": 0,
                    "data_loaded": False,
                },
                "projects": [
                    {
                        "project_id": created["project_id"],
                        "name": "Income",
                        "selected_count": 0,
                        "data_loaded": False,
                    }
                ],
            },
        )
    ]


def test_navigation_read_model_binds_rls_and_derives_a_stable_etag() -> None:
    class Cursor:
        def fetchone(self) -> tuple[object, ...]:
            return ({"current_project_id": "project-1", "projects": []}, 7)

    class Connection:
        calls: list[tuple[str, tuple[object, ...]]] = []

        def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> Cursor:
            self.calls.append((sql, parameters))
            return Cursor()

    connection = Connection()
    first = PostgresNavigationReadModel(connection).read("00000000-0000-5000-8000-000000000001")
    second = PostgresNavigationReadModel(connection).read("00000000-0000-5000-8000-000000000001")

    assert first is not None and second is not None
    assert first[0] == second[0]
    assert first[1] == second[1]
    assert connection.calls[0][0] == "select set_config(%s, %s, true)"
    assert "navigation_projections" in connection.calls[1][0]


def test_project_context_includes_an_active_project_run() -> None:
    state = HostedApiState()
    user_id = "00000000-0000-5000-8000-000000000001"
    project_id = "00000000-0000-5000-8000-000000000002"
    projects = InMemoryProjectRepository()
    projects.create_project(TenantProject(project_id, user_id, "Income"))
    selections = InMemorySelectionRepository()
    selections.create(TenantSelection("selection-1", project_id, user_id, "Income", ("IE1",)))
    service = CredentialProjectService(
        state,
        project_repository=projects,
        selection_repository=selections,
        project_active_run_reader=lambda reader_user_id, reader_project_id: (
            {"status": "waiting"}
            if (reader_user_id, reader_project_id) == (user_id, project_id)
            else None
        ),
    )

    context = service.project_context(user_id)

    assert context["projects"][0]["active_run"] == {
        "status": "waiting",
    }


def test_metadata_builder_can_use_an_injected_selection_repository() -> None:
    state = HostedApiState(
        all_isins_rows=(
            {
                "isin": "IE1",
                "exchange": "XETRA",
                "code": "AAA",
                "name": "Example UCITS ETF",
                "instrument_type": "ETF",
                "country": "IE",
                "currency": "EUR",
            },
        )
    )
    user_id = "00000000-0000-5000-8000-000000000001"
    state.metadata_revisions_by_user[user_id] = "revision-1"
    runtime = InMemoryRuntime(state)
    projects = InMemoryProjectRepository()
    selections = InMemorySelectionRepository()
    service = MetadataProjectService(
        state,
        runtime,
        project_repository=projects,
        selection_repository=selections,
    )

    created = service.create_project_from_criteria(
        user_id,
        exchange="XETRA",
        name="UCITS ETF",
        instrument_type="ETF",
        country="IE",
        currency="EUR",
        idempotency_key="request-1",
    )
    repeated = service.create_project_from_criteria(
        user_id,
        exchange="XETRA",
        name="UCITS ETF",
        instrument_type="ETF",
        country="IE",
        currency="EUR",
        idempotency_key="request-1",
    )

    assert state.projects_by_id == {}
    assert state.selections_by_id == {}
    assert repeated == created


def test_metadata_builder_project_refreshes_navigation_projection() -> None:
    refreshed: list[str] = []
    state = HostedApiState(
        all_isins_rows=(
            {
                "isin": "IE1",
                "exchange": "XETRA",
                "code": "AAA",
                "name": "Example",
                "instrument_type": "ETF",
                "country": "IE",
                "currency": "EUR",
            },
        )
    )
    state.metadata_revisions_by_user["user-1"] = "metadata-v1"
    service = MetadataProjectService(
        state,
        InMemoryRuntime(state),
        navigation_refresher=refreshed.append,
    )

    service.create_project_from_criteria(
        "user-1",
        exchange="XETRA",
        name="",
        instrument_type="ETF",
        country="",
        currency="",
        idempotency_key=None,
    )

    assert refreshed == ["user-1"]


def test_metadata_builder_reuses_an_immutable_selection_after_catalog_changes() -> None:
    user_id = "00000000-0000-5000-8000-000000000001"
    state = HostedApiState(
        all_isins_rows=(
            {
                "isin": "IE1",
                "exchange": "XETRA",
                "code": "AAA",
                "name": "Example",
                "instrument_type": "ETF",
                "country": "IE",
                "currency": "EUR",
            },
        )
    )
    state.metadata_revisions_by_user[user_id] = "revision-1"
    service = MetadataProjectService(
        state,
        InMemoryRuntime(state),
    )

    created = service.create_project_from_criteria(
        user_id,
        exchange="XETRA",
        name="Example",
        instrument_type="ETF",
        country="IE",
        currency="EUR",
        idempotency_key=None,
    )
    state.all_isins_rows = (
        *state.all_isins_rows,
        {
            "isin": "IE2",
            "exchange": "XETRA",
            "code": "BBB",
            "name": "Example",
            "instrument_type": "ETF",
            "country": "IE",
            "currency": "EUR",
        },
    )

    repeated = service.create_project_from_criteria(
        user_id,
        exchange="XETRA",
        name="Example",
        instrument_type="ETF",
        country="IE",
        currency="EUR",
        idempotency_key=None,
    )

    assert repeated == created


def test_analysis_can_authorize_an_injected_project_repository() -> None:
    state = HostedApiState()
    user_id = "00000000-0000-5000-8000-000000000001"
    project_id = "00000000-0000-5000-8000-000000000002"
    selection_id = "00000000-0000-5000-8000-000000000003"
    projects = InMemoryProjectRepository()
    projects.create_project(TenantProject(project_id, user_id, "Income"))
    selections = InMemorySelectionRepository()
    selections.create(TenantSelection(selection_id, project_id, user_id, "Income", ("IE1",)))
    repository = HostedResearchRepository(
        state,
        project_repository=projects,
        selection_repository=selections,
    )
    service = HostedAnalysisService(repository, LocalResearchPersistence(state))

    analysis = service.create(
        user_id,
        project_id,
        selection_id,
        {"objective": "minimum_variance"},
        idempotency_key=None,
    )

    assert state.projects_by_id == {}
    assert state.selections_by_id == {}
    assert analysis["status"] == "succeeded"


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
    filtered = UnivariateSelection(
        "filter-1",
        "user-a",
        univariate.run_id,
        ("IE1",),
        (Predicate("mean", ">", "0"),),
        (),
        1,
    )
    state.univariate_selections_by_id[filtered.selection_id] = filtered
    state.current_univariate_selection_by_user["user-a"] = filtered.selection_id

    stages = workflow_row(state, "user-a", "project-1")["stages"]

    assert stages["metadata_builder"]["status"] == "complete"
    assert stages["univariate_statistics"]["status"] == "complete"
    assert stages["bivariate_statistics"]["status"] == "ready"
    assert workflow_row(state, "user-a", None)["stages"]["metadata_builder"]["status"] == "ready"


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

    assert stages["metadata_builder"]["quote_run_id"] == run_id
    assert stages["univariate_statistics"]["status"] == "ready"


def test_univariate_selection_settings_filter_frequency_and_numeric_ranges() -> None:
    rows: tuple[JsonRow, ...] = (
        {"distribution_frequency": "monthly", "mean": 1.0},
        {"distribution_frequency": "annual", "mean": 1.0},
        {"distribution_frequency": "monthly", "mean": 3.0},
        {"distribution_frequency": "unknown", "mean": 1.0},
        {"distribution_frequency": "monthly", "mean": "invalid"},
    )

    filtered = _apply_univariate_selection_settings(
        rows,
        {
            "dividend_frequencies": ["monthly", 3],
            "statistic_ranges": {
                "mean": [{"minimum": 0.0, "maximum": 2.0}],
                "ignored": "not-a-range",
            },
        },
    )

    assert filtered == (rows[0],)


def test_univariate_duration_filter_excludes_the_exact_six_month_boundary() -> None:
    rows: tuple[JsonRow, ...] = (
        {"isin": "IE00A", "distribution_frequency": "monthly", "quote_observation_count": 126},
        {"isin": "IE00B", "distribution_frequency": "monthly", "quote_observation_count": 127},
        {"isin": "IE00C", "distribution_frequency": "monthly", "quote_observation_count": 21},
    )

    filtered = _apply_univariate_selection_settings(
        rows,
        {
            "dividend_frequencies": ["monthly"],
            "statistic_ranges": {
                "quote_observation_count": [{"minimum": 127, "maximum": 9_007_199_254_740_991}],
            },
        },
    )

    assert filtered == (rows[1],)
