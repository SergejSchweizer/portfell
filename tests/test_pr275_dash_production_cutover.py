from __future__ import annotations

from pathlib import Path


def _service_names(compose: str) -> tuple[str, ...]:
    lines = compose.splitlines()
    start = lines.index("services:") + 1
    names: list[str] = []
    for line in lines[start:]:
        if line and not line.startswith(" "):
            break
        if line.startswith("  ") and not line.startswith("    ") and line.endswith(":"):
            names.append(line.strip()[:-1])
    return tuple(names)


def test_pr275_final_compose_has_exactly_three_long_running_services() -> None:
    compose = Path("compose.yaml").read_text(encoding="utf-8")
    assert _service_names(compose) == (
        "postgres",
        "app",
        "project-bootstrap-worker",
    )
    assert "apps/web" not in compose
    assert "compose.dash" not in compose
    assert "node" not in compose.casefold()


def test_pr275_production_python_image_installs_dash_without_node() -> None:
    requirements = Path("apps/api/requirements-ui.txt").read_text(encoding="utf-8").splitlines()
    assert requirements == ["dash==3.2.0"]
    dockerfile = Path("apps/api/Dockerfile").read_text(encoding="utf-8")
    assert "requirements-ui.txt" in dockerfile
    assert "npm" not in dockerfile.casefold()
    assert "node" not in dockerfile.casefold()


def test_pr275_pr_gate_keeps_lint_type_unit_integration_image_parallel() -> None:
    workflow = Path(".github/workflows/pr-quality.yml").read_text(encoding="utf-8")
    for job in ("  lint:", "  type:", "  unit:", "  integration:", "  dash-image:"):
        assert job in workflow
    assert "needs: [lint, type, unit, integration, dash-image]" in workflow
    assert "matrix: {shard: [1, 2, 3, 4]}" in workflow
    assert "uv run pyright" in workflow
    assert "uv run ruff check ." in workflow


def test_pr275_merge_gate_combines_eight_shards_and_enforces_95_percent() -> None:
    workflow = Path(".github/workflows/merge-gate.yml").read_text(encoding="utf-8")
    assert "matrix: {shard: [1, 2, 3, 4]}" in workflow
    assert "coverage-unit-${{ matrix.shard }}" in workflow
    assert "coverage-integration-${{ matrix.shard }}" in workflow
    assert "uv run coverage combine coverage-shards" in workflow
    assert "uv run coverage report --fail-under=95" in workflow
    assert "needs: [lint, type, unit, integration, app-image]" in workflow


def test_pr275_gates_document_remains_single_95_percent_authority() -> None:
    gates = Path("GATES.md").read_text(encoding="utf-8")
    assert "**95%** line coverage" in gates
    assert "Coverage threshold is 95%" in gates
    assert "React/TypeScript/Vite/Node are no longer production dependencies" in gates
