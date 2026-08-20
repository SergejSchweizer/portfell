from __future__ import annotations

from unittest.mock import Mock

from portfell.hosted_api import _project_slug, _resolve_project_id, create_app
from portfell.multivariate.read_api.reader import PersistedMultivariateEvidenceReader


class Cursor:
    def __init__(self, rows=(), one=None):
        self._rows = rows
        self._one = one

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._one


class Connection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, sql: str, parameters=()):
        self.calls.append((sql, parameters))
        if "multivariate_current_selections" in sql:
            assert parameters == ("user-1", "project-1")
            return Cursor(
                one=(
                    "selection-1",
                    '{"run_id":"run-1","winner":"cfg-1"}',
                )
            )
        assert parameters == ("user-1", "project-1", "run-1")
        if "multivariate_decisions" in sql:
            return Cursor(
                rows=[
                    (
                        "decision-1",
                        "run-1",
                        "winner_selection",
                        '{"stage":"winner_selection","winner":"cfg-1"}',
                    )
                ]
            )
        if "research_universe_snapshots" in sql:
            return Cursor(
                rows=[
                    (
                        "snapshot-2",
                        "run-1",
                        "final_portfolio",
                        '{"stage":"final_portfolio","snapshot_id":"snapshot-2"}',
                    ),
                    (
                        "snapshot-1",
                        "run-1",
                        "metadata",
                        '{"stage":"metadata","snapshot_id":"snapshot-1"}',
                    ),
                ]
            )
        raise AssertionError(sql)


class Projects:
    def project_context(self, user_id: str):
        assert user_id == "user-1"
        return {
            "projects": [
                {"name": "Alpha Growth", "project_id": "project-1"},
                {"name": "Beta Income", "project_id": "project-2"},
            ]
        }


def test_reader_resolves_owned_project_before_project_scoped_repository_reads() -> None:
    resolver_calls = []
    connection = Connection()

    def resolve(user_id: str, project_slug: str) -> str:
        resolver_calls.append((user_id, project_slug))
        return "project-1"

    reader = PersistedMultivariateEvidenceReader(connection, resolve_project_id=resolve)
    run = reader.run_projection(user_id="user-1", project_slug="alpha", run_id="run-1")

    assert resolver_calls == [("user-1", "alpha")]
    assert run["decisions"][0]["winner"] == "cfg-1"
    assert [row["stage"] for row in run["history"]] == ["final_portfolio", "metadata"]
    assert all("user_id = %s::uuid and project_id = %s::uuid" in sql for sql, _ in connection.calls)


def test_reader_current_projection_returns_persisted_run_and_selection_only() -> None:
    reader = PersistedMultivariateEvidenceReader(
        Connection(), resolve_project_id=lambda _user_id, _slug: "project-1"
    )
    current = reader.current_projection(user_id="user-1", project_slug="alpha")
    assert current == {
        "project_slug": "alpha",
        "availability": "available",
        "selection_revision": "selection-1",
        "run_id": "run-1",
        "selection": {"run_id": "run-1", "winner": "cfg-1"},
    }


def test_reader_sections_and_pipeline_are_deterministic() -> None:
    reader = PersistedMultivariateEvidenceReader(
        Connection(), resolve_project_id=lambda _user_id, _slug: "project-1"
    )

    section = reader.section_projection(
        user_id="user-1",
        project_slug="alpha",
        run_id="run-1",
        section_id="winner_selection",
    )
    pipeline = reader.pipeline_projection(
        user_id="user-1", project_slug="alpha", run_id="run-1"
    )

    assert section["winner"] == "cfg-1"
    assert [row["stage"] for row in pipeline] == ["metadata", "final_portfolio"]


def test_reader_missing_section_is_typed_unavailable_without_calculation() -> None:
    reader = PersistedMultivariateEvidenceReader(
        Connection(), resolve_project_id=lambda _user_id, _slug: "project-1"
    )
    section = reader.section_projection(
        user_id="user-1",
        project_slug="alpha",
        run_id="run-1",
        section_id="risk_model_candidates",
    )
    assert section == {
        "availability": "unavailable",
        "reason": "section_not_persisted",
        "section_id": "risk_model_candidates",
    }


def test_project_slug_resolution_is_deterministic_and_fail_closed() -> None:
    assert _project_slug("Älpha Growth") == "alpha-growth"
    assert (
        _resolve_project_id(Projects(), user_id="user-1", project_slug="alpha-growth")
        == "project-1"
    )

    try:
        _resolve_project_id(Projects(), user_id="user-1", project_slug="missing")
    except KeyError as error:
        assert error.args == ("missing",)
    else:
        raise AssertionError("missing project slug must fail closed")


def test_create_app_registers_all_read_only_multivariate_evidence_routes() -> None:
    services = (Mock(), Mock(), Mock(), Mock())
    application = create_app(services=services, multivariate_evidence_reader=Mock())
    paths = {route.path for route in application.routes}

    assert "/api/projects/{project_slug}/multivariate/current" in paths
    assert "/api/projects/{project_slug}/multivariate/runs/{run_id}/evidence" in paths
    assert (
        "/api/projects/{project_slug}/multivariate/runs/{run_id}/sections/{section_id}"
        in paths
    )
    assert "/api/projects/{project_slug}/multivariate/runs/{run_id}/universe-history" in paths
