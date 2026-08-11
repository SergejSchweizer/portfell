from __future__ import annotations

import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPOSITORY_ROOT / "apps" / "web"


def test_web_has_exactly_four_research_modules() -> None:
    routes = (WEB_ROOT / "src" / "routes.tsx").read_text(encoding="utf-8")
    expected = (
        "/metadata-builder",
        "/univariate-statistics",
        "/bivariate-statistics",
        "/multivariate-statistics",
    )
    for route in expected:
        assert f'path: "{route}"' in routes
    assert routes.count('path: "/') == len(expected)


def test_workflow_pages_place_ingestion_actions_before_their_stage_controls() -> None:
    metadata_page = (WEB_ROOT / "src" / "pages" / "metadata-builder.tsx").read_text(
        encoding="utf-8"
    )
    frame = (WEB_ROOT / "src" / "shell" / "frame.tsx").read_text(encoding="utf-8")
    univariate_page = (WEB_ROOT / "src" / "pages" / "univariate-statistics.tsx").read_text(
        encoding="utf-8"
    )
    assert "Fetch all metadata" in metadata_page
    assert (
        metadata_page.index('<Panel title="Download Metadata">')
        < metadata_page.index('<Panel title="Metadata Builder">')
        < metadata_page.index('<Panel title="Historical Data">')
    )
    assert "EODHD key" in frame
    assert "Fetch all metadata" not in frame
    assert '"/univariate-statistics"' not in metadata_page
    assert '"portfell:workflow-updated"' in metadata_page
    assert "Initial fill progress" in metadata_page
    assert "Download Historical Data" not in metadata_page
    assert "loadInitialFill" in metadata_page
    assert "startQuoteRun" not in metadata_page
    assert "historicalDataUpdateLabel" not in metadata_page
    assert (
        "Historical data is refreshed automatically by the shared-data service" in univariate_page
    )
    assert "Update Historical Data" not in univariate_page
    assert "Download Historical Data" not in univariate_page
    assert "startQuoteRun" not in univariate_page
    assert "loadQuoteRun" not in univariate_page
    assert "quoteStatus" not in univariate_page
    assert "/quote-runs" not in univariate_page
    assert "!metadata.quote_run_id" not in univariate_page
    assert 'page.id === "univariate_statistics"' in frame
    assert "metricDefinitions" in univariate_page
    assert "univariate-group-card" in univariate_page
    assert "univariate-group-card__label" in univariate_page
    assert "univariate-equation" in univariate_page
    assert "univariate-notation" in univariate_page
    assert "dividendFrequency" in univariate_page
    assert 'className="univariate-statistic__tabs"' in univariate_page
    assert 'role="tablist"' in univariate_page
    assert 'activeStatisticTab === "dividends"' in univariate_page
    assert "portfell:univariate-statistic-order" not in univariate_page
    assert "onDragStart" not in univariate_page

    bivariate_page = (WEB_ROOT / "src" / "pages" / "bivariate-statistics.tsx").read_text(
        encoding="utf-8"
    )
    assert 'label: "Tail Dependence"' in bivariate_page
    assert 'label: "Co-exceedance"' in bivariate_page
    assert "lowerTailDependenceMatrix" in bivariate_page
    assert "tailCoexceedanceRateMatrix" in bivariate_page


def test_vite_build_is_the_canonical_web_runtime() -> None:
    package = json.loads((WEB_ROOT / "package.json").read_text(encoding="utf-8"))
    dockerfile = (WEB_ROOT / "Dockerfile").read_text(encoding="utf-8")
    server = (WEB_ROOT / "server.js").read_text(encoding="utf-8")
    assert package["scripts"]["build"] == "vite build"
    assert package["scripts"]["typecheck"] == "tsc -p tsconfig.json --noEmit"
    assert "npm ci" in dockerfile
    assert "npm run build" in dockerfile
    assert "COPY --from=build /app/dist ./dist" in dockerfile
    assert "dist" in server


def test_old_web_surfaces_are_absent() -> None:
    forbidden = (
        "compat/" + "legacy",
        "Legacy" + "Shell",
        "render" + "AppShell",
        "renderAuthenticated" + "Shell",
    )
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in (WEB_ROOT / "src").rglob("*") if path.is_file()
    )
    server = (WEB_ROOT / "server.js").read_text(encoding="utf-8")
    for token in forbidden:
        assert token not in source
        assert token not in server


