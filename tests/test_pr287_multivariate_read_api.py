from __future__ import annotations

from unittest.mock import Mock

from portfell.hosted_api import _project_slug, _resolve_project_id, create_app
from portfell.multivariate.read_api.reader import PersistedMultivariateEvidenceReader


class Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class Connection:
    def execute(self, sql: str, parameters=()):
        assert parameters == ("project-1", "run-1")
        if "multivariate_decisions" in sql:
            return Cursor(
                [
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
                [
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


def test_reader_resolves_owned_project_and_returns_stored_evidence_only() -> None:
    resolver_calls = []

    def resolve(user_id: str, project_slug: str) -> str:
        resolver_calls.append((user_id, project_slug))
        return "project-1"

    reader = PersistedMultivariateEvidenceReader(Connection(), resolve_project_id=resolve)
    run = reader.run_projection(user_id="user-1", project_slug="alpha", run_id="run-1")

    assert resolver_calls == [("user-1", "alpha")]
    assert run["decisions"][0]["winner"] == "cfg-1"
    assert [row["stage"] for row in run["history"]] == ["final_portfolio", "metadata"]


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


def test_create_app_registers_multivariate_evidence_routes_when_reader_is_injected() -> None:
    services = (Mock(), Mock(), Mock(), Mock())
    application = create_app(services=services, multivariate_evidence_reader=Mock())
    paths = {route.path for route in application.routes}

    assert "/api/projects/{project_slug}/multivariate/runs/{run_id}/evidence" in paths
    assert (
        "/api/projects/{project_slug}/multivariate/runs/{run_id}/sections/{section_id}"
        in paths
    )
    assert "/api/projects/{project_slug}/multivariate/runs/{run_id}/universe-history" in paths
