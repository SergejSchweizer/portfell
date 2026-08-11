"""Static validation of the hosted catalog's role and migration invariants."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def validate_catalog_contracts(
    *, roles: Sequence[Any], tables: Sequence[Any], migrations: Sequence[Any]
) -> None:
    if any(role.can_bypass_rls for role in roles):
        raise ValueError("hosted roles must not bypass RLS")
    runtime_names = {"portfell_app", "portfell_worker", "portfell_readonly"}
    if any(role.owns_tables for role in roles if role.name in runtime_names):
        raise ValueError("runtime roles must not own tables")
    versions = [migration.version for migration in migrations]
    if versions != sorted(set(versions)):
        raise ValueError("migration versions must be unique and ordered")
    if not [table for table in tables if table.user_scoped]:
        raise ValueError("at least one user-scoped table is required")
    sql = "\n".join(migration.sql.lower() for migration in migrations)
    for forbidden in ("plaintext", "api_token", "eodhd_token", "bypassrls"):
        if forbidden in sql:
            raise ValueError(f"forbidden hosted catalog token present: {forbidden}")
