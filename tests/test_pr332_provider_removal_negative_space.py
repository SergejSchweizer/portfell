"""Repository-level negative-space checks for the PostgreSQL source cutover.

These checks deliberately inspect deployable surfaces rather than historical design
documents.  The source-architecture documentation is rewritten separately; keeping
this test focused on executable authority makes it a stable merge gate.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from portfell.cli import build_parser

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPOSITORY_ROOT / "src" / "portfell"
OPENAPI_SNAPSHOT = REPOSITORY_ROOT / "docs" / "hosted_api_openapi.snapshot.json"

RETIRED_MODULES = frozenset(
    {
        "http.py",
        "search.py",
        "fetch_all_metadata.py",
        "fetch_all_quotes.py",
        "shared_market_data.py",
        "shared_market_refresh.py",
        "shared_market_cron.py",
        "hosted_api_local_runtime.py",
        "hosted_local_test_composition.py",
        "hosted_credentials.py",
        "hosted_routes_credentials.py",
        "provider_credential_schema.py",
        "user_ingestion.py",
    }
)
RETIRED_CLI_COMMANDS = frozenset(
    {
        "search",
        "fetch-all-metadata",
        "fetch-all-quotes",
        "shared-market-refresh",
        "portfell-shared-market-cron",
    }
)
RETIRED_OPENAPI_FRAGMENTS = frozenset(
    {
        "credential",
        "download",
        "provider",
        "fetch-all",
        "refresh",
    }
)
FORBIDDEN_MARKET_TABLE_NAMES = frozenset({"listings", "eod_quotes", "dividends", "splits"})


def _module_imports(path: Path) -> set[str]:
    imports: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            imports.add(node.module)
    return imports


def test_retired_provider_runtime_modules_and_commands_are_absent() -> None:
    assert all(not (PACKAGE_ROOT / module).exists() for module in RETIRED_MODULES)

    parser = build_parser()
    command_actions = {
        action.dest
        for action in parser._actions  # noqa: SLF001 - CLI parser is the public command inventory.
    }
    assert "command" in command_actions
    for command in RETIRED_CLI_COMMANDS:
        assert command not in parser._subparsers._group_actions[0].choices  # noqa: SLF001


def test_production_code_has_no_retired_provider_or_refresh_import() -> None:
    forbidden_roots = {
        f"portfell.{module.removesuffix('.py')}" for module in RETIRED_MODULES
    }
    for path in PACKAGE_ROOT.rglob("*.py"):
        imports = _module_imports(path)
        violations = {
            imported
            for imported in imports
            if any(imported == root or imported.startswith(f"{root}.") for root in forbidden_roots)
        }
        assert not violations, f"{path.relative_to(REPOSITORY_ROOT)}: {sorted(violations)}"


def test_openapi_has_no_provider_or_download_lifecycle_surface() -> None:
    operations = json.loads(OPENAPI_SNAPSHOT.read_text(encoding="utf-8"))["operations"]
    lowered = "\n".join(operations).lower()
    assert all(fragment not in lowered for fragment in RETIRED_OPENAPI_FRAGMENTS)


def test_market_table_names_are_confined_to_the_market_source_adapter() -> None:
    """Application repositories may not bypass the read-only market-source gateway."""

    for path in PACKAGE_ROOT.rglob("*.py"):
        if path.is_relative_to(PACKAGE_ROOT / "market_source"):
            continue
        source = path.read_text(encoding="utf-8").lower()
        violations = sorted(
            table
            for table in FORBIDDEN_MARKET_TABLE_NAMES
            if re.search(
                rf"\\b(?:from|join|into|update|table)\\s+(?:xetra_loader\\.)?{table}\\b",
                source,
            )
        )
        assert not violations, f"{path.relative_to(REPOSITORY_ROOT)}: {violations}"
