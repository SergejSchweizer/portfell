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
    page = (WEB_ROOT / "src" / "pages" / "metadata-filter.tsx").read_text(
        encoding="utf-8"
    )
    assert "Fetch quotes" in page
    assert "postJson<LoadQuotesResponse>" in page
    assert '"/api/data/load-selected-isins"' in page
    assert page.index("<progress") < page.index("quote-fetch__action")
    assert page.index("quote-fetch__action") < page.index("Fetch quotes")


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
        path.read_text(encoding="utf-8")
        for path in (WEB_ROOT / "src").rglob("*")
        if path.is_file()
    )
    server = (WEB_ROOT / "server.js").read_text(encoding="utf-8")
    for token in forbidden:
        assert token not in source
        assert token not in server
