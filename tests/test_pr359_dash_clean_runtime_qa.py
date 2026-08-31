from __future__ import annotations

import ast
import re
import tomllib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "portfell"
SQL_PATTERN = re.compile(
    r"^\s*(?:select\s+.+?\s+from|insert\s+into|update\s+\S+\s+set|delete\s+from|"
    r"create\s+(?:table|schema)|alter\s+|drop\s+)\b",
    re.IGNORECASE | re.DOTALL,
)


def _sql_literals(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return tuple(
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and SQL_PATTERN.search(node.value)
    )


def test_final_tree_has_no_legacy_ui_database_or_provider_runtime() -> None:
    assert not (ROOT / "apps" / "web").exists()
    source_files = tuple(path for path in ROOT.rglob("*") if ".venv" not in path.parts)
    assert not tuple(path for path in source_files if path.name == "package.json")
    assert not tuple(path for path in source_files if path.suffix in {".tsx", ".ts"})

    retired_modules = (
        "hosted_catalog.py",
        "hosted_catalog_migration.py",
        "hosted_repository_importer.py",
        "hosted_postgres_repository_bundle.py",
        "hosted_postgres_service_composition.py",
        "tenant_control_schema.py",
        "legacy_import_schema.py",
    )
    assert all(not (PACKAGE / name).exists() for name in retired_modules)
    assert not tuple(PACKAGE.glob("hosted_*repository.py"))
    assert not tuple(PACKAGE.glob("hosted_postgres_*.py"))

    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8").lower()
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    assert "apps/web" not in compose
    assert "node" not in compose
    assert "eodhd" not in compose
    assert "provider_token" not in compose
    assert "provider_key" not in compose
    assert "refresh-worker" not in compose
    assert "download-worker" not in compose
    assert "eodhistoricaldata" not in pyproject
    assert "xetra-loader" not in pyproject


def test_sql_is_owned_only_by_app_state_and_market_source_packages() -> None:
    dash_offenders: list[str] = []
    market_offenders: list[str] = []
    app_state_offenders: list[str] = []

    for path in sorted(PACKAGE.rglob("*.py")):
        relative = path.relative_to(PACKAGE)
        literals = _sql_literals(path)
        if not literals:
            continue
        if "dash_app" in relative.parts:
            dash_offenders.append(str(relative))
        for literal in literals:
            lowered = literal.lower()
            if "xetra_loader." in lowered and "market_source" not in relative.parts:
                market_offenders.append(str(relative))
            if "portfell." in lowered and "app_state" not in relative.parts:
                app_state_offenders.append(str(relative))

    assert dash_offenders == []
    assert market_offenders == []
    assert app_state_offenders == []


def test_root_config_is_local_only_and_images_cannot_bake_it() -> None:
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    dockerfile = (ROOT / "apps" / "api" / "Dockerfile").read_text(encoding="utf-8")
    example = (ROOT / "config.example.yaml").read_text(encoding="utf-8")
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "config.yaml" in gitignore
    assert "!config.example.yaml" in gitignore
    assert "!config.yaml" not in dockerignore
    assert "COPY config.yaml" not in dockerfile
    assert "password:" not in example.lower()
    assert "postgresql://" not in example.lower()
    assert "password=" not in env_example.lower()


def test_final_compose_has_exactly_two_database_authorities_and_one_app_surface() -> None:
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text(encoding="utf-8"))
    services = compose["services"]
    assert set(services) == {"api", "postgres"}
    assert services["postgres"]["environment"]["POSTGRES_DB"] == "portfell_dash"
    assert services["api"]["environment"]["PORTFELL_DATABASE_URL"].endswith("/portfell_dash")
    assert "PORTFELL_MARKET_DATABASE_URL" in services["api"]["environment"]
    assert services["api"]["ports"] == ["0.0.0.0:${PORTFELL_PORT:-8080}:8000"]


def test_clean_install_and_browser_acceptance_harnesses_cover_final_contract() -> None:
    api = (PACKAGE / "hosted_api.py").read_text(encoding="utf-8")
    browser = (ROOT / "tests" / "browser" / "test_dash_four_page_parity.py").read_text(
        encoding="utf-8"
    )
    visual = (PACKAGE / "dash_app" / "visual_contract.py").read_text(encoding="utf-8")

    for token in (
        "migrate_to_head",
        "PostgresAppStateRepository",
        "ResearchApplicationService",
        "MarketDataGateway",
        "mount_dash_app",
    ):
        assert token in api

    for token in (
        "PAGE_ROUTES",
        "VISUAL_VIEWPORTS",
        "reference_requests",
        "typed_failure_retry",
        "cross_stage_invalidation",
        "screenshots_complete",
        "stage_reload_persistence",
        "body_horizontal_overflow_absent",
    ):
        assert token in browser

    assert '("/metadata", "/univariate", "/bivariate", "/multivariate")' in visual
    assert 'Viewport("desktop", 1440, 900)' in visual
    assert 'Viewport("tablet", 1024, 768)' in visual
    assert 'Viewport("mobile", 390, 844)' in visual
    assert "financial-dashboard-example.plotly.app" not in visual
    assert "financial-dashboard-example.plotly.app" in browser
    assert "assert not reference_requests" in browser


def test_local_quality_contract_exposes_both_required_layers() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["scripts"]["portfell-quality"] == "portfell.quality:main"

    quality = (PACKAGE / "quality.py").read_text(encoding="utf-8")
    assert 'if layer == "pr"' in quality
    assert 'if layer in {"merge", "main"}' in quality
    assert '"--cov-fail-under=90"' in quality