def test_three_module_ui_uses_canonical_server_owned_workflow_contracts() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in (WEB_ROOT / "src").rglob("*") if path.is_file()
    )
    hosted_api = (REPOSITORY_ROOT / "src" / "portfell" / "hosted_api.py").read_text(
        encoding="utf-8"
    )

    for endpoint in (
        "/api/workflow",
        "/api/metadata/fetch-all",
        "/api/metadata-builder",
        "/api/projects/${encodeURIComponent(projectId)}/initial-fill",
        "/api/univariate-statistics/runs",
        "/api/bivariate-statistics/plan",
        "/api/bivariate-statistics/runs",
    ):
        assert endpoint in source

    for removed in (
        "/metadata-builder/fetch-all-metadata",
        "/metadata-builder/projects",
        "/data/load-selected-isins",
        "/statistics/univariate/summary",
        "/statistics/{statistics_kind}/compute",
    ):
        assert removed not in hosted_api

    frame = (WEB_ROOT / "src" / "shell" / "frame.tsx").read_text(encoding="utf-8")
    sidebar = (WEB_ROOT / "src" / "shell" / "project-sidebar.tsx").read_text(encoding="utf-8")
    assert "ProjectSidebar" in frame
    assert "workflowPages" in sidebar
    assert 'aria-disabled="true"' in sidebar
    assert not (WEB_ROOT / "src" / "shell" / "authenticated-shell.tsx").exists()


def test_project_context_client_contracts_precede_sidebar_rendering() -> None:
    client = (WEB_ROOT / "src" / "api" / "client.ts").read_text(encoding="utf-8")
    contracts = (WEB_ROOT / "src" / "contracts.ts").read_text(encoding="utf-8")
    sidebar_specification = WEB_ROOT.parents[1] / "docs" / "ui" / "layout" / "sidebar.md"

    for endpoint in (
        "/api/project-context",
        "/api/project-context/current-project",
        "/api/projects/${encodeURIComponent(projectId)}/workflow",
        "/api/projects/${encodeURIComponent(projectId)}/metadata-builder",
    ):
        assert endpoint in client
    for contract in ("ApiProjectSummary", "ApiProjectContext", "ApiProjectMetadataBuilder"):
        assert f"export type {contract}" in contracts
    assert sidebar_specification.exists()


def test_project_switch_resets_all_three_module_local_workflow_states() -> None:
    for page_name in (
        "metadata-builder.tsx",
        "univariate-statistics.tsx",
        "bivariate-statistics.tsx",
    ):
        page = (WEB_ROOT / "src" / "pages" / page_name).read_text(encoding="utf-8")
        assert 'window.addEventListener("portfell:project-updated"' in page


def test_metadata_builder_restores_saved_project_criteria() -> None:
    page = (WEB_ROOT / "src" / "pages" / "metadata-builder.tsx").read_text(encoding="utf-8")

    assert "loadProjectContext" in page
    assert "loadProjectCriteria" in page
    assert "setExchange(criteria.exchange)" in page
    assert "setInstrumentType(criteria.instrument_type)" in page
    assert "setCountry(criteria.country)" in page
    assert "setCurrency(criteria.currency)" in page
    assert "setName(criteria.name)" in page


def test_metadata_refresh_uses_the_operations_credential_not_a_browser_key() -> None:
    context = (WEB_ROOT / "src" / "shell" / "metadata-fetch-context.tsx").read_text(
        encoding="utf-8"
    )

    assert 'postJson<ApiMetadataFetch>("/api/metadata/fetch-all", {})' in context
    assert (
        'await postJson("/api/credentials/eodhd", { provider_key: providerKey.trim() })'
        not in context
    )
    assert 'setProviderKey("")' not in context


def test_metadata_header_uses_masked_saved_credential_without_browser_secret_persistence() -> None:
    frame = (WEB_ROOT / "src" / "shell" / "frame.tsx").read_text(encoding="utf-8")
    context = (WEB_ROOT / "src" / "shell" / "metadata-fetch-context.tsx").read_text(
        encoding="utf-8"
    )
    client = (WEB_ROOT / "src" / "api" / "client.ts").read_text(encoding="utf-8")

    assert "loadEodhdCredentialStatus" in context
    assert "loadEodhdCredentialValue" in context
    assert "setProviderKey(savedProviderKey.data.provider_key)" in context
    assert "Saved: {maskedCredentialLabel}" in frame
    assert "if (fetching) return;" in context
    assert 'setProviderKey("")' not in context
    assert 'type="text"' in frame
    assert 'requestJson<ApiCredentialStatus>("/api/credentials/eodhd")' in client
    assert 'requestJson<ApiCredentialValue>("/api/credentials/eodhd/value")' in client


