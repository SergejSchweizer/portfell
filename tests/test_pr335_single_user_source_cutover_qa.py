from __future__ import annotations

import inspect
from pathlib import Path

from portfell.hosted_api import create_runtime_app
from portfell.hosted_api_state import DEFAULT_LOCAL_WORKSPACE_USER_ID, ConfiguredUserProvider
from portfell.hosted_postgres_repository_bundle import PostgresHostedRepositoryBundle
from portfell.market_source.connection import (
    preflight_market_source,
    repeatable_read_snapshot,
    validate_reader_role,
)

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web"


class _Connection:
    def execute(self, _sql: str, _parameters: tuple[object, ...] = ()) -> object:
        return object()


def test_production_composition_has_one_server_owned_workspace_principal() -> None:
    source = inspect.getsource(create_runtime_app)

    assert "PORTFELL_LOCAL_WORKSPACE_USER_ID" not in source
    assert "PostgresHostedUserRepository" not in source
    assert "ensure_user=" not in source
    assert "DEFAULT_LOCAL_WORKSPACE_USER_ID" in source
    assert ConfiguredUserProvider().current_user().user_id == DEFAULT_LOCAL_WORKSPACE_USER_ID

    bundle = PostgresHostedRepositoryBundle.from_connection(_Connection())
    assert not hasattr(bundle, "users")
    assert not hasattr(bundle, "memberships")
    assert not hasattr(bundle, "credentials")


def test_transitional_browser_has_only_canonical_workspace_route_authority() -> None:
    routes = (WEB / "src" / "routes.tsx").read_text(encoding="utf-8")
    frame = (WEB / "src" / "shell" / "frame.tsx").read_text(encoding="utf-8")
    sidebar = (WEB / "src" / "shell" / "project-sidebar.tsx").read_text(encoding="utf-8")

    for path in ("/metadata", "/univariate", "/bivariate", "/multivariate"):
        assert f'path: "{path}"' in routes

    assert 'path: "/metadata-builder"' not in routes
    assert 'path: "/univariate-statistics"' not in routes
    assert 'path: "/bivariate-statistics"' not in routes
    assert 'path: "/multivariate-statistics"' not in routes
    assert "selectCurrentProject" not in frame
    assert "onProjectChange" not in frame
    assert "current-project" not in sidebar
    assert "onProjectChange" not in sidebar


def test_market_postgres_contract_remains_read_only_non_superuser_group_membership() -> None:
    preflight = inspect.getsource(preflight_market_source)
    snapshot = inspect.getsource(repeatable_read_snapshot)
    role_validation = inspect.getsource(validate_reader_role)

    assert "REPEATABLE READ READ ONLY" in preflight
    assert "REPEATABLE READ READ ONLY" in snapshot
    assert "SET LOCAL TIME ZONE 'UTC'" in preflight
    assert "SET LOCAL TIME ZONE 'UTC'" in snapshot
    assert "pg_has_role" in role_validation
    assert "rolsuper" in role_validation
    assert "row != (True, False, True)" in role_validation

    forbidden_dml = (
        "INSERT INTO",
        "UPDATE ",
        "DELETE FROM",
        "TRUNCATE ",
        "ALTER TABLE",
        "DROP TABLE",
    )
    for statement in forbidden_dml:
        assert statement not in preflight.upper()
        assert statement not in snapshot.upper()


def test_pr335_qa_does_not_restore_provider_or_project_switching_surfaces() -> None:
    production_paths = [
        ROOT / "src" / "portfell" / "hosted_api.py",
        ROOT / "src" / "portfell" / "hosted_postgres_repository_bundle.py",
        WEB / "src" / "routes.tsx",
        WEB / "src" / "shell" / "frame.tsx",
        WEB / "src" / "shell" / "project-sidebar.tsx",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in production_paths)

    assert "PostgresHostedUserRepository" not in text
    assert "PORTFELL_LOCAL_WORKSPACE_USER_ID" not in text
    assert "selectCurrentProject" not in text
    assert "#current-project" not in text
    assert "EODHD" not in text.upper()
