from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from fastapi.testclient import TestClient

import portfell.hosted_api as hosted_api
from portfell.entitlements import ProviderDownloadRun
from portfell.hosted_api import (
    ApiUser,
    HostedApiState,
    LocalWorkspaceUserProvider,
    ProjectRecord,
    SelectionRecord,
    create_app,
    create_persistent_local_workspace_state,
)
from portfell.hosted_credentials import InMemoryCredentialStore, KeyEncryptionKey
from portfell.paths import LakePaths
from portfell.table_io import read_json, read_rows


def _client(state: HostedApiState | None = None) -> TestClient:
    return TestClient(create_app(state or HostedApiState()))


def _headers(
    user_id: str = "user-a", *, csrf: bool = False, idempotency: str | None = None
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if idempotency is not None:
        headers["Idempotency-Key"] = idempotency
    return headers


def _json(response: Any) -> dict[str, Any]:
    payload = response.json()
    assert isinstance(payload, dict)
    return cast("dict[str, Any]", payload)


def test_local_workspace_requires_no_authentication_or_csrf() -> None:
    client = _client()

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/auth/google/start").status_code == 404
    assert client.post("/projects", json={"name": "Core"}).status_code == 200


def test_local_workspace_user_provider_is_stable_and_server_owned() -> None:
    provider = LocalWorkspaceUserProvider(user_id="workspace-a")
    first = provider.current_user()
    second = provider.current_user()

    assert first == ApiUser(user_id="workspace-a")
    assert second == first


def test_api_uses_injected_current_user_provider() -> None:
    provider = LocalWorkspaceUserProvider(user_id="workspace-a")
    client = TestClient(create_app(current_user_provider=provider))

    client.post("/credentials/eodhd", json={"provider_key": "secret-provider-token"})
    status = _json(client.get("/credentials/eodhd"))

    assert status["status"] == "active"


def test_api_uses_injected_credential_vault_dependencies() -> None:
    state = HostedApiState(
        credentials=InMemoryCredentialStore(),
        credential_key_encryption_key=KeyEncryptionKey("test-v1", b"1" * 32),
        credential_fingerprint_secret=b"test-fingerprint-secret",
    )
    client = _client(state)

    client.post("/credentials/eodhd", json={"provider_key": "secret-provider-token"})

    assert (
        state.credential_vault().unwrap_for_provider_call(user_id="user-a")
        == "secret-provider-token"
    )


def test_persistent_local_workspace_restores_credential_and_projects_after_restart(
    tmp_path: Path,
) -> None:
    key = KeyEncryptionKey("test-v1", b"1" * 32)
    first_client = _client(
        create_persistent_local_workspace_state(tmp_path, key_encryption_key=key)
    )
    first_client.post("/credentials/eodhd", json={"provider_key": "secret-provider-token"})
    project = _json(first_client.post("/projects", json={"name": "Core"}))

    restored_client = _client(
        create_persistent_local_workspace_state(tmp_path, key_encryption_key=key)
    )

    assert _json(restored_client.get("/credentials/eodhd/value")) == {
        "provider_key": "secret-provider-token"
    }
    context = _json(restored_client.get("/project-context"))
    assert context["current_project_id"] == project["project_id"]
    assert context["projects"] == [
        {
            "project_id": project["project_id"],
            "name": "Core",
            "selected_count": 0,
            "data_loaded": False,
        }
    ]


def test_workflow_starts_with_only_metadata_ready() -> None:
    client = _client()

    workflow = _json(client.get("/workflow"))

    assert workflow == {
        "stages": {
            "metadata_filter": {"status": "ready"},
            "univariate_statistics": {"status": "locked"},
            "univariate_filter": {"status": "locked"},
            "bivariate_statistics": {"status": "locked"},
        }
    }


def test_credential_lifecycle_redacts_sensitive_material() -> None:
    client = _client()

    created = _json(
        client.post(
            "/credentials/eodhd",
            headers=_headers(idempotency="credential-1"),
            json={"provider_key": "secret-provider-token"},
        )
    )
    repeated = _json(
        client.post(
            "/credentials/eodhd",
            headers=_headers(idempotency="credential-1"),
            json={"provider_key": "changed-token"},
        )
    )
    deleted = _json(client.delete("/credentials/eodhd", headers=_headers()))
    rendered = str(created) + str(repeated) + str(deleted)

    assert created["status"] == "active"
    assert repeated["credential_id"] == created["credential_id"]
    assert deleted["status"] == "deleted"
    assert "secret-provider-token" not in rendered
    assert "changed-token" not in rendered
    assert "fingerprint" not in rendered
    assert "ciphertext" not in rendered
    assert "nonce" not in rendered


def test_downloads_publish_visible_user_datasets_and_are_idempotent() -> None:
    client = _client()

    plan = _json(
        client.post(
            "/downloads/plan",
            headers=_headers(),
            json={"symbols": ["AAA.XETRA", "BBB.XETRA"]},
        )
    )
    run = _json(
        client.post(
            "/downloads/run",
            headers=_headers(idempotency="download-1"),
            json={"symbols": ["AAA.XETRA", "BBB.XETRA"]},
        )
    )
    repeated = _json(
        client.post(
            "/downloads/run",
            headers=_headers(idempotency="download-1"),
            json={"symbols": ["CCC.XETRA"]},
        )
    )
    datasets = _json(client.get("/datasets", headers=_headers(csrf=False)))
    other_datasets = _json(client.get("/datasets", headers=_headers("user-b", csrf=False)))

    assert plan["status"] == "planned"
    assert run == repeated
    assert run["status"] == "succeeded"
    assert run["observation_count"] == 2
    assert len(datasets["items"]) == 2
    assert other_datasets == datasets


def test_metadata_filter_options_and_project_creation_use_all_isins_reference() -> None:
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
                "source_exchange": "XETRA",
                "fetched_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "isin": "US1",
                "exchange": "NYSE",
                "code": "BBB",
                "name": "Example Stock",
                "instrument_type": "Common Stock",
                "country": "US",
                "currency": "USD",
                "source_exchange": "NYSE",
                "fetched_at": "2026-01-01T00:00:00+00:00",
            },
        )
    )
    client = _client(state)

    options = _json(client.get("/metadata-filter/options", headers=_headers(csrf=False)))
    created = _json(
        client.post(
            "/metadata-filter",
            headers=_headers(idempotency="metadata-project-1"),
            json={
                "exchange": "XETRA",
                "name": "UCITS ETF",
                "instrument_type": "ETF",
                "country": "IE",
                "currency": "EUR",
            },
        )
    )
    repeated = _json(
        client.post(
            "/metadata-filter",
            headers=_headers(idempotency="metadata-project-1"),
            json={
                "exchange": "XETRA",
                "name": "UCITS ETF",
                "instrument_type": "ETF",
                "country": "IE",
                "currency": "EUR",
            },
        )
    )

    assert options == {
        "country": ["IE", "US"],
        "currency": ["EUR", "USD"],
        "exchange": ["NYSE", "XETRA"],
        "instrument_type": ["Common Stock", "ETF"],
    }
    assert created == repeated
    assert created["project"]["name"] == "xetra_ucits_etf_etf_ie_eur"
    assert "name_" not in created["project"]["name"]
    assert created["selection"]["member_ids"] == ["IE1:XETRA:AAA"]
    assert created["selected_count"] == 1
    assert _json(client.get("/projects", headers=_headers(csrf=False)))["items"] == [
        {
            **created["project"],
            "data_loaded": False,
            "selected_count": 1,
            "selection_id": created["selection"]["selection_id"],
        }
    ]
    assert _json(client.get("/projects", headers=_headers("user-b", csrf=False)))["items"] == [
        {
            **created["project"],
            "data_loaded": False,
            "selected_count": 1,
            "selection_id": created["selection"]["selection_id"],
        }
    ]
    assert (
        _json(
            client.get(
                f"/selections/{created['selection']['selection_id']}",
                headers=_headers("user-b", csrf=False),
            )
        )["selection_id"]
        == created["selection"]["selection_id"]
    )


