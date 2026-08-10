"""Exact immutable project-selection bootstrap control contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, replace

BOOTSTRAP_STATUSES = frozenset({"not_started", "planning", "running", "ready", "partial", "failed"})
TERMINAL_BOOTSTRAP_STATUSES = frozenset({"ready", "partial"})


class BootstrapError(ValueError):
    """Raised for stable, non-secret bootstrap authorization or state errors."""


@dataclass(frozen=True)
class ProjectBootstrap:
    """One payload-free initial-fill request frozen to immutable selection membership."""

    bootstrap_id: str
    user_id: str
    project_id: str
    selection_id: str
    member_ids: tuple[str, ...]
    selected_listing_count: int
    status: str = "not_started"


class InMemoryBootstrapService:
    """Deterministic control-plane test double enforcing one bootstrap per project."""

    def __init__(self) -> None:
        self._bootstraps_by_project: dict[str, ProjectBootstrap] = {}

    def start(
        self,
        *,
        user_id: str,
        project_id: str,
        selection_id: str,
        member_ids: tuple[str, ...],
    ) -> ProjectBootstrap:
        """Freeze persisted selection members and return the one project bootstrap."""

        existing = self._bootstraps_by_project.get(project_id)
        if existing is not None:
            if existing.user_id != user_id:
                raise BootstrapError("bootstrap_project_not_owned")
            return existing
        frozen_members = tuple(sorted(set(member_ids)))
        if not frozen_members:
            raise BootstrapError("bootstrap_members_required")
        if not project_id or not selection_id or not user_id:
            raise BootstrapError("bootstrap_identity_required")
        bootstrap = ProjectBootstrap(
            bootstrap_id=_bootstrap_id(project_id, selection_id, frozen_members),
            user_id=user_id,
            project_id=project_id,
            selection_id=selection_id,
            member_ids=frozen_members,
            selected_listing_count=len(frozen_members),
        )
        self._bootstraps_by_project[project_id] = bootstrap
        return bootstrap

    def update_status(self, *, user_id: str, project_id: str, status: str) -> ProjectBootstrap:
        """Record a worker lifecycle transition without changing frozen membership."""

        bootstrap = self._bootstraps_by_project.get(project_id)
        if bootstrap is None or bootstrap.user_id != user_id:
            raise BootstrapError("bootstrap_project_not_owned")
        if status not in BOOTSTRAP_STATUSES:
            raise BootstrapError("bootstrap_status_invalid")
        if bootstrap.status in TERMINAL_BOOTSTRAP_STATUSES and status != bootstrap.status:
            raise BootstrapError("bootstrap_terminal")
        updated = replace(bootstrap, status=status)
        self._bootstraps_by_project[project_id] = updated
        return updated


def _bootstrap_id(project_id: str, selection_id: str, member_ids: tuple[str, ...]) -> str:
    payload = json.dumps(
        {"project_id": project_id, "selection_id": selection_id, "member_ids": member_ids},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode()).hexdigest()
