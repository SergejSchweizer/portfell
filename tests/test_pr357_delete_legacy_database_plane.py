from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "portfell"


def test_pr357_deletes_inventory_owned_legacy_database_sources() -> None:
    explicit = (
        "analysis_lifecycle_schema.py",
        "durable_job_schema.py",
        "hosted_catalog.py",
        "hosted_catalog_migration.py",
        "hosted_catalog_ports.py",
        "hosted_navigation_read_model_schema.py",
        "hosted_project_workflow_projection_schema.py",
        "legacy_import_schema.py",
        "metadata_builder_criteria_schema.py",
        "metadata_lifecycle_schema.py",
        "multivariate_lifecycle_schema.py",
        "project_membership_trigger_schema.py",
        "project_settings_schema.py",
        "research_lifecycle_schema.py",
        "tenant_control_schema.py",
    )
    assert all(not (SRC / name).exists() for name in explicit)
    assert not tuple(SRC.glob("hosted_*persistence.py"))
    assert not tuple(SRC.glob("hosted_*repository.py"))
    assert not tuple(SRC.glob("hosted_postgres_*.py"))


def test_pr357_runtime_names_only_clean_app_database() -> None:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    api = (SRC / "hosted_api.py").read_text(encoding="utf-8")
    readiness = (SRC / "hosted_readiness.py").read_text(encoding="utf-8")
    config = (ROOT / "config.example.yaml").read_text(encoding="utf-8")

    assert "PORTFELL_HOSTED_AUTHORITY" not in compose
    assert "PORTFELL_HOSTED_AUTHORITY" not in api
    assert "PORTFELL_HOSTED_AUTHORITY" not in readiness
    assert re.search(r"POSTGRES_DB:\s*portfell_dash\b", compose)
    assert "postgres:5432/portfell_dash" in compose
    assert "portfell-dash-postgres-data" in compose
    assert not re.search(r"POSTGRES_DB:\s*portfell\s*$", compose, re.MULTILINE)
    assert "portfell_private" not in api
    assert "portfell_private" not in readiness
    assert "database: portfell_dash" in config
    assert "schema: portfell" in config


def test_pr357_clean_runtime_uses_app_state_and_market_source_only() -> None:
    api = (SRC / "hosted_api.py").read_text(encoding="utf-8")
    assert "portfell.app_state.migration" in api
    assert "PostgresAppStateRepository" in api
    assert "MarketDataGateway" in api
    assert "hosted_postgres_" not in api
    assert "hosted_catalog" not in api
    assert "hosted_repository" not in api

    migration = (SRC / "app_state" / "migration.py").read_text(encoding="utf-8")
    assert "portfell.schema_migrations" in migration
    assert "portfell_dash" in migration
