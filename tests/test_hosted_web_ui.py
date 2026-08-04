from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / "apps" / "web" / "server.js"


def test_server_only_handles_auth_proxy_health_and_vite_assets() -> None:
    source = SERVER.read_text(encoding="utf-8")
    for expected in (
        'requestUrl.pathname === "/health"',
        'requestUrl.pathname.startsWith("/api/")',
        'requestUrl.pathname === "/auth/google/start"',
        'requestUrl.pathname === "/auth/google/callback"',
        'requestUrl.pathname.startsWith("/assets/")',
        'path.join(DIST_ROOT, "index.html")',
    ):
        assert expected in source
    for removed in (
        "renderA" + "ppShell",
        "renderAuthen" + "ticatedShell",
        "bindAuthenticatedHandlers",
        "statisticsSteps",
        "window.camovarApi",
    ):
        assert removed not in source
