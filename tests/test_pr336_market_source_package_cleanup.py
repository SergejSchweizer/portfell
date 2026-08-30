from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "src" / "portfell"
MARKET_SOURCE = PACKAGE / "market_source"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_legacy_local_market_cli_and_workflow_authority_are_deleted() -> None:
    assert not (PACKAGE / "cli.py").exists()
    assert not (PACKAGE / "workflows.py").exists()

    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'portfell = "portfell.cli:main"' not in pyproject
    assert "Silver quotes" not in pyproject
    assert "EODHD" not in pyproject.upper()


def test_market_source_package_has_no_filesystem_or_hosted_runtime_dependency() -> None:
    forbidden_prefixes = (
        "portfell.hosted_",
        "portfell.paths",
        "portfell.table_io",
        "portfell.metadata_builder",
        "portfell.run_locks",
        "portfell.workflows",
        "portfell.cli",
    )
    for path in sorted(MARKET_SOURCE.glob("*.py")):
        for imported in _imports(path):
            assert not imported.startswith(forbidden_prefixes), (path.name, imported)


def test_only_postgresql_market_package_owns_source_sql() -> None:
    market_sql_tokens = (
        "from xetra_loader.",
        "join xetra_loader.",
        "insert into xetra_loader.",
        "update xetra_loader.",
        "delete from xetra_loader.",
    )
    offenders: list[str] = []
    for path in sorted(PACKAGE.rglob("*.py")):
        if MARKET_SOURCE in path.parents:
            continue
        text = path.read_text(encoding="utf-8").lower()
        if any(token in text for token in market_sql_tokens):
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == []


def test_package_description_declares_postgresql_market_authority() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "external read-only PostgreSQL market data" in pyproject
