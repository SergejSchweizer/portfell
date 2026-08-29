from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from portfell.quality import (
    build_parser,
    commands_for_layer,
    commit_range,
    has_pr_scope,
    is_conventional_commit_subject,
    main,
    reflects_branch_name,
    run_commands,
    run_quality_gate,
    validate_commit_message_file,
    validate_conventional_commits,
    validate_squash_subject,
)


def test_pr_gate_has_simple_checks() -> None:
    assert commands_for_layer("pr") == (
        ("ruff", "check", "."),
        ("ruff", "format", "--check", "."),
        ("python", "-m", "portfell.security_gates"),
        ("pyright",),
        ("pytest", "-q", "-n", "auto"),
    )


def test_merge_gate_extends_pr_gate_with_protected_checks() -> None:
    commands = commands_for_layer("merge")

    assert commands[:4] == (
        ("ruff", "check", "."),
        ("ruff", "format", "--check", "."),
        ("python", "-m", "portfell.architecture_checks"),
        ("python", "-m", "portfell.schema_validation"),
    )
    assert commands[4] == ("python", "-m", "portfell.security_gates")
    assert commands[5] == ("pyright",)
    assert commands[6] == (
        "pytest",
        "-n",
        "auto",
        "--cov=portfell",
        "--cov-report=term-missing",
        "--cov-fail-under=90",
    )
    assert commands[-3:] == (
        ("git", "diff", "--quiet"),
        ("git", "diff", "--cached", "--quiet"),
        ("git", "status", "--short", "--untracked-files=all"),
    )
    assert commands_for_layer("main") == commands


