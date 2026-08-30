from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from hosted_test_support import build_research_service, build_services

import portfell.hosted_api as hosted_api
from portfell.entitlements import ProviderDownloadRun
from portfell.hosted_api import (
    DEFAULT_LOCAL_WORKSPACE_USER_ID,
    ApiUser,
    HostedApiError,
    HostedApiState,
    ProjectRecord,
    SelectionRecord,
    create_app,
)
from portfell.hosted_api_state import LocalWorkspaceUserProvider
from portfell.hosted_postgres_request_scope import RequestScopedPostgresConnection
from portfell.hosted_research_workflow import ResearchRun, UnivariateSelection
from portfell.market_source.contracts import EodQuote, Listing, ListingKey
from portfell.market_source.gateway import MarketDataGateway, MarketDataSnapshot


@dataclass
class _FixtureMarketGateway:
    quotes: tuple[EodQuote, ...]

    def read_snapshot(
        self, keys: tuple[ListingKey, ...], *, start: date, end: date
    ) -> MarketDataSnapshot:
        selected = set(keys)
        return MarketDataSnapshot(
            listings=tuple(Listing(key, key.code, "ETF", "Germany", "EUR", True) for key in keys),
            quotes=tuple(
                quote
                for quote in self.quotes
                if quote.key in selected and start <= quote.trade_date <= end
            ),
            dividends=(),
            splits=(),
        )


def _market_gateway(rows: tuple[dict[str, object], ...]) -> MarketDataGateway:
    gateway = _FixtureMarketGateway(
        tuple(
            EodQuote(
                ListingKey(str(row["isin"]), str(row["exchange"]), str(row["code"])),
                date.fromisoformat(str(row["date"])),
                Decimal(str(row["adjusted_close"])),
                None,
                None,
            )
            for row in rows
        )
    )
    return cast(MarketDataGateway, gateway)


def _client(
    state: HostedApiState | None = None, *, market_gateway: MarketDataGateway | None = None
) -> TestClient:
    resolved_state = state or HostedApiState()
    return TestClient(
        create_app(
            resolved_state,
            services=build_services(resolved_state, market_gateway=market_gateway),
        )
    )


def _test_app(state: HostedApiState | None = None, **kwargs: object) -> Any:
    resolved_state = state or HostedApiState()
    return create_app(resolved_state, services=build_services(resolved_state), **kwargs)


