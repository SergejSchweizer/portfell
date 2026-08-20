from __future__ import annotations

import ast
from pathlib import Path

import pytest


def test_pr277_runtime_source_has_no_db_provider_or_calculation_authority() -> None:
    source = Path("src/portfell/dash_ui/runtime/app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported |= {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    forbidden = ("postgres", "database", "eodhd", "provider", "silver", "gold", "risk")
    assert not any(token in name for name in imported for token in forbidden)


def test_pr277_container_receives_no_database_or_provider_secret() -> None:
    compose = Path("compose.dash.yaml").read_text(encoding="utf-8")
    assert 'PORTFELL_API_BASE_URL: http://api:8000' in compose
    assert "PORTFELL_DATABASE_URL" not in compose
    assert "EODHD" not in compose
    assert "secrets:" not in compose
    assert '127.0.0.1:${PORTFELL_DASH_PORT:-8050}:8050' in compose
    assert "/dash/" in compose


def test_pr277_dependency_surface_is_dash_only() -> None:
    requirements = Path("apps/dash/requirements.txt").read_text(encoding="utf-8").splitlines()
    assert requirements == ["dash==3.2.0"]
    forbidden = ("celery", "redis", "diskcache", "pandas")
    assert not any(token in line.casefold() for line in requirements for token in forbidden)


def test_pr277_dash_app_smoke_when_container_dependency_is_available() -> None:
    pytest.importorskip("dash")
    from portfell.dash_ui.runtime.app import create_dash_app

    app = create_dash_app()
    assert app.config.requests_pathname_prefix == "/dash/"
    assert app.config.routes_pathname_prefix == "/dash/"
    assert app.config.suppress_callback_exceptions is False
    assert app.layout is not None
