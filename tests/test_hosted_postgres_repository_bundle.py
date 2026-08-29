from __future__ import annotations

from portfell.hosted_postgres_repository_bundle import PostgresHostedRepositoryBundle


class _Connection:
    def execute(self, _sql: str, _parameters: tuple[object, ...] = ()) -> object:
        return object()


def test_composes_all_control_plane_repositories_on_one_connection() -> None:
    connection = _Connection()
    bundle = PostgresHostedRepositoryBundle.from_connection(connection)

    assert bundle.projects._connection is connection  # type: ignore[attr-defined]
    assert bundle.quotes._connection is connection  # type: ignore[attr-defined]
    assert bundle.analyses._connection is connection  # type: ignore[attr-defined]