def _headers(
    user_id: str = DEFAULT_LOCAL_WORKSPACE_USER_ID,
    *,
    csrf: bool = False,
    idempotency: str | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    if idempotency is not None:
        headers["Idempotency-Key"] = idempotency
    return headers


def _json(response: Any) -> dict[str, Any]:
    payload = response.json()
    assert isinstance(payload, dict)
    return cast("dict[str, Any]", payload)


class _ScopedConnection:
    def __init__(self) -> None:
        self.statements: list[tuple[str, tuple[object, ...]]] = []
        self.committed = False
        self.closed = False

    def execute(self, sql: str, parameters: tuple[object, ...] = ()) -> None:
        self.statements.append((sql, parameters))

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        raise AssertionError("successful request must not roll back")

    def close(self) -> None:
        self.closed = True


def test_local_workspace_requires_no_authentication_or_csrf() -> None:
    client = _client()

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/auth/google/start").status_code == 404
    assert client.post("/projects", json={"name": "Core"}).status_code == 200


def test_hosted_api_requires_an_explicit_service_composition() -> None:
    with pytest.raises(HostedApiError, match="hosted_services_must_be_explicit"):
        create_app()


def test_postgres_composition_excludes_legacy_user_quote_routes() -> None:
    application = _test_app()

    assert "/quote-runs" not in application.openapi()["paths"]


def test_local_workspace_user_provider_is_stable_and_server_owned() -> None:
    provider = LocalWorkspaceUserProvider(user_id="00000000-0000-5000-8000-000000000002")
    first = provider.current_user()
    second = provider.current_user()

    assert first == ApiUser(user_id="00000000-0000-5000-8000-000000000002")
    assert second == first


def test_postgres_runtime_requires_its_explicit_runtime_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PORTFELL_HOSTED_AUTHORITY", "postgres")

    with pytest.raises(HostedApiError, match="postgres_hosted_runtime_configuration_required"):
        hosted_api.create_runtime_app()


def test_postgres_runtime_composes_without_a_local_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """postgres:
  app:
    host: postgres
    port: 5432
    database: portfell
    schema: portfell_app
    role: portfell_app
    password_secret: PORTFELL_DATABASE_PASSWORD_FILE
  market:
    host: market-postgres
    port: 5432
    database: xetra_loader
    schema: xetra_loader
    role: portfell
    member_of: portfell_app
    tables:
      - listings
      - eod_quotes
      - dividends
      - splits
    password_secret: PORTFELL_MARKET_DATABASE_PASSWORD_FILE
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("PORTFELL_HOSTED_AUTHORITY", "postgres")
    monkeypatch.setenv("PORTFELL_DATABASE_URL", "postgresql://portfell_app@postgres:5432/portfell")
    monkeypatch.setenv(
        "PORTFELL_MARKET_DATABASE_URL", "postgresql://portfell@market-postgres:5432/xetra_loader"
    )
    monkeypatch.setenv("PORTFELL_CONFIG_PATH", str(config_path))
    application = hosted_api.create_runtime_app()

    assert application.state.portfell_state.workspace_store is None


def test_database_runtime_requires_explicit_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PORTFELL_HOSTED_AUTHORITY", raising=False)
    monkeypatch.setenv("PORTFELL_DATABASE_URL", "postgresql://portfell_app@postgres:5432/portfell")

    with pytest.raises(HostedApiError, match="postgres_hosted_authority_required"):
        hosted_api.create_runtime_app()


def test_runtime_rejects_the_removed_local_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PORTFELL_HOSTED_AUTHORITY", "local")
    monkeypatch.setenv("PORTFELL_DATABASE_URL", "postgresql://portfell_app@postgres:5432/portfell")

    with pytest.raises(HostedApiError, match="postgres_hosted_authority_required"):
        hosted_api.create_runtime_app()


def test_api_uses_injected_current_user_provider() -> None:
    provider = LocalWorkspaceUserProvider(user_id="00000000-0000-5000-8000-000000000002")
    client = TestClient(_test_app(current_user_provider=provider))

    assert client.get("/health").status_code == 200


def test_provider_credential_routes_are_not_exposed() -> None:
    application = _test_app()

    assert "/credentials/eodhd" not in application.openapi()["paths"]
    client = TestClient(application)
    assert client.get("/credentials/eodhd").status_code == 404


def test_postgres_composition_exposes_the_durable_status_event_stream() -> None:
    scope = RequestScopedPostgresConnection(_ScopedConnection)

    application = _test_app(request_scope=scope)

    assert "/status-events" in application.openapi()["paths"]


def test_api_wraps_requests_in_an_authenticated_postgres_transaction() -> None:
    connections: list[_ScopedConnection] = []

    def connect() -> _ScopedConnection:
        connection = _ScopedConnection()
        connections.append(connection)
        return connection

    scope = RequestScopedPostgresConnection(connect)

    response = TestClient(_test_app(request_scope=scope)).get("/health")

    assert response.status_code == 200
    assert connections[0].committed
    assert connections[0].closed
    assert connections[0].statements[0][1][1] == DEFAULT_LOCAL_WORKSPACE_USER_ID


def test_api_provisions_the_server_principal_inside_the_postgres_request_scope() -> None:
    connections: list[_ScopedConnection] = []
    provisioned: list[str] = []

    def connect() -> _ScopedConnection:
        connection = _ScopedConnection()
        connections.append(connection)
        return connection

    response = TestClient(
        _test_app(
            request_scope=RequestScopedPostgresConnection(connect),
            ensure_user=provisioned.append,
        )
    ).get("/health")

    assert response.status_code == 200
    assert provisioned == [DEFAULT_LOCAL_WORKSPACE_USER_ID]
    assert connections[0].statements[0][1][1] == provisioned[0]


def test_workflow_starts_with_only_metadata_ready() -> None:
    client = _client()

    workflow = _json(client.get("/workflow"))

    assert workflow == {
        "stages": {
            "metadata_builder": {"status": "ready"},
            "univariate_statistics": {"status": "locked"},
            "bivariate_statistics": {"status": "locked"},
            "multivariate_statistics": {"status": "locked"},
        }
    }


def test_legacy_direct_download_routes_are_not_exposed() -> None:
    client = _client()
    plan_response = client.post(
        "/downloads/plan", headers=_headers(), json={"symbols": ["AAA.XETRA"]}
    )
    run_response = client.post(
        "/downloads/run", headers=_headers(), json={"symbols": ["AAA.XETRA"]}
    )
    assert plan_response.status_code == 404
    assert run_response.status_code == 404
    assert client.get("/datasets", headers=_headers(csrf=False)).status_code == 404


def test_metadata_builder_options_and_project_creation_use_all_isins_reference() -> None:
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

    options = _json(client.get("/metadata-builder/options", headers=_headers(csrf=False)))
    rejected = client.post(
        "/metadata-builder",
        headers=_headers(idempotency="metadata-project-1"),
        json={
            "exchange": "XETRA",
            "name": "UCITS ETF",
            "instrument_type": "ETF",
            "country": "IE",
            "currency": "EUR",
        },
    )
    state.metadata_revisions_by_user["00000000-0000-5000-8000-000000000001"] = "revision-1"
    ready_options = _json(client.get("/metadata-builder/options", headers=_headers(csrf=False)))
    created = _json(
        client.post(
            "/metadata-builder",
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
            "/metadata-builder",
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
        "metadata_ready": False,
        "country": [{"value": "IE", "isin_count": 1}, {"value": "US", "isin_count": 1}],
        "currency": [{"value": "EUR", "isin_count": 1}, {"value": "USD", "isin_count": 1}],
        "exchange": [{"value": "NYSE", "isin_count": 1}, {"value": "XETRA", "isin_count": 1}],
        "instrument_type": [
            {"value": "Common Stock", "isin_count": 1},
            {"value": "ETF", "isin_count": 1},
        ],
    }
    assert rejected.status_code == 422
    assert _json(rejected)["detail"]["code"] == "metadata_required"
    assert ready_options == {**options, "metadata_ready": True}
    assert created == repeated
    assert created["project"]["name"] == "xetra_ucits_etf_etf_ie_eur"
    assert "name_" not in created["project"]["name"]
    assert created["selection"]["member_ids"] == ["IE1:XETRA:AAA"]
    assert created["selected_count"] == 1
    assert "initial_fill" not in created
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
    assert str(UUID(project["project_id"])) == project["project_id"]
    assert str(UUID(selection["selection_id"])) == selection["selection_id"]
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


def test_project_context_requires_an_explicit_current_project_selection() -> None:
    alpha = ProjectRecord(
        project_id="00000000-0000-5000-8000-000000000021",
        user_id=DEFAULT_LOCAL_WORKSPACE_USER_ID,
        name="alpha",
    )
    core = ProjectRecord(
        project_id="00000000-0000-5000-8000-000000000022",
        user_id=DEFAULT_LOCAL_WORKSPACE_USER_ID,
        name="Core",
    )
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
    assert default_context["current_project_id"] is None
    assert default_context["current_project"] is None
    assert state.current_project_id_by_user == {}
    assert selected_context["current_project_id"] == core.project_id
    assert empty_workflow == {
        "stages": {
            "metadata_builder": {"status": "ready"},
            "univariate_statistics": {"status": "locked"},
            "bivariate_statistics": {"status": "locked"},
            "multivariate_statistics": {"status": "locked"},
        }
    }
    assert deleted == {"project_id": core.project_id, "status": "deleted"}
    assert fallback_context["current_project_id"] is None
    missing = client.put(
        "/project-context/current-project",
        json={"project_id": "00000000-0000-5000-8000-000000000023"},
    )
    assert missing.status_code == 404
    legacy = client.put("/project-context/current-project", json={"project_id": "project_core"})
    assert legacy.status_code == 422


def test_project_metadata_builder_restores_saved_field_values(
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
    state.metadata_revisions_by_user["00000000-0000-5000-8000-000000000001"] = "revision-1"
    client = _client(state)
    created = _json(
        client.post(
            "/metadata-builder",
            headers=_headers(idempotency="metadata-builder-project-values"),
            json={
                "exchange": "XETRA",
                "name": "UCITS ETF",
                "instrument_type": "ETF",
                "country": "IE",
                "currency": "EUR",
            },
        )
    )

    restored = _json(client.get(f"/projects/{created['project']['project_id']}/metadata-builder"))

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


def test_metadata_builder_page_view_is_versioned_and_revalidates(
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
    state.metadata_revisions_by_user[DEFAULT_LOCAL_WORKSPACE_USER_ID] = "revision-1"
    client = _client(state)
    created = _json(
        client.post(
            "/metadata-builder",
            headers=_headers(idempotency="metadata-builder-page-view"),
            json={"exchange": "XETRA"},
        )
    )
    project_id = created["project"]["project_id"]

    response = client.get(f"/projects/{project_id}/views/metadata-builder")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "private, max-age=0, must-revalidate"
    assert response.json()["contract_version"] == 1
    assert response.json()["project_id"] == project_id
    assert response.json()["summary"]["criteria"]["selected_count"] == 1
    etag = response.headers["etag"]
    not_modified = client.get(
        f"/projects/{project_id}/views/metadata-builder", headers={"If-None-Match": etag}
    )
    assert not_modified.status_code == 304
    assert not_modified.headers["etag"] == etag


@pytest.mark.parametrize(
    ("module", "path", "section"),
    (
        ("univariate_statistics", "univariate-statistics", "results"),
        ("bivariate_statistics", "bivariate-statistics", "correlation_matrix"),
        ("multivariate_statistics", "multivariate-statistics", "performance"),
    ),
)
def test_analytical_page_views_are_compact_authorized_and_revalidate(
    module: str, path: str, section: str
) -> None:
    client = _client()
    project_id = _json(client.post("/projects", json={"name": "Core"}))["project_id"]

    response = client.get(f"/projects/{project_id}/views/{path}")

    assert response.status_code == 200
    body = _json(response)
    assert body["module"] == module
    assert body["project_id"] == project_id
    assert body["sections"][section]["available"] is False
    assert response.headers["cache-control"] == "private, max-age=0, must-revalidate"
    repeated = client.get(
        f"/projects/{project_id}/views/{path}", headers={"If-None-Match": response.headers["etag"]}
    )
    assert repeated.status_code == 304
    assert repeated.content == b""
    assert (
        client.get(f"/projects/00000000-0000-5000-8000-000000000099/views/{path}").status_code
        == 404
    )


def test_project_context_is_empty_without_projects() -> None:
    client = _client()

    first = client.get("/project-context")

    assert _json(first) == {
        "current_project_id": None,
        "current_project": None,
        "projects": [],
    }
    assert first.headers["cache-control"] == "private, max-age=0, must-revalidate"
    assert first.headers["etag"]
    repeated = client.get("/project-context", headers={"If-None-Match": first.headers["etag"]})
    assert repeated.status_code == 304
    assert repeated.content == b""


def test_projects_listing_keeps_explicit_statistics_smoke_project() -> None:
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

    assert _json(client.get("/projects", headers=_headers(csrf=False))) == {
        "items": [
            {
                "project_id": project["project_id"],
                "name": "Statistics Smoke",
                "selection_id": selection["selection_id"],
                "selected_count": 2,
                "data_loaded": False,
            }
        ]
    }


def test_univariate_selection_metrics_expose_numerical_contract() -> None:
    payload = _json(_client().get("/univariate-selection/metrics", headers=_headers(csrf=False)))
    metrics = {row["metric"]: row for row in payload["items"]}

    assert metrics["annualized_volatility"]["unit"] == "ratio"
    assert metrics["quote_observation_count"]["unit"] == "count"
    assert metrics["expected_shortfall"]["operators"] == ["=", "!=", ">", ">=", "<", "<="]


def test_scoped_research_runs_filter_and_build_unique_pairs() -> None:
    project = ProjectRecord(
        project_id="00000000-0000-5000-8000-000000000031",
        user_id=DEFAULT_LOCAL_WORKSPACE_USER_ID,
        name="Research",
    )
    selection = SelectionRecord(
        selection_id="metadata-selection-a",
        user_id=DEFAULT_LOCAL_WORKSPACE_USER_ID,
        project_id=project.project_id,
        name="Research",
        member_ids=("IE1:XETRA:AAA", "IE2:XETRA:BBB", "IE3:XETRA:CCC"),
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
    )
    state.metadata_revisions_by_user[DEFAULT_LOCAL_WORKSPACE_USER_ID] = "metadata-revision-a"
    client = _client(state, market_gateway=_market_gateway(quote_rows))

    request = {"metadata_selection_id": selection.selection_id}
    univariate = _json(client.post("/univariate-statistics/runs", headers=_headers(), json=request))
    repeated = _json(client.post("/univariate-statistics/runs", headers=_headers(), json=request))
    univariate_status = _json(
        client.get(f"/univariate-statistics/runs/{univariate['run_id']}", headers=_headers())
    )
    filtered = _json(
        client.post(
            "/univariate-selection",
            headers=_headers(),
            json={
                "source_run_id": univariate["run_id"],
                "predicates": [{"metric": "quote_observation_count", "operator": ">=", "value": 4}],
            },
        )
    )
    source = {"univariate_selection_id": filtered["selection_id"]}
    plan = _json(client.post("/bivariate-statistics/plan", headers=_headers(), json=source))
    bivariate = _json(client.post("/bivariate-statistics/runs", headers=_headers(), json=source))
    pair_rows = _json(
        client.get(
            f"/bivariate-statistics/runs/{bivariate['run_id']}/results",
            headers=_headers(csrf=False),
        )
    )["items"]
    summary = _json(
        client.get(
            f"/bivariate-statistics/runs/{bivariate['run_id']}/summary",
            headers=_headers(csrf=False),
        )
    )
    pearson_matrix = _json(
        client.get(
            f"/bivariate-statistics/runs/{bivariate['run_id']}/correlation-matrix?metric=pearson",
            headers=_headers(csrf=False),
        )
    )
    spearman_matrix = _json(
        client.get(
            f"/bivariate-statistics/runs/{bivariate['run_id']}/correlation-matrix?metric=spearman",
            headers=_headers(csrf=False),
        )
    )
    downside_matrix = _json(
        client.get(
            f"/bivariate-statistics/runs/{bivariate['run_id']}/correlation-matrix?metric=downside",
            headers=_headers(csrf=False),
        )
    )
    tail_dependence_matrix = _json(
        client.get(
            f"/bivariate-statistics/runs/{bivariate['run_id']}/correlation-matrix?metric=lower_tail_dependence",
            headers=_headers(csrf=False),
        )
    )
    coexceedance_matrix = _json(
        client.get(
            f"/bivariate-statistics/runs/{bivariate['run_id']}/correlation-matrix?metric=tail_coexceedance_rate",
            headers=_headers(csrf=False),
        )
    )
    tail_scatter = _json(
        client.get(
            f"/bivariate-statistics/runs/{bivariate['run_id']}/tail-risk-scatter",
            headers=_headers(csrf=False),
        )
    )

    assert repeated["run_id"] == univariate["run_id"]
    assert univariate_status["status"] == "complete"
    assert filtered["input_count"] == filtered["selected_count"] == 3
    assert filtered["excluded_count"] == 0
    assert plan["theoretical_pair_count"] == 3
    assert plan["allowed"] is True
    assert len(pair_rows) == 3
    assert len({(row["left_id"], row["right_id"]) for row in pair_rows}) == 3
    assert summary["pair_count"] == 3
    assert summary["pearson_diagnostics"]["high_70_pairs"] >= 0
    assert "most_correlated_listing" in summary["pearson_diagnostics"]
    assert summary["spearman_diagnostics"]["cluster_count"] >= 0
    assert summary["downside_diagnostics"]["minimum_joint_negative_days"] >= 0
    assert summary["tail_dependence_diagnostics"]["high_30_pairs"] >= 0
    assert "worst_pair" in summary["tail_dependence_diagnostics"]
    assert summary["coexceedance_diagnostics"]["independence_baseline"] == 0.0025
    assert summary["coexceedance_diagnostics"]["high_1_pairs"] >= 0
    assert summary["rolling_correlation_diagnostics"]["high_threshold_pairs"] >= 0
    assert summary["drawdown_overlap_diagnostics"]["cluster_count"] >= 0
    assert pearson_matrix["values"][0][0] is None
    assert isinstance(pearson_matrix["values"][0][1], float)
    assert isinstance(spearman_matrix["values"][0][1], float)
    assert isinstance(downside_matrix["values"][0][1], float)
    assert isinstance(tail_dependence_matrix["values"][0][1], float)
    assert isinstance(coexceedance_matrix["values"][0][1], float)
    assert tail_scatter["pair_count"] == 3
    assert tail_scatter["points"][0]["tail_dependence"] >= 0.0
    assert tail_scatter["points"][0]["coexceedance_rate"] >= 0.0
    assert tail_scatter["diagnostics"]["pareto_best_pair_count"] >= 1
    assert "tail_concentration" in tail_scatter["diagnostics"]
    assert set(summary["metrics"]) >= {
        "pearson_correlation",
        "downside_correlation",
        "lower_tail_dependence",
        "rolling_correlation_stability",
        "drawdown_overlap_rate",
    }
    assert (
        client.get(
            f"/univariate-statistics/runs/{univariate['run_id']}",
            headers=_headers("user-b", csrf=False),
        ).status_code
        == 200
    )


def test_bivariate_statistics_read_quotes_from_the_market_source_snapshot() -> None:
    """Bivariate runs read the selected source snapshot, not a local quote lake."""
    project = ProjectRecord(
        project_id="00000000-0000-5000-8000-000000000041",
        user_id=DEFAULT_LOCAL_WORKSPACE_USER_ID,
        name="Research",
    )
    selection = SelectionRecord(
        selection_id="metadata-selection-a",
        user_id=DEFAULT_LOCAL_WORKSPACE_USER_ID,
        project_id=project.project_id,
        name="Research",
        member_ids=("IE1:XETRA:AAA", "IE2:XETRA:BBB"),
    )
    quote_run = ProviderDownloadRun(
        download_run_id="quote-run-a",
        user_id=DEFAULT_LOCAL_WORKSPACE_USER_ID,
        credential_id="credential-a",
        provider="eodhd",
        status="succeeded",
        returned_observation_ids=selection.member_ids,
        request_hash="quote-request-a",
    )
    statistic_rows = tuple(
        {"isin": isin, "exchange": "XETRA", "code": code}
        for isin, code in (("IE1", "AAA"), ("IE2", "BBB"))
    )
    univariate = ResearchRun(
        "univariate-run-a",
        DEFAULT_LOCAL_WORKSPACE_USER_ID,
        "source-a",
        "complete",
        statistic_rows,
        2,
        2,
    )
    filtered = UnivariateSelection(
        "univariate-selection-a",
        DEFAULT_LOCAL_WORKSPACE_USER_ID,
        univariate.run_id,
        selection.member_ids,
        (),
        statistic_rows,
        2,
    )
    quote_rows = tuple(
        {
            "isin": isin,
            "exchange": "XETRA",
            "code": code,
            "date": f"2026-01-0{day}",
            "adjusted_close": base + day,
        }
        for isin, code, base in (("IE1", "AAA", 100), ("IE2", "BBB", 80))
        for day in range(1, 5)
    )
    state = HostedApiState(
        projects_by_id={project.project_id: project},
        selections_by_id={selection.selection_id: selection},
        downloads_by_id={quote_run.download_run_id: quote_run},
        univariate_runs_by_id={univariate.run_id: univariate},
        univariate_selections_by_id={filtered.selection_id: filtered},
        quote_run_by_univariate_run_id={univariate.run_id: quote_run.download_run_id},
    )
    market_gateway = _market_gateway(quote_rows)
    client = _client(state, market_gateway=market_gateway)

    run = _json(
        client.post(
            "/bivariate-statistics/runs",
            headers=_headers(),
            json={"univariate_selection_id": filtered.selection_id},
        )
    )
    research = build_research_service(state, market_gateway=market_gateway)
    research.complete_bivariate(DEFAULT_LOCAL_WORKSPACE_USER_ID, filtered.selection_id)
    completed = _json(
        client.get(f"/bivariate-statistics/runs/{run['run_id']}", headers=_headers(csrf=False))
    )
    matrix = _json(
        client.get(
            f"/bivariate-statistics/runs/{run['run_id']}/covariance-matrix",
            headers=_headers(csrf=False),
        )
    )

    assert completed["status"] == "complete"
    assert completed["total"] == 1
    assert matrix["observation_count"] == 3
    assert [row["label"] for row in matrix["labels"]] == ["AAA.XETRA", "BBB.XETRA"]
    assert len(matrix["values"]) == len(matrix["values"][0]) == 2
    assert matrix["values"][0][0] is None
    assert matrix["values"][1] == [None, None]
    assert isinstance(matrix["values"][0][1], float)


def test_legacy_account_deletion_route_is_not_exposed() -> None:
    client = _client()
    assert client.delete("/account", headers=_headers()).status_code == 404
