from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "docs" / "contracts" / "legacy-ui-db-inventory-v1.json"
REPLACEMENT_PATH = ROOT / "docs" / "contracts" / "plotly-dash-replacement-v1.md"
UI_PATH = ROOT / "docs" / "contracts" / "plotly-dash-ui-v1.md"

ALLOWED_DISPOSITIONS = {
    "delete-pr356",
    "delete-pr357",
    "retain-backend",
    "retain-test-only",
}
FORBIDDEN_SECRET_FRAGMENTS = (
    "postgresql://",
    "password=",
    "passwd=",
    "bearer ",
    "api_key=",
    "apikey=",
    "secret=",
    "token=",
)


def _inventory() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(INVENTORY_PATH.read_text(encoding="utf-8")))


def test_inventory_schema_is_frozen_and_has_no_unknown_disposition() -> None:
    inventory = _inventory()
    assert inventory["schema_version"] == 1
    items = cast(list[dict[str, Any]], inventory["items"])
    assert items
    assert all(set(item) == {"disposition", "identifier", "kind", "reason"} for item in items)
    dispositions = {cast(str, item["disposition"]) for item in items}
    assert dispositions <= ALLOWED_DISPOSITIONS
    assert dispositions == ALLOWED_DISPOSITIONS
    assert "unknown" not in dispositions


def test_inventory_identifiers_are_unique_and_deterministically_grouped() -> None:
    items = cast(list[dict[str, Any]], _inventory()["items"])
    identifiers = [cast(str, item["identifier"]) for item in items]
    assert len(identifiers) == len(set(identifiers))
    # The checked-in JSON is the deterministic artifact. Canonical JSON key ordering is
    # enforced separately; item order is frozen by review and must not mutate at runtime.
    raw = INVENTORY_PATH.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    canonical = json.dumps(parsed, indent=2, ensure_ascii=False) + "\n"
    assert raw == canonical


def test_inventory_contains_no_credentials_or_credential_bearing_dsn() -> None:
    raw = INVENTORY_PATH.read_text(encoding="utf-8").casefold()
    for fragment in FORBIDDEN_SECRET_FRAGMENTS:
        assert fragment not in raw


def test_legacy_web_root_and_all_direct_frontend_dependencies_belong_to_pr356() -> None:
    items = cast(list[dict[str, Any]], _inventory()["items"])
    dispositions = {
        cast(str, item["identifier"]): cast(str, item["disposition"]) for item in items
    }
    assert dispositions["apps/web/**"] == "delete-pr356"
    expected_dependencies = {
        "npm:@playwright/test",
        "npm:@tanstack/react-query",
        "npm:@testing-library/jest-dom",
        "npm:@testing-library/react",
        "npm:@types/node",
        "npm:@types/react",
        "npm:@types/react-dom",
        "npm:@vitejs/plugin-react",
        "npm:@vitest/coverage-v8",
        "npm:jsdom",
        "npm:lucide-react",
        "npm:react",
        "npm:react-dom",
        "npm:typescript",
        "npm:vite",
        "npm:vitest",
    }
    assert all(dispositions[dependency] == "delete-pr356" for dependency in expected_dependencies)


def test_legacy_database_plane_belongs_to_pr357_and_market_authority_is_excluded() -> None:
    inventory = _inventory()
    items = cast(list[dict[str, Any]], inventory["items"])
    dispositions = {
        cast(str, item["identifier"]): cast(str, item["disposition"]) for item in items
    }
    assert dispositions["database:portfell"] == "delete-pr357"
    assert dispositions["database:portfell/schema:portfell_app"] == "delete-pr357"
    assert dispositions["database:portfell/schema:portfell_private"] == "delete-pr357"
    assert dispositions["src/portfell/hosted_catalog.py"] == "delete-pr357"
    assert dispositions["src/portfell/market_source/**"] == "retain-backend"

    excluded = {
        cast(str, item["identifier"])
        for item in cast(list[dict[str, Any]], inventory["excluded_authorities"])
    }
    assert excluded == {
        "external-db:xetra_loader",
        "external-role:xetra_loader.portfell_app",
        "external-schema:xetra_loader",
        "external-schema:xetra_loader_sync",
    }


def test_frozen_dash_contract_has_exact_routes_objectives_and_shared_primitives() -> None:
    replacement = REPLACEMENT_PATH.read_text(encoding="utf-8")
    ui = UI_PATH.read_text(encoding="utf-8")
    for route in ("/metadata", "/univariate", "/bivariate", "/multivariate"):
        assert route in replacement
        assert route in ui
    for objective in ("return_risk", "return_drawdown", "minimum_risk"):
        assert objective in replacement
        assert objective in ui
    for primitive in (
        "PageHeader",
        "ControlBar",
        "KpiCard",
        "ChartCard",
        "TableCard",
        "StatusBanner",
        "HistoryCard",
        "StageFooter",
    ):
        assert primitive in ui


def test_reference_is_documentation_only_and_forbidden_features_stay_absent() -> None:
    replacement = REPLACEMENT_PATH.read_text(encoding="utf-8")
    ui = UI_PATH.read_text(encoding="utf-8")
    reference = "https://financial-dashboard-example.plotly.app/"
    assert reference in ui
    assert "runtime/test dependency" in replacement
    assert "iframe" in replacement
    assert "Node Web runtime" in replacement
    assert "direct SQL" in replacement
    assert "xetra_loader_sync" in replacement
