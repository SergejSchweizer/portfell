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


def test_hosted_api_uses_a_current_user_provider_boundary() -> None:
    hosted_api = (REPOSITORY_ROOT / "src" / "portfell" / "hosted_api.py").read_text(
        encoding="utf-8"
    )
    hosted_api_state = (REPOSITORY_ROOT / "src" / "portfell" / "hosted_api_state.py").read_text(
        encoding="utf-8"
    )

    assert "\nLOCAL_WORKSPACE_USER_ID =" not in hosted_api
    assert "class CurrentUserProvider(Protocol):" in hosted_api_state
    assert '"CurrentUserProvider"' in hosted_api
    assert "current_user_provider: CurrentUserProvider | None" in hosted_api


def test_active_backlog_contains_only_unfinished_records() -> None:
    backlog = (REPOSITORY_ROOT / "BACKLOG.md").read_text(encoding="utf-8")
    active_start = backlog.index("## Active Monthly-Distribution ETF Multivariate PR Stack")
    completed_start = backlog.index("## Completed PR History")
    active = backlog[active_start:completed_start]

    assert "## Active Three-Module Portfell UI PR Stack" not in backlog
    assert "## Active Hosted Multi-Tenant Portfell PR Stack" not in backlog
    assert not re.search(
        r"^Git status: (merged|complete|pushed|closed|superseded)\b", active, re.MULTILINE
    )

    for pr_number in range(143, 151):
        assert f"| PR{pr_number} |" in backlog[completed_start:]

    assert "### PR143." not in active
    assert "### Monthly-Distribution ETF Multivariate Series Completion Gate" in active


def test_backlog_places_only_completed_records_after_the_active_series() -> None:
    backlog = (REPOSITORY_ROOT / "BACKLOG.md").read_text(encoding="utf-8")
    completed = backlog.index("## Completed PR History")

    assert "## Completed And Superseded Detailed Records" not in backlog
    history = backlog[completed:]
    assert "### Completed Hosted Stack Records" not in history
    assert "### Completed UI Foundation Record" not in history
    assert "| PR92 |" in history
    assert "| PR229 |" in history


def test_quality_gates_are_documented_centrally() -> None:
    backlog = (REPOSITORY_ROOT / "BACKLOG.md").read_text(encoding="utf-8")
    gate = backlog.split("## Series Completion Gate", maxsplit=1)[1].split(
        "## Update Rules", maxsplit=1
    )[0]
    gates = (REPOSITORY_ROOT / "GATES.md").read_text(encoding="utf-8")

    for backlog_text in (
        "PR143 through PR150 are the first active series",
        "PR151 through PR155 then implement",
        "four modules only after",
        "[GATES.md](GATES.md)",
    ):
        assert backlog_text in gate

    for gates_text in (
        "## `pr-quality`",
        "## `merge-gate`",
        "## Auto-Merge",
        "## Branch Protection",
        "Ruff lint and format",
        "pyright",
        "coverage report --fail-under=95",
        "python -m portfell.schema_validation",
        "python -m portfell.architecture_checks",
        "pytest-xdist: pytest -n auto",
    ):
        assert gates_text in gates


def test_hosted_security_architecture_maps_goals_to_backlog_records() -> None:
    architecture = (REPOSITORY_ROOT / "ARCHITECTURE.md").read_text(encoding="utf-8")
    decisions = (REPOSITORY_ROOT / "DECISIONS.md").read_text(encoding="utf-8")
    risks = (REPOSITORY_ROOT / "RISKS.md").read_text(encoding="utf-8")
    goals = (REPOSITORY_ROOT / "GOALS.md").read_text(encoding="utf-8")
    hosted = (REPOSITORY_ROOT / "docs/hosted_security_architecture.md").read_text(encoding="utf-8")
    backlog = (REPOSITORY_ROOT / "BACKLOG.md").read_text(encoding="utf-8")

    assert "docs/hosted_security_architecture.md" in architecture
    assert "D016. Use PostgreSQL-First User-Key-Backed Hosted Architecture" in decisions
    assert "R010. Hosted Multi-Tenant Access Can Leak Provider Data Or Credentials" in risks
    assert "multi-tenant but user-key-backed" in goals

    for boundary in (
        "Browser",
        "Web app",
        "API service",
        "PostgreSQL",
        "External key-encryption key",
        "Shared immutable store",
        "EODHD",
    ):
        assert boundary in hosted

    for forbidden in (
        "Plaintext EODHD keys",
        "global current-selection pointers",
        "Public-hosted mode",
    ):
        assert forbidden in hosted

    for pr_number, requirement in HOSTED_REQUIREMENTS_BY_PR.items():
        assert f"| {requirement} | PR{pr_number} |" in hosted
    assert "## Active Monthly-Distribution ETF Multivariate PR Stack" in backlog


def test_github_quality_workflows_validate_and_use_squash_subject() -> None:
    merge_gate_workflow = (REPOSITORY_ROOT / ".github/workflows/merge-gate.yml").read_text(
        encoding="utf-8"
    )
    pr_workflow = (REPOSITORY_ROOT / ".github/workflows/pr-quality.yml").read_text(encoding="utf-8")
    merge_workflow = (REPOSITORY_ROOT / ".github/workflows/auto-merge.yml").read_text(
        encoding="utf-8"
    )

    assert "pr-lint-quality" in pr_workflow
    assert "pr-type-quality" in pr_workflow
    assert "pr-unit-tests-${{ matrix.shard }}" in pr_workflow
    assert "pr-integration-tests-${{ matrix.shard }}" in pr_workflow
    assert "merge-lint-quality" in merge_gate_workflow
    assert "merge-type-quality" in merge_gate_workflow
    assert "merge-unit-tests-${{ matrix.shard }}" in merge_gate_workflow
    assert "merge-integration-tests-${{ matrix.shard }}" in merge_gate_workflow
    assert "scripts/pytest_shard.py" in pr_workflow
    assert "scripts/pytest_shard.py" in merge_gate_workflow
    assert "--suite unit" in pr_workflow
    assert "--suite integration" in pr_workflow
    assert "-n auto" in pr_workflow
    assert "-n auto" in merge_gate_workflow
    assert "uv run portfell-quality --commits-only" in pr_workflow
    assert "uv run portfell-quality --commits-only" in merge_gate_workflow
    assert "uv run python -m portfell.schema_validation" in merge_gate_workflow
    assert "uv run coverage combine coverage-shards" in merge_gate_workflow
    assert "uv run coverage report --fail-under=95" in merge_gate_workflow
    assert 'uv run portfell-quality --squash-subject "$SQUASH_SUBJECT"' in pr_workflow
    assert "pull_request:" not in merge_gate_workflow
    assert "workflows: [pr-quality]" in merge_workflow
    assert "is still a draft; skipping auto-merge" in merge_workflow
    assert "Invalid squash subject" in merge_workflow
    assert '--squash --delete-branch --subject "$PR_TITLE"' in merge_workflow
