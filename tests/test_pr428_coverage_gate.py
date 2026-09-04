"""PR428 coverage threshold and transitional-scope contract tests."""

from __future__ import annotations

from pathlib import Path

from portfell.quality import MAIN_COVERAGE_COMMAND


def test_quality_and_documentation_require_92_percent() -> None:
    assert "--cov-fail-under=92" in MAIN_COVERAGE_COMMAND
    docs = Path("docs/contracts/coverage-gate-v1.md").read_text()
    assert "92%" in docs
    assert "PR427" in docs


def test_coverage_omits_only_named_transitional_files() -> None:
    config = Path("pyproject.toml").read_text()
    for path in (
        "src/portfell/app_services/workspace.py",
        "src/portfell/app_services/analysis_compute.py",
        "src/portfell/univariate_refresh.py",
        "src/portfell/run_locks.py",
        "src/portfell/selection_filters.py",
    ):
        assert path in config