def test_run_commands_stops_at_first_failure() -> None:
    calls: list[Sequence[str]] = []

    def runner(command: Sequence[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 2, stdout="", stderr="failed")

    assert run_commands((("ruff", "check", "."), ("pytest",)), runner=runner) == 2
    assert calls == [("ruff", "check", ".")]


def test_merge_gate_fails_on_dirty_status_output() -> None:
    def runner(command: Sequence[str], **_: object) -> subprocess.CompletedProcess[str]:
        stdout = " M README.md\n" if command[0:2] == ("git", "status") else ""
        return subprocess.CompletedProcess(command, 0, stdout=stdout, stderr="")

    assert run_commands((commands_for_layer("merge")[-1],), runner=runner) == 1


def test_conventional_commit_subject_validation() -> None:
    assert is_conventional_commit_subject("feat: add search contracts")
    assert is_conventional_commit_subject("fix(http): redact token")
    assert is_conventional_commit_subject("refactor!: change bronze contract")
    assert not is_conventional_commit_subject("Add search contracts")
    assert not is_conventional_commit_subject("feat add search contracts")


def test_branch_name_is_required_as_the_commit_scope() -> None:
    assert reflects_branch_name(
        "feat(four-page-workflow-state): add workflow contract",
        "four-page-workflow-state",
    )
    assert not reflects_branch_name(
        "feat: add workflow contract",
        "four-page-workflow-state",
    )
    assert has_pr_scope("feat(four-page-workflow-state): add workflow contract")
    assert not has_pr_scope("feat: add workflow contract")
    assert not reflects_branch_name(
        "feat(other-work): add workflow contract",
        "four-page-workflow-state",
    )


def test_validate_conventional_commits_rejects_invalid_branch_subjects() -> None:
    def runner(command: Sequence[str], **_: object) -> subprocess.CompletedProcess[str]:
        if command[0:2] == ("git", "merge-base"):
            return subprocess.CompletedProcess(command, 0, stdout="abc123\n", stderr="")
        if command[0:2] == ("git", "log"):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="Add bad commit\nfeat(config): add config\n",
                stderr="",
            )
        if command[0:3] == ("git", "branch", "--show-current"):
            return subprocess.CompletedProcess(command, 0, stdout="feat/config\n", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    assert validate_conventional_commits(runner=runner) == 1


def test_validate_conventional_commits_rejects_a_different_pr_scope() -> None:
    def runner(command: Sequence[str], **_: object) -> subprocess.CompletedProcess[str]:
        if command[0:2] == ("git", "merge-base"):
            return subprocess.CompletedProcess(command, 0, stdout="abc123\n", stderr="")
        if command[0:2] == ("git", "log"):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="feat(other-pr): add config\n",
                stderr="",
            )
        if command[0:3] == ("git", "branch", "--show-current"):
            return subprocess.CompletedProcess(command, 0, stdout="feat/config\n", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    assert validate_conventional_commits(runner=runner) == 1


def test_commit_range_uses_github_pull_request_base(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_BASE_REF", "agent/rewrite-backlog-four-page-ui")

    def runner(command: Sequence[str], **_: object) -> subprocess.CompletedProcess[str]:
        assert command == (
            "git",
            "merge-base",
            "HEAD",
            "origin/agent/rewrite-backlog-four-page-ui",
        )
        return subprocess.CompletedProcess(command, 0, stdout="abc123\n", stderr="")

    assert commit_range(runner=runner) == "abc123..HEAD"


def test_commit_range_uses_main_for_github_push_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_BASE_REF", "")

    def runner(command: Sequence[str], **_: object) -> subprocess.CompletedProcess[str]:
        assert command == ("git", "merge-base", "HEAD", "origin/main")
        return subprocess.CompletedProcess(command, 0, stdout="abc123\n", stderr="")

    assert commit_range(runner=runner) == "abc123..HEAD"


def test_quality_gate_runs_commands_before_commit_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    calls: list[Sequence[str]] = []

    def runner(command: Sequence[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        if command[0:2] == ("git", "merge-base"):
            return subprocess.CompletedProcess(command, 0, stdout="abc123\n", stderr="")
        if command[0:2] == ("git", "log"):
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="feat(config): add config\n",
                stderr="",
            )
        if command[0:3] == ("git", "branch", "--show-current"):
            return subprocess.CompletedProcess(command, 0, stdout="main\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    assert run_quality_gate("pr", runner=runner) == 0
    pr_commands = list(commands_for_layer("pr"))
    assert calls[: len(pr_commands)] == pr_commands
    assert calls[-2:] == [
        ("git", "log", "--format=%s", "abc123..HEAD"),
        ("git", "branch", "--show-current"),
    ]


def test_validate_commit_message_file(tmp_path: Path) -> None:
    message_file = tmp_path / "COMMIT_EDITMSG"

    def runner(command: Sequence[str], **_: object) -> subprocess.CompletedProcess[str]:
        assert command == ("git", "branch", "--show-current")
        return subprocess.CompletedProcess(command, 0, stdout="main\n", stderr="")

    message_file.write_text("feat: add config\n\nbody\n", encoding="utf-8")
    assert validate_commit_message_file(str(message_file), runner=runner) == 0

    message_file.write_text("Add config\n", encoding="utf-8")
    assert validate_commit_message_file(str(message_file), runner=runner) == 1


def test_validate_squash_subject() -> None:
    def runner(command: Sequence[str], **_: object) -> subprocess.CompletedProcess[str]:
        assert command == ("git", "branch", "--show-current")
        return subprocess.CompletedProcess(command, 0, stdout="main\n", stderr="")

    assert validate_squash_subject("feat(cli): add command", runner=runner) == 0
    assert validate_squash_subject("Add command", runner=runner) == 1


def test_build_parser_describes_portfell_quality_gates() -> None:
    parser = build_parser()

    assert parser.description is not None
    assert "Portfell quality gates" in parser.description


def test_main_validates_commit_message_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    message_file = tmp_path / "COMMIT_EDITMSG"
    message_file.write_text("feat: add config\n", encoding="utf-8")
    monkeypatch.setattr("portfell.quality.branch_slug", lambda **_: None)

    assert main(["--commit-msg-file", str(message_file)]) == 0


def test_main_validates_squash_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("portfell.quality.branch_slug", lambda **_: None)
    assert main(["--squash-subject", "feat(cli): add command"]) == 0


def test_main_validates_only_branch_commits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("portfell.quality.validate_conventional_commits", lambda: 0)

    assert main(["--commits-only"]) == 0


def test_main_requires_layer_without_commit_message_file() -> None:
    with pytest.raises(SystemExit):
        main([])
