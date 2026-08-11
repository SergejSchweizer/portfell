from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import portfell.shared_market_cron as cron
from portfell.shared_market_cron import (
    BEGIN_MARKER,
    END_MARKER,
    SCHEDULE,
    TIMEZONE,
    cron_block,
    replace_managed_block,
)


def test_cron_block_uses_the_operations_service_without_secret_values(tmp_path: Path) -> None:
    block = cron_block(tmp_path / "project", tmp_path / "logs" / "refresh.log")

    assert BEGIN_MARKER in block and END_MARKER in block
    assert f"CRON_TZ={TIMEZONE}" in block
    assert block.count(SCHEDULE) == 1
    assert "/usr/bin/flock -n" in block
    assert "-f /" in block
    assert "compose.production.yaml" in block
    assert "--profile operations run --rm --no-deps shared-market-refresh" in block
    assert "EODHD" not in block and "KEK" not in block


def test_replace_managed_block_is_idempotent_and_preserves_unrelated_crontab() -> None:
    original = "MAILTO=ops@example.test\n0 1 * * * /usr/local/bin/backup\n"
    block = f"{BEGIN_MARKER}\nmanaged\n{END_MARKER}"

    installed = replace_managed_block(original, block)

    assert replace_managed_block(installed, block) == installed
    assert replace_managed_block(installed, None) == original


def test_replace_managed_block_rejects_an_incomplete_existing_block() -> None:
    with pytest.raises(ValueError, match="incomplete"):
        replace_managed_block(f"{BEGIN_MARKER}\n", "replacement")


def test_main_installs_statuses_and_uninstalls_only_the_managed_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "compose.yaml").touch()
    (root / "compose.production.yaml").touch()
    data_root = tmp_path / "portfell"
    log_path = data_root / "logs" / "shared-market-refresh.log"
    crontab = "MAILTO=ops@example.test\n"
    calls: list[str] = []

    monkeypatch.setattr(cron, "_read_crontab", lambda: crontab)
    monkeypatch.setattr(cron, "_validate_production_paths", lambda _root, _log: None)
    monkeypatch.setattr(cron, "_validate_project_data_root", lambda _root, _data_root: None)
    monkeypatch.setattr(cron, "_compose_config", lambda _: calls.append("config"))
    monkeypatch.setattr(
        cron, "_run_once", lambda _root, _log, *, dry_run=False: calls.append(f"run:{dry_run}") or 0
    )
    written: list[str] = []
    monkeypatch.setattr(cron, "_write_crontab", written.append)

    args = ["--project-root", str(root), "--data-root", str(data_root), "--log-path", str(log_path)]
    assert cron.main(["install", *args]) == 0
    assert calls == ["config", "run:True"]
    assert BEGIN_MARKER in written[-1]
    installed = written[-1]
    monkeypatch.setattr(cron, "_read_crontab", lambda: installed)

    assert cron.main(["status", *args]) == 0
    assert '"installed": true' in capsys.readouterr().out
    assert cron.main(["uninstall", *args]) == 0
    assert written[-1] == crontab


def test_cron_subprocess_helpers_and_missing_project_are_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "project"
    root.mkdir()
    log_path = tmp_path / "logs" / "refresh.log"
    log_path.parent.mkdir()
    commands: list[tuple[list[str], dict[str, object]]] = []

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        commands.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="existing")

    monkeypatch.setattr(cron.subprocess, "run", fake_run)
    assert cron._run_once(root, log_path, dry_run=True) == 0
    cron._compose_config(root)
    assert "--dry-run" in commands[0][0]
    assert commands[1][0][-1] == "config"
    assert cron._read_crontab() == "existing"
    cron._write_crontab("managed\n")
    assert commands[-1][0] == ["crontab", "-"]

    with pytest.raises(SystemExit, match="compose.yaml"):
        cron.main(["status", "--project-root", str(tmp_path / "missing")])


def test_production_paths_require_the_final_bind_root_log_path(tmp_path: Path) -> None:
    root = tmp_path / "portfell"
    root.mkdir()
    log_path = root / "logs" / "different.log"

    with pytest.raises(ValueError, match="log path"):
        cron._validate_production_paths(root, log_path)


def test_production_paths_reject_an_unapproved_data_root(tmp_path: Path) -> None:
    root = tmp_path / "portfell"
    root.mkdir()
    log_path = root / "logs" / cron.PRODUCTION_LOG_NAME

    with pytest.raises(ValueError, match="preflight"):
        cron._validate_production_paths(root, log_path)


def test_project_environment_must_select_the_same_data_root(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / ".env.local").write_text("PORTFELL_DATA_ROOT=/wrong/path\n", encoding="utf-8")

    with pytest.raises(ValueError, match="must match"):
        cron._validate_project_data_root(root, cron.PRODUCTION_DATA_ROOT)
