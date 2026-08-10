"""Local-only hosted audit event repository adapter."""

from __future__ import annotations

from portfell.hosted_api_state import HostedApiState
from portfell.hosted_audit_event_repository import AuditEventRepository, HostedAuditEvent
from portfell.hosted_workspace_repository import persist_local_workspace


class LocalAuditEventRepository(AuditEventRepository):
    """Persist local-mode audit events in the explicit development-state adapter."""

    def __init__(self, state: HostedApiState) -> None:
        self._state = state

    def append(self, event: HostedAuditEvent) -> HostedAuditEvent:
        self._state.audit_events.append(
            {
                "audit_event_id": event.audit_event_id,
                "user_id": event.user_id,
                "event_type": event.event_type,
                "subject_ref": event.subject_ref,
                "metadata": event.metadata,
            }
        )
        persist_local_workspace(self._state)
        return event
