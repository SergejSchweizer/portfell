"""Workspace persistence adapter for hosted research transitions."""

from __future__ import annotations

from portfell.hosted_api_state import HostedApiState
from portfell.hosted_workspace_repository import persist_local_workspace


class LocalResearchPersistence:
    """Persist research state through the configured local workspace store."""

    def __init__(self, state: HostedApiState) -> None:
        self._state = state

    def persist(self) -> None:
        persist_local_workspace(self._state)
