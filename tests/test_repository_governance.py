from __future__ import annotations

import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TYPED_BRANCH_PATTERN = re.compile(r"^(feat|fix|refactor|docs|chore)/[a-z0-9]+(?:-[a-z0-9]+)*$")

FOUR_PAGE_PR_TITLES = {
    110: "Canonical Workflow State And Four-Page API Contract",
    111: "Metadata Header, Metadata Builder, And Real Quote Progress",
    112: "Functional Univariate Statistics Page",
    113: "Functional Univariate Selection Page",
    114: "Functional Bivariate Statistics Page",
    115: "Sequential Navigation, Final Legacy Deletion, And End-To-End Gate",
}
FOUR_PAGE_PR_DEPENDENCIES = {
    110: "PR189",
    111: "PR110",
    112: "PR111",
    113: "PR112",
    114: "PR113",
    115: "PR114",
}
FOUR_PAGE_GITHUB_PRS = {
    110: 190,
    111: 197,
    112: 192,
    113: 193,
    114: 194,
    115: 195,
}
PROJECT_SIDEBAR_PR_TITLES = {
    117: "Persisted Current-Project Context And Project-Scoped Workflow API",
    118: "Desktop Sidebar, Project Dropdown, And Workflow Hierarchy",
    119: "Responsive Sidebar Drawer, Accessibility, And Completion Gate",
}
PROJECT_SIDEBAR_PR_DEPENDENCIES = {
    117: "PR116",
    118: "PR117",
    119: "PR118",
}
PROJECT_SIDEBAR_PR_STATUSES = {
    117: "pushed",
    118: "pushed",
    119: "pushed",
}
PROJECT_SIDEBAR_PR_URLS = {
    117: "https://github.com/SergejSchweizer/portfell/pull/199",
    118: "https://github.com/SergejSchweizer/portfell/pull/200",
    119: "https://github.com/SergejSchweizer/portfell/pull/201",
}
SIMPLE_UI_PR_TITLES = {
    120: "Platform-Inspired Visual Foundations And Core Components",
    121: "Platform-Inspired Header, Sidebar, And Navigation Refinement",
    122: "Platform-Inspired Forms, Progress, Tables, And Page States",
    123: "Simple UI Motion, Accessibility, Visual Regression, And Completion Gate",
}
SIMPLE_UI_PR_DEPENDENCIES = {
    120: "PR119",
    121: "PR120",
    122: "PR121",
    123: "PR122",
}
SIMPLE_UI_PR_STATUSES = {
    120: "pushed",
    121: "pushed",
    122: "not started",
    123: "not started",
}
SIMPLE_UI_PR_URLS = {
    120: "https://github.com/SergejSchweizer/portfell/pull/245",
    121: "https://github.com/SergejSchweizer/portfell/pull/246",
    122: "TBD",
    123: "TBD",
}

HOSTED_REQUIREMENTS_BY_PR = {
    84: "Architecture decision, threat model, and prohibited designs",
    85: "PostgreSQL catalog, roles, migrations, and RLS",
    86: "Google-only OIDC and server-side sessions",
    87: "Encrypted EODHD credential vault and KEK rotation",
    88: "Shared content-addressed market observation store",
    89: "User grants, provenance, and immutable snapshots",
    90: "User-key-backed ingestion and refresh planning",
    91: "Scoped analytical input boundary and local adapter compatibility",
    92: "Content-addressed univariate and return artifact cache",
    93: "Content-addressed bivariate cache and exact alignment",
    94: "Content-addressed portfolio, backtest, and report artifacts",
    95: "Docker Compose hosted development runtime",
    96: "FastAPI user, credential, download, project, and analysis API",
    97: "Google-authenticated Web UI and research funnel",
    98: "Public-repository CI, supply-chain, and deployment hardening",
    99: "Licensing, privacy, retention, backup, restore, and key-rotation readiness",
    100: "End-to-end hosted cutover and multi-user proof",
}


def _pr_section(backlog: str, pr_number: int) -> str:
    start = backlog.index(f"### PR{pr_number}.")
    next_pr = backlog.find("\n### PR", start + 1)
    next_section = backlog.find("\n## ", start + 1)
    candidates = [value for value in (next_pr, next_section) if value != -1]
    return backlog[start : len(backlog) if not candidates else min(candidates)]


