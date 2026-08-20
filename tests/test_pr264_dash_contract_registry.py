from __future__ import annotations

import ast
import inspect

import pytest

from portfell.dash_ui.core import gateway
from portfell.dash_ui.core.ids import NAMESPACES, component_id
from portfell.dash_ui.core.routes import (
    PRODUCTION_DASH_PREFIX,
    TEMPORARY_DASH_PREFIX,
    WORKFLOW_ORDER,
    WORKFLOW_SUFFIX,
    WorkflowId,
    project_route,
)


def test_pr264_freezes_exactly_four_ordered_workflows_and_suffixes() -> None:
    assert WORKFLOW_ORDER == (
        WorkflowId.METADATA_BUILDER,
        WorkflowId.UNIVARIATE_STATISTICS,
        WorkflowId.BIVARIATE_STATISTICS,
        WorkflowId.MULTIVARIATE_STATISTICS,
    )
    assert len(WORKFLOW_ORDER) == len(set(WORKFLOW_ORDER)) == 4
    assert set(WORKFLOW_SUFFIX) == set(WORKFLOW_ORDER)
    assert tuple(WORKFLOW_SUFFIX.values()) == (
        "/metadata-builder",
        "/univariate-statistics",
        "/bivariate-statistics",
        "/multivariate-statistics",
    )


def test_pr264_route_builder_supports_only_temporary_and_production_prefixes() -> None:
    workflow = WorkflowId.MULTIVARIATE_STATISTICS
    assert project_route(
        project_slug="alpha",
        workflow=workflow,
        base_prefix=TEMPORARY_DASH_PREFIX,
    ) == "/dash/projects/alpha/multivariate-statistics"
    assert project_route(
        project_slug="alpha",
        workflow=workflow,
        base_prefix=PRODUCTION_DASH_PREFIX,
    ) == "/projects/alpha/multivariate-statistics"
    with pytest.raises(ValueError):
        project_route(project_slug="alpha", workflow=workflow, base_prefix="/other")


def test_pr264_component_namespaces_are_unique_and_reject_unknown_values() -> None:
    assert len(NAMESPACES) == len(set(NAMESPACES))
    assert component_id("multivariate", "objective") == "multivariate-objective"
    with pytest.raises(ValueError):
        component_id("database", "connection")


def test_pr264_gateway_protocol_has_no_runtime_authority_imports() -> None:
    tree = ast.parse(inspect.getsource(gateway))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports |= {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    forbidden = ("postgres", "database", "provider", "eodhd", "storage", "lake")
    assert not any(token in imported for imported in imports for token in forbidden)