def test_load_selected_isins_runs_fetch_all_quotes_for_metadata_selection(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    lake_root = tmp_path / "lake"
    monkeypatch.setenv("PORTFELL_LAKE_ROOT", str(lake_root))
    calls: list[dict[str, Any]] = []
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
                "source_exchange": "XETRA",
                "fetched_at": "2026-01-01T00:00:00+00:00",
            },
        )
    )

    def fake_fetch_all_quotes_workflow(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        kwargs["on_progress"](3, 4, 0)
        return {
            "coverage_rows": 1,
            "raw_dataset_errors": 0,
            "raw_dataset_successes": 2,
            "quote_errors": 0,
            "quote_successes": 1,
            "run_id": kwargs["run_id"],
            "selection_id": kwargs["selection_id"],
            "selected_listing_count": 1,
            "silver_quote_rows": 42,
        }

    monkeypatch.setattr(
        "portfell.hosted_api.run_fetch_all_quotes_workflow",
        fake_fetch_all_quotes_workflow,
    )
    monkeypatch.setattr(hosted_api.os, "process_cpu_count", lambda: 6)
    client = _client(state)
    client.post(
        "/credentials/eodhd",
        headers=_headers(idempotency="credential-load-selected-isins"),
        json={"provider_key": "secret-provider-token"},
    )
    created = _json(
        client.post(
            "/metadata-filter",
            headers=_headers(idempotency="metadata-project-load-selected-isins"),
            json={
                "exchange": "XETRA",
                "name": "UCITS ETF",
                "instrument_type": "ETF",
                "country": "IE",
                "currency": "EUR",
            },
        )
    )
    selection_id = created["selection"]["selection_id"]

    loaded_data = _json(
        client.post(
            "/quote-runs",
            headers=_headers(idempotency="load-selected-isins-1"),
            json={"project_id": created["project"]["project_id"]},
        )
    )
    loaded_data_again = _json(
        client.post(
            "/quote-runs",
            headers=_headers(idempotency="load-selected-isins-1"),
            json={"project_id": created["project"]["project_id"]},
        )
    )
    loaded_status = _json(
        client.get(f"/quote-runs/{loaded_data['download_run_id']}", headers=_headers(csrf=False))
    )
    paths = LakePaths(root=lake_root)
    persisted_selection_rows = read_rows(paths.metadata_filter_isins(selection_id))
    current_selection = read_json(paths.current_metadata_filter_selection())
    reloaded_project = _json(client.get("/projects", headers=_headers(csrf=False)))["items"][0]

    assert len(calls) == 1
    assert calls[0]["root"] == lake_root
    assert calls[0]["selection_id"] == selection_id
    assert calls[0]["concurrency"] == 6
    assert calls[0]["memory_safe"] is True
    assert calls[0]["eodhd_config"].api_token == "secret-provider-token"
    assert persisted_selection_rows[0]["isin"] == "IE1"
    assert persisted_selection_rows[0]["exchange"] == "XETRA"
    assert persisted_selection_rows[0]["code"] == "AAA"
    assert current_selection["selection_id"] == selection_id
    assert loaded_data["download_run_id"] == loaded_data_again["download_run_id"]
    assert loaded_data["status"] == "running"
    assert loaded_data_again["status"] == "succeeded"
    assert loaded_data["kind"] == "load-data"
    assert loaded_data["observation_count"] == 1
    assert loaded_data_again["quote_successes"] == 1
    assert loaded_data_again["raw_dataset_successes"] == 2
    assert loaded_data_again["selected_listing_count"] == 1
    assert loaded_data_again["selected_count"] == 1
    assert loaded_data_again["silver_quote_rows"] == 42
    assert loaded_status["completed"] == 3
    assert loaded_status["started_at"] > 0
    assert loaded_status["total"] == 4
    assert loaded_status["percent"] == 100
    assert reloaded_project["data_loaded"] is True


def test_quote_run_progress_is_visible_after_the_first_completed_task(
    monkeypatch: Any,
) -> None:
    state = HostedApiState()
    run = ProviderDownloadRun(
        download_run_id="quote-run-progress",
        user_id="user-a",
        credential_id="project-selection",
        provider="eodhd",
        status="running",
        returned_observation_ids=("IE1:XETRA:AAA",),
        request_hash="request-a",
    )
    state.downloads_by_id[run.download_run_id] = run
    state.download_summaries_by_id[run.download_run_id] = {
        "total": 10_000,
        "completed": 0,
        "failed": 0,
        "percent": 0,
    }

    def fake_fetch_all_quotes_workflow(**kwargs: Any) -> dict[str, Any]:
        kwargs["on_progress"](1, 10_000, 0)
        assert state.download_summaries_by_id[run.download_run_id]["percent"] == 1
        return {
            "coverage_rows": 0,
            "raw_dataset_errors": 0,
            "raw_dataset_successes": 0,
            "quote_errors": 0,
            "quote_successes": 0,
            "run_id": kwargs["run_id"],
            "selection_id": kwargs["selection_id"],
            "selected_listing_count": 1,
            "silver_quote_rows": 0,
        }

    monkeypatch.setattr(
        "portfell.hosted_api.run_fetch_all_quotes_workflow",
        fake_fetch_all_quotes_workflow,
    )

    hosted_api._run_quote_fetch(
        state,
        run,
        "selection-a",
        "unused-provider-key",
    )


def test_load_selected_isins_reuses_running_quote_run_for_new_idempotency_key(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    lake_root = tmp_path / "lake"
    monkeypatch.setenv("PORTFELL_LAKE_ROOT", str(lake_root))
    calls: list[dict[str, Any]] = []
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

    def fake_fetch_all_quotes_workflow(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return {
            "coverage_rows": 0,
            "raw_dataset_errors": 0,
            "raw_dataset_successes": 0,
            "quote_errors": 0,
            "quote_successes": 0,
            "run_id": kwargs["run_id"],
            "selection_id": kwargs["selection_id"],
            "selected_listing_count": 1,
            "silver_quote_rows": 0,
        }

    monkeypatch.setattr(
        "portfell.hosted_api.run_fetch_all_quotes_workflow",
        fake_fetch_all_quotes_workflow,
    )
    client = _client(state)
    client.post("/credentials/eodhd", json={"provider_key": "secret-provider-token"})
    created = _json(
        client.post(
            "/metadata-filter",
            json={"exchange": "XETRA", "name": "UCITS ETF", "instrument_type": "ETF"},
        )
    )
    selection = state.selections_by_id[created["selection"]["selection_id"]]
    request_hash = hosted_api._stable_hash(
        {
            "project_id": created["project"]["project_id"],
            "selection_id": selection.selection_id,
            "member_ids": list(selection.member_ids),
        }
    )
    run = ProviderDownloadRun(
        download_run_id=hosted_api._opaque_id("fetch-all-quotes", f"user-a:{request_hash}"),
        user_id="user-a",
        credential_id="project-selection",
        provider="eodhd",
        status="running",
        returned_observation_ids=selection.member_ids,
        request_hash=request_hash,
    )
    state.downloads_by_id[run.download_run_id] = run
    state.download_summaries_by_id[run.download_run_id] = {"total": 4, "completed": 2}

    response = _json(
        client.post(
            "/quote-runs",
            headers=_headers(idempotency="new-quote-run-request"),
            json={"project_id": created["project"]["project_id"]},
        )
    )

    assert response["download_run_id"] == run.download_run_id
    assert response["status"] == "running"
    assert response["completed"] == 2
    assert calls == []


def test_fetch_all_metadata_for_metadata_filter_requires_eodhd_key(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    calls: list[str] = []

    class FakeMetadataClient:
        def get_json(
            self,
            path: str,
            params: dict[str, str | int | float] | None = None,
        ) -> object:
            calls.append(path)
            if path == "/exchanges-list/":
                return [{"Code": "XETRA"}]
            if path == "/exchange-symbol-list/XETRA":
                return [
                    {
                        "Code": "AAA",
                        "Exchange": "XETRA",
                        "Name": "Example UCITS ETF",
                        "Type": "ETF",
                        "Country": "IE",
                        "Currency": "EUR",
                        "Isin": "IE1",
                    }
                ]
            raise AssertionError(path)

    monkeypatch.setenv("PORTFELL_LAKE_ROOT", str(tmp_path / "lake"))
    monkeypatch.setattr(
        "portfell.workflows.EodhdClient",
        lambda _config: FakeMetadataClient(),
    )
    client = _client(HostedApiState())

    rejected = client.post("/metadata/fetch-all", headers=_headers())
    client.post(
        "/credentials/eodhd",
        headers=_headers(idempotency="credential-fetch-all-metadata"),
        json={"provider_key": "secret-provider-token"},
    )
    credential_status = _json(client.get("/credentials/eodhd", headers=_headers(csrf=False)))
    fetched = _json(client.post("/metadata/fetch-all", headers=_headers()))
    fetched_status = _json(
        client.get(
            f"/metadata/fetch-all/{fetched['metadata_run_id']}",
            headers=_headers(csrf=False),
        )
    )

    assert rejected.status_code == 422
    assert _json(rejected)["detail"]["code"] == "eodhd_key_required"
    assert credential_status["status"] == "active"
    assert calls == [
        "/exchanges-list/",
        "/exchange-symbol-list/XETRA",
    ]
    assert fetched["status"] == "running"
    assert fetched_status == {
        "exchange_count": 1,
        "completed": 2,
        "metadata_run_id": fetched["metadata_run_id"],
        "percent": 100,
        "requested_exchange_count": 1,
        "row_count": 1,
        "skipped_exchange_count": 0,
        "skipped_exchanges": [],
        "status": "succeeded",
        "total": 2,
    }


def test_fetch_all_metadata_rejects_an_invalid_eodhd_key_without_a_server_error(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    from portfell.http import EodhdHttpError

    class RejectedMetadataClient:
        def get_json(
            self,
            path: str,
            params: dict[str, str | int | float] | None = None,
        ) -> object:
            raise EodhdHttpError("EODHD request failed", status_code=401)

    monkeypatch.setenv("PORTFELL_LAKE_ROOT", str(tmp_path / "lake"))
    monkeypatch.setattr("portfell.workflows.EodhdClient", lambda _config: RejectedMetadataClient())
    client = _client(HostedApiState())
    client.post(
        "/credentials/eodhd",
        headers=_headers(idempotency="invalid-metadata-key"),
        json={"provider_key": "test-invalid-eodhd-key"},
    )

    started = _json(client.post("/metadata/fetch-all", headers=_headers()))
    response = client.get(
        f"/metadata/fetch-all/{started['metadata_run_id']}",
        headers=_headers(csrf=False),
    )

    assert response.status_code == 200
    assert _json(response)["status"] == "failed"
    assert _json(response)["error_code"] == "eodhd_key_rejected"


def test_fetch_all_metadata_rejects_an_invalid_eodhd_payload_without_a_server_error(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    class InvalidPayloadMetadataClient:
        def get_json(
            self,
            path: str,
            params: dict[str, str | int | float] | None = None,
        ) -> object:
            return {"error": "Invalid API token"}

    monkeypatch.setenv("PORTFELL_LAKE_ROOT", str(tmp_path / "lake"))
    monkeypatch.setattr(
        "portfell.workflows.EodhdClient", lambda _config: InvalidPayloadMetadataClient()
    )
    client = _client(HostedApiState())
    client.post(
        "/credentials/eodhd",
        headers=_headers(idempotency="invalid-metadata-payload"),
        json={"provider_key": "test-invalid-eodhd-key"},
    )

    started = _json(client.post("/metadata/fetch-all", headers=_headers()))
    response = client.get(
        f"/metadata/fetch-all/{started['metadata_run_id']}",
        headers=_headers(csrf=False),
    )

    assert response.status_code == 200
    assert _json(response)["status"] == "failed"
    assert _json(response)["error_code"] == "eodhd_metadata_invalid_response"


def test_projects_selections_and_analyses_use_the_local_workspace() -> None:
    client = _client()
    project = _json(
        client.post(
            "/projects",
            headers=_headers(idempotency="project-1"),
            json={"name": "ETF Research"},
        )
    )
    repeated_project = _json(
        client.post(
            "/projects",
            headers=_headers(idempotency="project-1"),
            json={"name": "ETF Research"},
        )
    )
    selection = _json(
        client.post(
            "/selections",
            headers=_headers(),
            json={
                "project_id": project["project_id"],
                "name": "Monthly ETFs",
                "member_ids": ["IE1", "IE2"],
            },
        )
    )
    analysis = _json(
        client.post(
            "/analyses",
            headers=_headers(idempotency="analysis-1"),
            json={
                "project_id": project["project_id"],
                "selection_id": selection["selection_id"],
                "settings": {"objective": "minimum_variance"},
            },
        )
    )
    repeated_analysis = _json(
        client.post(
            "/analyses",
            headers=_headers(idempotency="analysis-1"),
            json={
                "project_id": project["project_id"],
                "selection_id": selection["selection_id"],
                "settings": {"objective": "changed"},
            },
        )
    )
    projects_page = _json(client.get("/projects?limit=1&offset=0", headers=_headers(csrf=False)))

    assert repeated_project == project
    assert selection["member_ids"] == ["IE1", "IE2"]
    assert analysis["status"] == "succeeded"
    assert analysis["cache_hit"] is False
    assert repeated_analysis["run_id"] == analysis["run_id"]
    assert repeated_analysis["cache_hit"] is True
    assert len(projects_page["items"]) == 1
    assert _json(
        client.get(f"/analyses/{analysis['run_id']}/metrics", headers=_headers(csrf=False))
    )["items"]
    assert _json(
        client.get(f"/analyses/{analysis['run_id']}/returns", headers=_headers(csrf=False))
    )["items"]
    assert _json(
        client.get(f"/analyses/{analysis['run_id']}/weights", headers=_headers(csrf=False))
    )["items"]
    assert "summary" in _json(
        client.get(f"/analyses/{analysis['run_id']}/report", headers=_headers(csrf=False))
    )

    assert (
        _json(
            client.get(
                f"/selections/{selection['selection_id']}", headers=_headers("user-b", csrf=False)
            )
        )["selection_id"]
        == selection["selection_id"]
    )
    assert (
        _json(
            client.get(f"/analyses/{analysis['run_id']}", headers=_headers("user-b", csrf=False))
        )["run_id"]
        == analysis["run_id"]
    )
    deleted_project = _json(
        client.delete(f"/projects/{project['project_id']}", headers=_headers("user-b"))
    )
    assert deleted_project == {"project_id": project["project_id"], "status": "deleted"}
    assert _json(client.get("/projects", headers=_headers(csrf=False)))["items"] == []
    assert (
        client.get(
            f"/selections/{selection['selection_id']}", headers=_headers(csrf=False)
        ).status_code
        == 404
    )
    assert (
        client.get(f"/analyses/{analysis['run_id']}", headers=_headers(csrf=False)).status_code
        == 404
    )
    assert client.get("/projects?limit=0", headers=_headers(csrf=False)).status_code == 422


def test_project_context_defaults_selects_and_clears_current_project() -> None:
    alpha = ProjectRecord(project_id="project-alpha", user_id="user-a", name="alpha")
    core = ProjectRecord(project_id="project-core", user_id="user-a", name="Core")
    state = HostedApiState(projects_by_id={core.project_id: core, alpha.project_id: alpha})
    client = _client(state)

    default_context = _json(client.get("/project-context"))
    selected_context = _json(
        client.put("/project-context/current-project", json={"project_id": core.project_id})
    )
    empty_workflow = _json(client.get(f"/projects/{core.project_id}/workflow"))
    deleted = _json(client.delete(f"/projects/{core.project_id}"))
    fallback_context = _json(client.get("/project-context"))

    assert [project["name"] for project in default_context["projects"]] == ["alpha", "Core"]
    assert default_context["current_project_id"] == alpha.project_id
    assert selected_context["current_project_id"] == core.project_id
    assert empty_workflow == {
        "stages": {
            "metadata_filter": {"status": "ready"},
            "univariate_statistics": {"status": "locked"},
            "univariate_filter": {"status": "locked"},
            "bivariate_statistics": {"status": "locked"},
        }
    }
    assert deleted == {"project_id": core.project_id, "status": "deleted"}
    assert fallback_context["current_project_id"] == alpha.project_id
    missing = client.put("/project-context/current-project", json={"project_id": "missing"})
    assert missing.status_code == 404


def test_project_metadata_filter_restores_saved_field_values(
    tmp_path: Path, monkeypatch: Any
) -> None:
    monkeypatch.setenv("PORTFELL_LAKE_ROOT", str(tmp_path / "lake"))
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
    client = _client(state)
    created = _json(
        client.post(
            "/metadata-filter",
            headers=_headers(idempotency="metadata-filter-project-values"),
            json={
                "exchange": "XETRA",
                "name": "UCITS ETF",
                "instrument_type": "ETF",
                "country": "IE",
                "currency": "EUR",
            },
        )
    )

    restored = _json(client.get(f"/projects/{created['project']['project_id']}/metadata-filter"))

    assert restored == {
        "project_id": created["project"]["project_id"],
        "selection_id": created["selection"]["selection_id"],
        "selected_count": 1,
        "exchange": "XETRA",
        "instrument_type": "ETF",
        "country": "IE",
        "currency": "EUR",
        "name": "UCITS ETF",
    }


def test_project_context_is_empty_without_projects() -> None:
    client = _client()

    assert _json(client.get("/project-context")) == {
        "current_project_id": None,
        "current_project": None,
        "projects": [],
    }


def test_projects_listing_removes_discontinued_statistics_smoke_project() -> None:
    client = _client()
    project = _json(
        client.post(
            "/projects",
            headers=_headers(idempotency="statistics-smoke-project"),
            json={"name": "Statistics Smoke"},
        )
    )
    selection = _json(
        client.post(
            "/selections",
            headers=_headers(),
            json={
                "project_id": project["project_id"],
                "name": "Smoke Selection",
                "member_ids": ["IE1", "IE2"],
            },
        )
    )

    assert _json(client.get("/projects", headers=_headers(csrf=False))) == {"items": []}
    assert (
        client.get(
            f"/selections/{selection['selection_id']}", headers=_headers(csrf=False)
        ).status_code
        == 404
    )


def test_univariate_filter_metrics_expose_numerical_contract() -> None:
    payload = _json(_client().get("/univariate-filter/metrics", headers=_headers(csrf=False)))
    metrics = {row["metric"]: row for row in payload["items"]}

    assert metrics["annualized_volatility"]["unit"] == "ratio"
    assert metrics["quote_observation_count"]["unit"] == "count"
    assert metrics["expected_shortfall"]["operators"] == ["=", "!=", ">", ">=", "<", "<="]


def test_scoped_research_runs_filter_and_build_unique_pairs() -> None:
    project = ProjectRecord(project_id="project-a", user_id="user-a", name="Research")
    selection = SelectionRecord(
        selection_id="metadata-selection-a",
        user_id="user-a",
        project_id=project.project_id,
        name="Research",
        member_ids=("IE1:XETRA:AAA", "IE2:XETRA:BBB", "IE3:XETRA:CCC"),
    )
    quote_run = ProviderDownloadRun(
        download_run_id="quote-run-a",
        user_id="user-a",
        credential_id="credential-a",
        provider="eodhd",
        status="succeeded",
        returned_observation_ids=selection.member_ids,
        request_hash="quote-request-a",
    )
    quote_rows = tuple(
        {
            "isin": isin,
            "exchange": "XETRA",
            "code": code,
            "date": f"2026-01-0{day}",
            "adjusted_close": base + day,
        }
        for isin, code, base in (
            ("IE1", "AAA", 100),
            ("IE2", "BBB", 80),
            ("IE3", "CCC", 120),
        )
        for day in range(1, 5)
    )
    state = HostedApiState(
        projects_by_id={project.project_id: project},
        selections_by_id={selection.selection_id: selection},
        downloads_by_id={quote_run.download_run_id: quote_run},
        quote_rows_by_run_id={quote_run.download_run_id: quote_rows},
    )
    client = _client(state)

    request = {
        "metadata_selection_id": selection.selection_id,
        "quote_run_id": quote_run.download_run_id,
    }
    univariate = _json(client.post("/univariate-statistics/runs", headers=_headers(), json=request))
    repeated = _json(client.post("/univariate-statistics/runs", headers=_headers(), json=request))
    filtered = _json(
        client.post(
            "/univariate-filter",
            headers=_headers(),
            json={
                "source_run_id": univariate["run_id"],
                "predicates": [{"metric": "quote_observation_count", "operator": ">=", "value": 4}],
            },
        )
    )
    source = {"univariate_filter_selection_id": filtered["selection_id"]}
    plan = _json(client.post("/bivariate-statistics/plan", headers=_headers(), json=source))
    bivariate = _json(client.post("/bivariate-statistics/runs", headers=_headers(), json=source))
    pair_rows = _json(
        client.get(
            f"/bivariate-statistics/runs/{bivariate['run_id']}/results",
            headers=_headers(csrf=False),
        )
    )["items"]

    assert repeated == univariate
    assert univariate["status"] == "complete"
    assert filtered["input_count"] == filtered["selected_count"] == 3
    assert filtered["excluded_count"] == 0
    assert plan["theoretical_pair_count"] == 3
    assert plan["allowed"] is True
    assert len(pair_rows) == 3
    assert len({(row["left_id"], row["right_id"]) for row in pair_rows}) == 3
    assert (
        client.get(
            f"/univariate-statistics/runs/{univariate['run_id']}",
            headers=_headers("user-b", csrf=False),
        ).status_code
        == 200
    )


def test_account_deletion_removes_user_owned_api_state() -> None:
    client = _client()
    project = _json(client.post("/projects", headers=_headers(), json={"name": "Delete Me"}))
    selection = _json(
        client.post(
            "/selections",
            headers=_headers(),
            json={"project_id": project["project_id"], "name": "S", "member_ids": ["IE1"]},
        )
    )

    assert client.delete("/account", headers=_headers()).json() == {"status": "deleted"}
    assert client.get("/projects", headers=_headers(csrf=False)).json() == {"items": []}
    assert (
        client.get(
            f"/selections/{selection['selection_id']}", headers=_headers(csrf=False)
        ).status_code
        == 404
    )
