"""Typed presentation gateway boundary for the Dash package."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from portfell.dash_ui.core.routes import WorkflowId

Presentation = Mapping[str, object]


class DashResearchGateway(Protocol):
    """Application-facing operations available to presentation code.

    Implementations own authorization and persistence. Dash receives only serialized
    presentation values and opaque logical command identifiers.
    """

    def project_context(self, *, project_slug: str) -> Presentation: ...

    def page_view(self, *, project_slug: str, workflow: WorkflowId) -> Presentation: ...

    def run_status(self, *, project_slug: str, stage_id: WorkflowId) -> Presentation: ...

    def start_run(
        self,
        *,
        project_slug: str,
        stage_id: WorkflowId,
        command_key: str,
        settings: Mapping[str, object],
    ) -> Presentation: ...

    def selection_settings(self, *, project_slug: str, stage_id: WorkflowId) -> Presentation: ...

    def multivariate_settings(self, *, project_slug: str) -> Presentation: ...

    def decision_section(
        self, *, project_slug: str, run_id: str, section_id: str
    ) -> Presentation: ...

    def universe_history(self, *, project_slug: str, stage_id: str) -> Presentation: ...
