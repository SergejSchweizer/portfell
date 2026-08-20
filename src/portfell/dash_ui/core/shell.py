# pyright: reportMissingImports=false, reportUnknownArgumentType=false, reportUnknownMemberType=false, reportUnknownVariableType=false
"""Shared Portfell Dash shell."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from dash import dcc, html

from portfell.dash_ui.core.ids import SHELL_NAMESPACE, component_id
from portfell.dash_ui.core.navigation import navigation_items


def build_shell(
    *,
    project_slug: str,
    projects: Iterable[Mapping[str, str]],
    stage_statuses: Mapping[str, str],
    page_content: object,
    base_prefix: str = "/dash",
) -> object:
    """Build the presentation shell without granting authorization from URL state."""

    items = navigation_items(project_slug=project_slug, base_prefix=base_prefix)
    project_options = [
        {"label": project.get("label", project["slug"]), "value": project["slug"]}
        for project in projects
    ]
    return html.Div(
        [
            html.Header(
                [
                    html.Strong("Portfell"),
                    dcc.Dropdown(
                        id=component_id(SHELL_NAMESPACE, "project-selector"),
                        options=project_options,
                        value=project_slug,
                        clearable=False,
                    ),
                ],
                className="portfell-header",
            ),
            html.Div(
                [
                    html.A(
                        [html.Span(item.label), html.Small(stage_statuses.get(item.workflow.value, "not_run"))],
                        href=item.href,
                        className="workflow-link",
                    )
                    for item in items
                ],
                className="workflow-overview",
            ),
            html.Div(
                [
                    html.Nav(
                        [html.A(item.label, href=item.href, className="workflow-link") for item in items],
                        className="workflow-sidebar",
                    ),
                    html.Main(page_content, id=component_id(SHELL_NAMESPACE, "page-region")),
                ],
                className="portfell-body",
            ),
        ],
        id=component_id(SHELL_NAMESPACE, "root"),
        className="portfell-shell",
    )
