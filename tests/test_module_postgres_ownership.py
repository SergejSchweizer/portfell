"""PR409 schema ownership and immutable hand-off contract tests."""

from __future__ import annotations

import ast

from portfell.app_state.migration import APP_STATE_MIGRATIONS
from portfell.app_state.migrations import MIGRATION_V004
from portfell.app_state.module_ownership import MODULE_SCHEMAS, MODULE_TABLES, owner_for_schema


def test_v004_is_forward_only_head_and_declares_all_owner_schemas() -> None:
    assert APP_STATE_MIGRATIONS[-1] is MIGRATION_V004
    assert MIGRATION_V004.version == 4
    for schema in ("workflow", "metadata", "univariate", "bivariate", "multivariate"):
        assert f"create schema if not exists {schema}" in MIGRATION_V004.sql
    assert "create table if not exists workflow.stage_commands" in MIGRATION_V004.sql


def test_ownership_matrix_has_one_owner_per_table() -> None:
    assert set(MODULE_SCHEMAS) == {"gateway", "metadata", "univariate", "bivariate", "multivariate"}
    flattened = [
        f"{MODULE_SCHEMAS[module]}.{table}"
        for module, tables in MODULE_TABLES.items()
        for table in tables
    ]
    assert len(flattened) == len(set(flattened))
    assert owner_for_schema("metadata") == "metadata"


def test_handoffs_are_ids_not_analytical_rows() -> None:
    sql = MIGRATION_V004.sql
    for forbidden in ("quote", "covariance", "matrix", "portfolio"):
        assert forbidden not in sql.casefold()
    assert "metadata_universe_id text not null" in sql
    assert "univariate_selection_id text not null" in sql
    assert "bivariate_run_id text not null" in sql


def test_handoff_tables_have_immutable_triggers_and_public_access_revoked() -> None:
    sql = MIGRATION_V004.sql
    assert sql.count("before update or delete") == 4
    assert "module_handoff_immutable" in sql
    assert "revoke all on all tables in schema workflow, metadata, univariate, bivariate," in sql


def test_ownership_module_contains_no_database_or_numerical_imports() -> None:
    from pathlib import Path

    source = ast.parse(Path("src/portfell/app_state/module_ownership.py").read_text())
    imported = {
        node.module.split(".")[0]
        for node in ast.walk(source)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert imported <= {"__future__", "collections", "typing"}