def test_active_backlog_contains_only_unfinished_records() -> None:
    backlog = (REPOSITORY_ROOT / "BACKLOG.md").read_text(encoding="utf-8")
    assert "## 0. Single-file authority" in backlog
    assert "## 3. Source cutover and simplification series — PR308–PR343" in backlog
    assert "## 4. Plotly Dash + clean database full-replacement series — PR344–PR360" in backlog
    assert "### PR308 — Xetra source contract foundation" in backlog
    assert "### PR360 — Production cutover, destructive removal" in backlog
    assert "PR308\n  |\nPR309 || PR310 || PR311 || PR312 || PR313 || PR314" in backlog


def test_backlog_places_only_completed_records_after_the_active_series() -> None:
    backlog = (REPOSITORY_ROOT / "BACKLOG.md").read_text(encoding="utf-8")

    assert "Historical backlog text" in backlog
    assert "no unfinished legacy UI/database work" in backlog
    assert "## Completed PR History" not in backlog
    assert "## Active Hosted Simplicity And Interactive Performance PR Stack" not in backlog


def test_quality_gates_are_documented_centrally() -> None:
    backlog = (REPOSITORY_ROOT / "BACKLOG.md").read_text(encoding="utf-8")
    gates = (REPOSITORY_ROOT / "GATES.md").read_text(encoding="utf-8")

    for backlog_text in (
        "`GATES.md` remains the sole authority",
        "focused tests plus `uv run portfell-quality pr`",
        "`uv run portfell-quality merge`",
        "## 6. Final series completion gate",
    ):
        assert backlog_text in backlog

    for gates_text in (
        "## Local merge gate",
        "uv run portfell-quality merge",
        "## GitHub `merge-gate`",
        "Ruff lint and format",
        "strict Pyright",
        "--cov-fail-under=90",
        "merge-unit-tests-1..4",
        "merge-integration-tests-1..4",
        "failed/skipped/zero-step workflow runs are never treated as success",
    ):
        assert gates_text in gates


def test_final_architecture_maps_backlog_to_runtime_boundaries() -> None:
    architecture = (REPOSITORY_ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
    backlog = (REPOSITORY_ROOT / "BACKLOG.md").read_text(encoding="utf-8")

    for boundary in (
        "FastAPI + Plotly Dash",
        "portfell_dash",
        "xetra_loader",
        "`dash_app`",
        "`app_state`",
        "`market_source`",
        "There is no production React/Vite/TypeScript/TanStack application",
    ):
        assert boundary in architecture
    assert "## 1. Final target architecture — hard decision" in backlog


def test_github_merge_gate_runs_once_and_uses_auto_rebase_completion() -> None:
    merge_gate_workflow = (REPOSITORY_ROOT / ".github/workflows/merge-gate.yml").read_text(
        encoding="utf-8"
    )
    merge_workflow = (REPOSITORY_ROOT / ".github/workflows/auto-rebase.yml").read_text(
        encoding="utf-8"
    )

    assert "merge-lint-quality" in merge_gate_workflow
    assert "merge-type-quality" in merge_gate_workflow
    assert "merge-unit-tests-${{ matrix.shard }}" in merge_gate_workflow
    assert "merge-integration-tests-${{ matrix.shard }}" in merge_gate_workflow
    assert "scripts/pytest_shard.py" in merge_gate_workflow
    assert "-n auto" in merge_gate_workflow
    assert "uv run portfell-quality --commits-only" in merge_gate_workflow
    assert "uv run python -m portfell.schema_validation" in merge_gate_workflow
    assert "uv run coverage combine coverage-shards" in merge_gate_workflow
    assert "uv run coverage report --fail-under=95" in merge_gate_workflow
    assert "pull_request:" in merge_gate_workflow
    # Stacked PRs must also be gated against their immediate base. The final rebase to main
    # triggers the same pull-request workflow again against the integration base.
    assert "branches: [main]" not in merge_gate_workflow
    assert "workflow_dispatch:" in merge_gate_workflow
    assert "push:" not in merge_gate_workflow
    assert not (REPOSITORY_ROOT / ".github/workflows/pr-quality.yml").exists()
    assert "workflows: [merge-gate]" in merge_workflow
    assert "runs-on: [self-hosted, Linux, X64, ubuntu-latest]" in merge_workflow
    assert "is still a draft; skipping auto-rebase" in merge_workflow
    assert "Invalid squash subject" in merge_workflow
    assert "--rebase --delete-branch" in merge_workflow
