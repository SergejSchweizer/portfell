"""PR422 least-privilege role and grant contract tests."""

from __future__ import annotations

from portfell.app_state.migration import APP_STATE_MIGRATIONS
from portfell.app_state.migrations import MIGRATION_V006
from portfell.app_state.module_permissions import can_write_schema, role_for_module


def test_role_matrix_is_one_login_per_process() -> None:
    assert MIGRATION_V006 in APP_STATE_MIGRATIONS
    assert {
        role_for_module(module)
        for module in ("gateway", "metadata", "univariate", "bivariate", "multivariate")
    } == {
        "portfell_gateway",
        "portfell_metadata",
        "portfell_univariate",
        "portfell_bivariate",
        "portfell_multivariate",
    }


def test_only_owned_schema_is_writable() -> None:
    for module, schema in (
        ("gateway", "workflow"),
        ("metadata", "metadata"),
        ("univariate", "univariate"),
        ("bivariate", "bivariate"),
        ("multivariate", "multivariate"),
    ):
        assert can_write_schema(module, schema)
        assert not can_write_schema(module, "portfell")
        assert not can_write_schema(module, "univariate" if schema != "univariate" else "metadata")


def test_grant_sql_has_no_passwords_and_restricts_writes_to_owner_tables() -> None:
    sql = MIGRATION_V006.sql.casefold()
    assert "password" not in sql
    assert "grant select, insert on metadata.universes" in sql
    assert "grant select, insert on univariate.runs, univariate.selections" in sql
    assert "grant select, insert on bivariate.runs" in sql
    assert "grant select, insert on multivariate.runs" in sql
    assert "grant all" not in sql
