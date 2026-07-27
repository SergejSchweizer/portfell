from __future__ import annotations

import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
BASELINE_DOC = REPOSITORY_ROOT / "docs" / "backlog" / "web-ui-migration-baseline.md"
BASELINE_JSON = REPOSITORY_ROOT / "docs" / "backlog" / "web-ui-migration-baseline.json"
BASELINE_SHEET = (
    REPOSITORY_ROOT
    / "docs"
    / "backlog"
    / "web-ui-migration-baseline"
    / "screenshots"
    / "baseline-sheet.svg"
)
WEB_SERVER = REPOSITORY_ROOT / "apps" / "web" / "server.js"


def _baseline() -> dict[str, object]:
    return json.loads(BASELINE_JSON.read_text(encoding="utf-8"))


def test_web_ui_migration_baseline_is_committed_and_versioned() -> None:
    baseline = _baseline()
    document = BASELINE_DOC.read_text(encoding="utf-8")

    assert baseline["version"] == 1
    assert baseline["captured_from"] == "apps/web/server.js"
    assert baseline["locale"] == "en-US"
    assert baseline["timezone"] == "UTC"
    assert baseline["viewports"]["desktop"] == {"width": 1440, "height": 1080}
    assert baseline["viewports"]["tablet"] == {"width": 1024, "height": 1366}
    assert baseline["viewports"]["mobile"] == {"width": 390, "height": 844}
    assert "The machine-readable inventory lives beside this document" in document
    assert "docs/backlog/web-ui-migration-baseline.json" in document
    assert "baseline-sheet.svg" in document
    assert BASELINE_SHEET.exists()


def test_web_ui_migration_baseline_captures_current_routes_controls_and_states() -> None:
    baseline = _baseline()
    routes = {route["id"]: route for route in baseline["routes"]}
    controls = {control["id"]: control for control in baseline["controls"]}
    states = {state["id"]: state for state in baseline["states"]}

    assert routes["root-anon"]["route"] == "/"
    assert routes["root-authenticated"]["output_state"] == "dashboard-shell"
    assert routes["google-start"]["route"] == "/auth/google/start"
    assert routes["google-callback"]["input_contract"] == "Query string contains code and state."
    assert routes["health"]["output_state"] == "health-json"
    assert routes["logout"]["output_state"] == "login-gate"

    assert controls["google-login-button"]["endpoint"] == "/auth/google/start"
    assert controls["eodhd-key-input"]["selector"] == "name=provider_key"
    assert "idempotency key" in controls["fetch-all-isins"]["input_contract"].lower()
    assert controls["project-definition"]["endpoint"] == "/api/metadata-filter/projects"
    assert controls["statistics-step-buttons"]["endpoint"] == "client-side only"

    assert "Sign in to continue" in states["login"]["visible_texts"]
    assert "Projects" in states["dashboard"]["visible_texts"]
    assert "No project selected" in states["project-shell-empty"]["visible_texts"]
    assert "Statistics path map" in states["project-shell-selected"]["visible_texts"]
    assert "Loading statistics summary..." in states["statistics-loading"]["visible_texts"]
    assert "Loaded selected ISINs." in states["statistics-complete"]["visible_texts"]
    assert "Fetch failed." in states["statistics-warning"]["visible_texts"]
    assert (
        "Choose at least one filter with matching ISINs."
        in states["statistics-failed"]["visible_texts"]
    )
    assert (
        "No univariate statistics are available yet." in states["statistics-empty"]["visible_texts"]
    )


def test_web_ui_migration_baseline_records_retained_defects_and_exclusions() -> None:
    baseline = _baseline()

    assert "monolithic HTML-string renderer" in " ".join(baseline["known_defects"])
    assert "Project Snapshot" in baseline["excluded_behaviors"]
    assert "browser-side calculations" in baseline["excluded_behaviors"]
    assert "React implementation assumptions" in baseline["excluded_behaviors"]
    assert "provider secrets" in baseline["excluded_behaviors"]


def test_web_ui_migration_baseline_matches_current_shell_surface_strings() -> None:
    source = WEB_SERVER.read_text(encoding="utf-8")
    document = BASELINE_DOC.read_text(encoding="utf-8")

    for expected in (
        "Google Login",
        "Fetch all ISINs",
        "Project Definition",
        "Create New Project",
        "Load Data",
        "Univariate Statistics",
        "Bivariate Statistics",
        "Multivariate Statistics",
        "Consisting currently of 0 ISINs",
        "Choose at least one filter with matching ISINs.",
        "Statistics summary is not available.",
    ):
        assert expected in source or expected in document

    for forbidden in (
        "localStorage",
        "sessionStorage",
        "document.cookie",
        "access_token",
        "api_token",
        "Project Snapshot",
        "Portfolio Analysis",
    ):
        assert forbidden not in source
