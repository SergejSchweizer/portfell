from __future__ import annotations

import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = REPOSITORY_ROOT / "apps" / "web"


def test_react_scaffold_exposes_vite_typescript_entrypoints() -> None:
    package = json.loads((WEB_ROOT / "package.json").read_text(encoding="utf-8"))

    assert package["scripts"]["dev"] == "vite"
    assert package["scripts"]["build"] == "vite build"
    assert package["scripts"]["typecheck"] == "tsc -p tsconfig.json --noEmit"
    assert "react" in package["dependencies"]
    assert "react-dom" in package["dependencies"]
    assert "vite" in package["devDependencies"]
    assert "typescript" in package["devDependencies"]

    for relative in (
        "index.html",
        "tsconfig.json",
        "tsconfig.node.json",
        "vite.config.ts",
        "playwright.config.ts",
        "src/main.tsx",
        "src/app.tsx",
        "src/routes.tsx",
        "src/env.ts",
        "src/api/client.ts",
        "src/pages/health.tsx",
        "src/pages/login-gate.tsx",
        "src/pages/authenticated-shell.tsx",
        "src/compat/legacy-shell.tsx",
        "src/components/button.tsx",
        "src/components/status-badge.tsx",
        "src/components/panel.tsx",
        "src/components/progress-stepper.tsx",
        "src/components/empty-state.tsx",
        "src/components/loading-state.tsx",
        "src/catalogue/ComponentCatalogue.tsx",
        "src/shell/login-gate.tsx",
        "src/shell/authenticated-shell.tsx",
        "src/shell/frame.tsx",
        "src/hooks/use-resource.ts",
        "src/pages/data.tsx",
        "src/pages/metadata.tsx",
        "src/pages/univariate.tsx",
        "src/pages/filter.tsx",
        "src/pages/diversification.tsx",
        "src/pages/portfolio.tsx",
        "src/pages/validation.tsx",
        "src/pages/report.tsx",
        "src/pages/stress.tsx",
        "src/pages/recommendation.tsx",
        "src/pages/fixture-preview.tsx",
        "src/pages/settings.tsx",
        "src/pages/account.tsx",
        "tests/ui.spec.ts",
    ):
        assert (WEB_ROOT / relative).exists()


def test_react_scaffold_defines_health_authenticated_shell_and_compatibility_routes() -> None:
    routes = (WEB_ROOT / "src" / "routes.tsx").read_text(encoding="utf-8")
    app = (WEB_ROOT / "src" / "app.tsx").read_text(encoding="utf-8")
    env = (WEB_ROOT / "src" / "env.ts").read_text(encoding="utf-8")
    package = json.loads((WEB_ROOT / "package.json").read_text(encoding="utf-8"))

    assert 'path: "/health"' in routes
    assert 'path: "/shell"' in routes
    assert 'path: "/compat/legacy"' in routes
    assert 'path: "/catalogue"' in routes
    assert 'path: "/fixtures"' in routes
    assert "HealthPage" in routes
    assert "AuthenticatedShellPage" in routes
    assert "LegacyShellAdapter" in routes
    assert "ComponentCatalogue" in routes
    assert "FixturePreviewPage" in routes
    assert "StressPage" in routes
    assert "RecommendationPage" in routes
    assert "ShellFrame" in (WEB_ROOT / "src" / "shell" / "frame.tsx").read_text(encoding="utf-8")
    assert "const pathname = window.location.pathname" in app
    assert "matchRoute(pathname)" in app
    assert "routeTitle(pathname)" in app
    assert "route.shell" in app
    assert "VITE_CAMOVAR_API_BASE_URL" in env
    assert "VITE_CAMOVAR_AUTH_MODE" in env
    assert "VITE_CAMOVAR_UI_FIXTURE" in env
    assert "VITE_CAMOVAR_UI_FIXTURE_MODE" in env
    assert package["scripts"]["e2e"] == "playwright test"
    assert 'requestJson<ApiProjects>("/api/projects")' in (
        WEB_ROOT / "src" / "pages" / "data.tsx"
    ).read_text(encoding="utf-8")
    assert 'requestJson<ApiFieldOptions>("/api/metadata-filter/options")' in (
        WEB_ROOT / "src" / "pages" / "metadata.tsx"
    ).read_text(encoding="utf-8")
    assert 'requestJson<ApiUnivariateSummary>("/api/statistics/univariate/summary")' in (
        WEB_ROOT / "src" / "pages" / "univariate.tsx"
    ).read_text(encoding="utf-8")
    assert 'requestJson<SessionSnapshot>("/api/session")' in (
        WEB_ROOT / "src" / "shell" / "authenticated-shell.tsx"
    ).read_text(encoding="utf-8")
    assert "useResource(loadSessionSnapshot" in (
        WEB_ROOT / "src" / "shell" / "authenticated-shell.tsx"
    ).read_text(encoding="utf-8")
    browser_tests = (WEB_ROOT / "tests" / "ui.spec.ts").read_text(encoding="utf-8")
    for expected in (
        "/shell?fixture=free-key",
        "/data?fixture=free-key",
        "/metadata?fixture=free-key",
        "/univariate?fixture=statistics-complete",
        "/stress?fixture=stress-warning",
        "/recommendation?fixture=recommendation-ready",
    ):
        assert expected in browser_tests


def test_react_scaffold_dockerfile_copies_browser_build_sources() -> None:
    dockerfile = (WEB_ROOT / "Dockerfile").read_text(encoding="utf-8")

    for expected in (
        "COPY apps/web/index.html ./",
        "COPY apps/web/tsconfig.json ./",
        "COPY apps/web/tsconfig.node.json ./",
        "COPY apps/web/vite.config.ts ./",
        "COPY apps/web/src ./src",
        "COPY apps/web/design-tokens.json ./",
        "COPY apps/web/styles ./styles",
    ):
        assert expected in dockerfile
