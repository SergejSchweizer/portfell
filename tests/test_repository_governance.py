from __future__ import annotations

import re
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TYPED_BRANCH_PATTERN = re.compile(r"^(feat|fix|refactor|docs|chore)/[a-z0-9]+(?:-[a-z0-9]+)*$")

FOUR_PAGE_PR_TITLES = {
    110: "Canonical Workflow State And Four-Page API Contract",
    111: "Metadata Header, Metadata Filter, And Real Quote Progress",
    112: "Functional Univariate Statistics Page",
    113: "Functional Univariate Filter Page",
    114: "Functional Bivariate Statistics Page",
    115: "Sequential Navigation, Final Legacy Deletion, And End-To-End Gate",
}
FOUR_PAGE_PR_DEPENDENCIES = {
    110: "current `main`",
    111: "PR110",
    112: "PR111",
    113: "PR112",
    114: "PR113",
    115: "PR114",
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


def test_four_page_stack_is_first_and_follows_dependency_order() -> None:
    backlog = (REPOSITORY_ROOT / "BACKLOG.md").read_text(encoding="utf-8")
    active_start = backlog.index("## Active Four-Page Portfell UI PR Stack")
    hosted_start = backlog.index("## Active Hosted Multi-Tenant Portfell PR Stack")
    completed_start = backlog.index("## Completed PR History")
    positions: list[int] = []

    assert active_start < hosted_start < completed_start

    for pr_number, title in FOUR_PAGE_PR_TITLES.items():
        heading = f"### PR{pr_number}. {title}"
        position = backlog.index(heading)
        section = _pr_section(backlog, pr_number)
        positions.append(position)

        assert position < hosted_start
        assert f"Depends on: {FOUR_PAGE_PR_DEPENDENCIES[pr_number]}." in section
        assert "Git status: not started. PR: TBD." in section
        assert "Scope:" in section
        assert "Acceptance:" in section
        assert "Security:" in section
        assert "Determinism:" in section
        assert "Idempotency:" in section

        branch_match = re.search(r"^Branch: `([^`]+)`\.$", section, flags=re.MULTILINE)
        assert branch_match is not None, f"PR{pr_number} has no Branch entry"
        assert TYPED_BRANCH_PATTERN.fullmatch(branch_match.group(1))

    assert positions == sorted(positions)


def test_backlog_places_completed_and_superseded_work_at_the_bottom() -> None:
    backlog = (REPOSITORY_ROOT / "BACKLOG.md").read_text(encoding="utf-8")
    completed = backlog.index("## Completed PR History")
    detailed = backlog.index("## Completed And Superseded Detailed Records")
    active = backlog.index("## Active Four-Page Portfell UI PR Stack")
    superseded_funnel = (
        "Data -> Metadata -> Univariate -> Filter -> Diversification"
        " -> Portfolio -> Validation -> Report"
    )

    assert active < completed < detailed
    assert "### Superseded Research Funnel UI Stack" in backlog[detailed:]
    assert "Historical only." in backlog[detailed:]
    assert superseded_funnel not in backlog[:detailed]


def test_four_page_stack_defines_exact_canonical_routes_and_no_retired_metadata_name() -> None:
    backlog = (REPOSITORY_ROOT / "BACKLOG.md").read_text(encoding="utf-8")
    active = backlog[
        backlog.index("## Active Four-Page Portfell UI PR Stack") : backlog.index(
            "## Active Hosted Multi-Tenant Portfell PR Stack"
        )
    ]

    ordered_pages = (
        "metadata_filter",
        "univariate_statistics",
        "univariate_filter",
        "bivariate_statistics",
    )
    positions = [active.index(page) for page in ordered_pages]
    assert positions == sorted(positions)
    assert "canonical Python operation is `fetch_all_metadata`" in active
    assert "`fetch_all_isins` must not be reintroduced" in active


def test_quality_gates_are_documented_centrally() -> None:
    backlog = (REPOSITORY_ROOT / "BACKLOG.md").read_text(encoding="utf-8")
    gate = backlog.split("## Series Completion Gate", maxsplit=1)[1].split(
        "## Update Rules", maxsplit=1
    )[0]
    gates = (REPOSITORY_ROOT / "GATES.md").read_text(encoding="utf-8")

    for backlog_text in (
        "PR110 through PR115",
        "exactly four production pages",
        "server-reported",
        "repository `pr-quality` gate",
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
        assert f"### PR{pr_number}." in backlog


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
