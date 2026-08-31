from __future__ import annotations

import ast
import importlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "portfell"


def test_clean_runtime_imports_without_legacy_market_cli() -> None:
    assert not (PACKAGE / "cli.py").exists()
    assert not (PACKAGE / "workflows.py").exists()

    for module in (
        "portfell",
        "portfell.hosted_api",
        "portfell.market_source",
        "portfell.market_source.gateway",
        "portfell.hosted_market_source_univariate_service",
        "portfell.hosted_market_source_bivariate_service",
        "portfell.hosted_market_source_multivariate_service",
    ):
        assert importlib.import_module(module) is not None


def test_unreachable_legacy_market_and_multi_tenant_runtime_modules_are_absent() -> None:
    """The clean runtime must not carry unimported legacy authority just for compatibility."""

    retired_modules = (
        "hosted_cutover.py",
        "hosted_download_run_schema.py",
        "hosted_market_source_bivariate_repository.py",
        "hosted_navigation_reconciler.py",
        "hosted_project_workflow_projection_schema.py",
        "hosted_status_event_retention_schema.py",
        "hosted_status_event_schema.py",
        "metadata_builder.py",
        "univariate_selection.py",
    )
    assert all(not (PACKAGE / module).exists() for module in retired_modules)


def test_locked_runtime_has_no_provider_or_loader_python_dependency() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8").lower()
    lock = (ROOT / "uv.lock").read_text(encoding="utf-8").lower()

    for forbidden in ("eodhd", "xetra-loader", "xetra_loader =", "eodhistoricaldata"):
        assert forbidden not in pyproject
        assert forbidden not in lock

    assert "psycopg[binary]" in pyproject


def test_transitional_compose_has_exactly_two_database_authorities() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    manifest = yaml.safe_load(compose)

    # One Portfell-owned application PostgreSQL service remains during source cutover.
    assert set(manifest["services"]) == {"postgres", "api"}
    assert set(manifest.get("volumes", {})) == {"portfell-postgres-data"}
    assert "PORTFELL_DATABASE_URL: postgresql://portfell_app@postgres:5432/portfell" in compose

    # Market data is an external required authority, never a Compose-owned database.
    assert "PORTFELL_MARKET_DATABASE_URL: ${PORTFELL_MARKET_DATABASE_URL:?" in compose
    assert "  market-postgres:" not in compose
    assert "  xetra-loader:" not in compose
    assert "POSTGRES_DB: xetra_loader" not in compose
    assert "PORTFELL_CONFIG_PATH: /run/portfell/config.yaml" in compose
    assert "./config.yaml:/run/portfell/config.yaml:ro" in compose


def test_compose_and_package_have_no_provider_nas_or_refresh_runtime() -> None:
    files = [ROOT / "compose.yaml", ROOT / "pyproject.toml"]
    text = "\n".join(path.read_text(encoding="utf-8").lower() for path in files)
    for forbidden in (
        "eodhd",
        "provider_key",
        "provider_token",
        "download-worker",
        "refresh-worker",
        "market-nas",
        "shared-market",
    ):
        assert forbidden not in text


def test_four_stage_application_fixture_remains_part_of_clean_runtime_gate() -> None:
    four_stage = ROOT / "tests" / "test_four_stage_market_source_qa.py"
    assert four_stage.exists()
    source = four_stage.read_text(encoding="utf-8")

    required = (
        "MetadataProjectService",
        "MarketSourceUnivariateResearchService",
        "MarketSourceBivariateResearchService",
        "MarketSourceMultivariateResearchService",
        "MarketDataSnapshot",
        "market_source_snapshot_",
        "MISSING_ADJUSTED_CLOSE",
        "IE00QA000001:XETRA:QA-A",
        "IE00QA000001:XETRA:QA-B",
    )
    for token in required:
        assert token in source


def test_market_sql_is_confined_to_market_source_package() -> None:
    offenders: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if (PACKAGE / "market_source") in path.parents:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            literal = node.value.lower()
            if "xetra_loader." in literal and any(
                keyword in literal for keyword in ("select ", "insert ", "update ", "delete ")
            ):
                offenders.append(str(path.relative_to(ROOT)))
                break
    assert offenders == []
