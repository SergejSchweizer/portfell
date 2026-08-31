from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from portfell.dash_app.app import create_dash_app, mount_dash_app
from portfell.dash_app.components import (
    ChartCard,
    ControlBar,
    HistoryCard,
    KpiCard,
    PageHeader,
    StageFooter,
    StatusBanner,
    TableCard,
)
from portfell.dash_app.contracts import PAGE_SPECS, SHARED_PRIMITIVES
from portfell.dash_app.shell import application_frame, normalize_route


def test_routes_and_navigation_are_exact() -> None:
    assert [item.route for item in PAGE_SPECS] == [
        "/metadata",
        "/univariate",
        "/bivariate",
        "/multivariate",
    ]
    assert [item.label for item in PAGE_SPECS] == [
        "Metadata",
        "Univariate",
        "Bivariate",
        "Multivariate",
    ]
    assert normalize_route("/") == "/metadata"
    assert normalize_route("/dashboard") == "/metadata"


def test_all_shared_primitives_are_implemented() -> None:
    assert SHARED_PRIMITIVES == (
        "PageHeader",
        "ControlBar",
        "KpiCard",
        "ChartCard",
        "TableCard",
        "StatusBanner",
        "HistoryCard",
        "StageFooter",
    )
    for primitive in (
        PageHeader,
        ControlBar,
        KpiCard,
        ChartCard,
        TableCard,
        StatusBanner,
        HistoryCard,
        StageFooter,
    ):
        assert callable(primitive)


def test_shell_renders_every_page_without_legacy_web_import() -> None:
    for spec in PAGE_SPECS:
        frame = application_frame(spec.route)
        rendered = str(frame.to_plotly_json())
        assert "Portfell" in rendered
        assert spec.title in rendered
        assert "Dashboard" not in rendered
        assert "Fees & Distributions" not in rendered
        assert "Resources" not in rendered

    package = Path("src/portfell/dash_app")
    source = "\n".join(path.read_text(encoding="utf-8") for path in package.rglob("*.py"))
    assert "apps.web" not in source
    assert "financial-dashboard-example.plotly.app" not in source
    assert ".execute(" not in source
    assert "psycopg" not in source
    assert "insert " not in source.lower()
    assert "update " not in source.lower()
    assert "delete " not in source.lower()


def test_fastapi_mount_keeps_health_and_redirects_root() -> None:
    api = FastAPI()

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    dash = create_dash_app()
    mount_dash_app(api, dash_app=dash)
    client = TestClient(api, follow_redirects=False)

    health_response = client.get("/health")
    root_response = client.get("/")
    metadata_response = client.get("/metadata")

    assert health_response.json() == {"status": "ok"}
    assert root_response.status_code == 307
    assert root_response.headers["location"] == "/metadata"
    assert metadata_response.status_code == 200


def test_css_freezes_reference_layout_tokens_and_breakpoints() -> None:
    css = Path("src/portfell/dash_app/assets/portfell.css").read_text(encoding="utf-8")
    for token in (
        "220px",
        "24px",
        "16px",
        "8px",
        "#f7f9fc",
        "#ffffff",
        "#e3e8ef",
        "#172033",
        "#6b7280",
        "#2f80ed",
        "#eaf3ff",
        "#198754",
        "#dc3545",
        "1099px",
        "768px",
        "767px",
    ):
        assert token in css
    assert "overflow-x: hidden" in css
