from __future__ import annotations

from portfell.hosted_project_workflow_projector import PostgresProjectWorkflowProjector


class Projection:
    def __init__(self, *, changed: bool) -> None:
        self.changed = changed

    def write_with_change(
        self, *, user_id: str, project_id: str, payload: dict[str, object]
    ) -> tuple[dict[str, object], str, bool]:
        assert user_id == "u1"
        assert project_id == "p1"
        return payload, "revision", self.changed


class Events:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def append(self, **kwargs: object) -> None:
        self.calls.append(kwargs)


def test_projector_publishes_one_event_only_for_a_workflow_transition() -> None:
    events = Events()
    projector = PostgresProjectWorkflowProjector(
        lambda _user_id, _project_id: {"stages": {}}, Projection(changed=True), events  # type: ignore[arg-type]
    )

    payload, revision = projector.reconcile("u1", "p1")

    assert payload == {"schema_version": 1, "stages": {}}
    assert revision == "revision"
    assert events.calls == [
        {
            "user_id": "u1",
            "project_id": "p1",
            "event_type": "workflow.changed",
            "aggregate_ref": "project:p1",
            "projection_revision": "revision",
        }
    ]


def test_projector_does_not_publish_when_the_projection_is_unchanged() -> None:
    events = Events()
    projector = PostgresProjectWorkflowProjector(
        lambda _user_id, _project_id: {"stages": {}}, Projection(changed=False), events  # type: ignore[arg-type]
    )

    projector.reconcile("u1", "p1")

    assert events.calls == []
