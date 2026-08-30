from __future__ import annotations

import inspect

from portfell.hosted_api import create_runtime_app
from portfell.hosted_api_state import DEFAULT_LOCAL_WORKSPACE_USER_ID, ConfiguredUserProvider
from portfell.hosted_postgres_repository_bundle import PostgresHostedRepositoryBundle


class _Connection:
    def execute(self, _sql: str, _parameters: tuple[object, ...] = ()) -> object:
        return object()


def test_production_runtime_freezes_one_workspace_principal() -> None:
    source = inspect.getsource(create_runtime_app)

    assert "PORTFELL_LOCAL_WORKSPACE_USER_ID" not in source
    assert "PostgresHostedUserRepository" not in source
    assert DEFAULT_LOCAL_WORKSPACE_USER_ID in source
    assert ConfiguredUserProvider().current_user().user_id == DEFAULT_LOCAL_WORKSPACE_USER_ID


def test_production_repository_bundle_has_no_identity_or_credential_authority() -> None:
    bundle = PostgresHostedRepositoryBundle.from_connection(_Connection())

    assert not hasattr(bundle, "users")
    assert not hasattr(bundle, "memberships")
    assert not hasattr(bundle, "credentials")
    assert bundle.projects is not None
    assert bundle.selections is not None
