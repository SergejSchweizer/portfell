"""Forward-only PostgreSQL migration SQL for durable legacy import idempotency."""

from __future__ import annotations

LEGACY_IMPORT_LEDGER_SQL = """
create table if not exists portfell_private.legacy_imports (
    checksum text primary key,
    imported_at timestamptz not null default now()
);
revoke all on portfell_private.legacy_imports from public, portfell_app, portfell_readonly;
grant select, insert on portfell_private.legacy_imports to portfell_migrator;
"""
