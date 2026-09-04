"""PR426 runbook structure and safety checks."""

from __future__ import annotations

from pathlib import Path


def test_runbook_has_toc_and_all_operator_sections() -> None:
    text = Path("docs/MODULES_RUNBOOK.md").read_text()
    for heading in (
        "## Contents",
        "## Topology",
        "## Prerequisites",
        "## Build and deploy",
        "## Health and logs",
        "## Backup and restore",
        "## Permissions",
        "## Cutover and rollback",
        "## Failure isolation",
    ):
        assert heading in text
    assert "postgres-password" in text
    assert "never" in text.casefold()


def test_runbook_links_canonical_compose_and_has_no_credentials() -> None:
    text = Path("docs/MODULES_RUNBOOK.md").read_text()
    assert "compose.yaml" in text
    assert "exactly one Application container" in text
    assert "portfell-app" in text
    assert "2156399" not in text
    assert "postgres://" not in text
