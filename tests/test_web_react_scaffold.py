from __future__ import annotations

import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPOSITORY_ROOT / "apps" / "web"


def test_web_has_exactly_four_research_pages() -> None:
    routes = (WEB_ROOT / "src" / "routes.tsx").read_text(encoding="utf-8")
    expected = (
        "/metadata-filter",
        "/univariate-statistics",
        "/univariate-filter",
        "/bivariate-statistics",
    )
    for route in expected:
        assert f'path: "{route}"' in routes
    assert routes.count('path: "/') == len(expected)


def test_metadata_page_orders_progress_before_fetch_quotes_action() -> None:
    page = (WEB_ROOT / "src" / "pages" / "metadata-filter.tsx").read_text(encoding="utf-8")
    assert "Fetch quotes" in page
    assert "postJson" in page
    assert '"/api/quote-runs"' in page
    assert page.index("<progress") < page.index("quote-fetch__action")
    assert page.index("quote-fetch__action") < page.index("Fetch quotes")
    assert "loadQuoteRun" in page
    assert "provider tasks completed" in page
    assert "value={quoteProgress}" in page


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


def test_four_page_ui_uses_canonical_server_owned_workflow_contracts() -> None:
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in (WEB_ROOT / "src").rglob("*") if path.is_file()
    )
    hosted_api = (REPOSITORY_ROOT / "src" / "portfell" / "hosted_api.py").read_text(
        encoding="utf-8"
    )

    for endpoint in (
        "/api/workflow",
        "/api/metadata/fetch-all",
        "/api/metadata-filter",
        "/api/quote-runs",
        "/api/univariate-statistics/runs",
        "/api/univariate-filter",
        "/api/bivariate-statistics/plan",
        "/api/bivariate-statistics/runs",
    ):
        assert endpoint in source

    for removed in (
        "/metadata-filter/fetch-all-metadata",
        "/metadata-filter/projects",
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
        "/api/projects/${encodeURIComponent(projectId)}/metadata-filter",
    ):
        assert endpoint in client
    for contract in ("ApiProjectSummary", "ApiProjectContext", "ApiProjectMetadataFilter"):
        assert f"export type {contract}" in contracts
    assert sidebar_specification.exists()


def test_project_switch_resets_all_four_page_local_workflow_states() -> None:
    for page_name in (
        "metadata-filter.tsx",
        "univariate-statistics.tsx",
        "univariate-filter.tsx",
        "bivariate-statistics.tsx",
    ):
        page = (WEB_ROOT / "src" / "pages" / page_name).read_text(encoding="utf-8")
        assert 'window.addEventListener("portfell:project-updated"' in page


def test_metadata_filter_restores_saved_project_filter_values() -> None:
    page = (WEB_ROOT / "src" / "pages" / "metadata-filter.tsx").read_text(encoding="utf-8")

    assert "loadProjectContext" in page
    assert "loadProjectMetadataFilter" in page
    assert "setExchange(filter.exchange)" in page
    assert "setInstrumentType(filter.instrument_type)" in page
    assert "setCountry(filter.country)" in page
    assert "setCurrency(filter.currency)" in page
    assert "setName(filter.name)" in page


def test_metadata_refresh_keeps_the_entered_eodhd_key_in_the_header_field() -> None:
    frame = (WEB_ROOT / "src" / "shell" / "frame.tsx").read_text(encoding="utf-8")

    assert 'await postJson("/api/credentials/eodhd", { provider_key: providerKey.trim() })' in frame
    assert 'setProviderKey("")' not in frame


def test_header_uses_masked_saved_credential_without_browser_secret_persistence() -> None:
    frame = (WEB_ROOT / "src" / "shell" / "frame.tsx").read_text(encoding="utf-8")
    client = (WEB_ROOT / "src" / "api" / "client.ts").read_text(encoding="utf-8")

    assert "loadEodhdCredentialStatus" in frame
    assert "loadEodhdCredentialValue" in frame
    assert "setProviderKey(savedProviderKey.data.provider_key)" in frame
    assert "Saved: {credential.data.masked_label}" in frame
    assert "!providerKey.trim() && !hasSavedCredential" in frame
    assert 'setProviderKey("")' not in frame
    assert 'type="text"' in frame
    assert 'requestJson<ApiCredentialStatus>("/api/credentials/eodhd")' in client
    assert 'requestJson<ApiCredentialValue>("/api/credentials/eodhd/value")' in client


def test_post_requests_support_browsers_without_crypto_random_uuid() -> None:
    client = (WEB_ROOT / "src" / "api" / "client.ts").read_text(encoding="utf-8")

    assert "function createIdempotencyKey" in client
    assert "globalThis.crypto?.randomUUID" in client
    assert '"Idempotency-Key": createIdempotencyKey()' in client


def test_metadata_header_shows_progress_under_the_eodhd_key_while_fetching() -> None:
    frame = (WEB_ROOT / "src" / "shell" / "frame.tsx").read_text(encoding="utf-8")
    styles = (WEB_ROOT / "styles" / "app.css").read_text(encoding="utf-8")

    assert 'fetching ? <progress className="metadata-fetch__progress"' in frame
    assert "max={100} value={metadataProgress}" in frame
    assert "loadMetadataFetchRun" in frame
    assert "exchanges completed" in frame
    assert ".metadata-fetch__progress { height: 4px;" in styles


def test_metadata_filter_refreshes_the_sidebar_project_context_and_decodes_api_errors() -> None:
    page = (WEB_ROOT / "src" / "pages" / "metadata-filter.tsx").read_text(encoding="utf-8")
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