def test_post_requests_support_browsers_without_crypto_random_uuid() -> None:
    client = (WEB_ROOT / "src" / "api" / "client.ts").read_text(encoding="utf-8")

    assert "function createIdempotencyKey" in client
    assert "globalThis.crypto?.randomUUID" in client
    assert '"Idempotency-Key": createIdempotencyKey()' in client


def test_metadata_panel_uses_the_historical_data_progress_status_action_layout() -> None:
    frame = (WEB_ROOT / "src" / "shell" / "frame.tsx").read_text(encoding="utf-8")
    page = (WEB_ROOT / "src" / "pages" / "metadata-builder.tsx").read_text(encoding="utf-8")
    context = (WEB_ROOT / "src" / "shell" / "metadata-fetch-context.tsx").read_text(
        encoding="utf-8"
    )
    styles = (WEB_ROOT / "styles" / "app.css").read_text(encoding="utf-8")

    assert 'fetching ? <progress className="metadata-fetch__progress"' not in frame
    assert 'id="metadata-progress"' in page
    assert "max={100} value={metadataProgress}" in page
    metadata_panel = page.index('<Panel title="Download Metadata">')
    progress = page.index("metadata-progress", metadata_panel)
    action = page.index("Fetch all metadata", metadata_panel)
    assert progress < action
    assert "metadataStatus" not in frame
    assert "metadataStatus" in page
    status_output = '<output className="status-line" aria-live="polite">{metadataStatus}</output>'
    assert progress < page.index(status_output, metadata_panel)
    assert page.index(status_output, metadata_panel) < action
    assert "loadMetadataFetchRun" in context
    assert "exchanges completed" in context
    assert ".metadata-fetch__progress { height: 4px;" in styles


def test_bivariate_facts_show_the_universe_aligned_data_period() -> None:
    page = (WEB_ROOT / "src" / "pages" / "bivariate-statistics.tsx").read_text(encoding="utf-8")
    contracts = (WEB_ROOT / "src" / "contracts.ts").read_text(encoding="utf-8")

    assert page.count("Aligned data period") >= 6
    assert "dataPeriod(matrix.date_start, matrix.date_end)" in page
    assert "lower_tail_dependence" in page
    assert "tail_coexceedance_rate" in page
    assert "TailRiskScatter" in page
    assert "Tail-Risk Scatter" in page
    assert contracts.count("date_start: string;") >= 4
    assert contracts.count("date_end: string;") >= 4


def test_metadata_builder_refreshes_the_sidebar_project_context_and_decodes_api_errors() -> None:
    page = (WEB_ROOT / "src" / "pages" / "metadata-builder.tsx").read_text(encoding="utf-8")
    frame = (WEB_ROOT / "src" / "shell" / "frame.tsx").read_text(encoding="utf-8")
    client = (WEB_ROOT / "src" / "api" / "client.ts").read_text(encoding="utf-8")

    assert 'window.dispatchEvent(new Event("portfell:workflow-updated"))' in page
    assert 'window.addEventListener("portfell:workflow-updated", refresh)' in frame
    assert 'typeof payload.detail === "string"' in client
    assert "payload.detail?.code" in client


def test_mobile_drawer_reuses_the_canonical_project_sidebar() -> None:
    frame = (WEB_ROOT / "src" / "shell" / "frame.tsx").read_text(encoding="utf-8")
    sidebar = (WEB_ROOT / "src" / "shell" / "project-sidebar.tsx").read_text(encoding="utf-8")
    styles = (WEB_ROOT / "styles" / "app.css").read_text(encoding="utf-8")

    assert frame.count("<ProjectSidebar") == 1
    assert 'aria-label="Open project navigation"' in frame
    assert 'aria-controls="project-navigation-drawer"' in frame
    assert 'document.body.style.overflow = "hidden"' in frame
    assert 'event.key === "Escape"' in frame
    assert "projectSelector?.disabled ? focusable()[0]" in frame
    assert "project-navigation-drawer" in sidebar
    assert "workflowPages" in sidebar
    assert "@media (max-width: 900px)" in styles
    assert "min(320px, 88vw)" in styles
    assert "prefers-reduced-motion" in styles
