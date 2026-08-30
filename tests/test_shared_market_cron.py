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


def test_cron_block_uses_the_existing_worker_without_secret_values(tmp_path: Path) -> None:
    block = cron_block(tmp_path / "project", tmp_path / "logs" / "refresh.log")

    assert SCHEDULE == "0 9 * * 0"
    assert BEGIN_MARKER in block and END_MARKER in block
    assert f"CRON_TZ={TIMEZONE}" in block
    assert block.count(SCHEDULE) == 1
    assert "/usr/bin/flock -n" in block
    assert "-f /" in block
    assert "compose.production.yaml" in block
    assert "exec -T project-bootstrap-worker python -m portfell.shared_market_refresh" in block
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


def test_main_is_disabled_without_touching_crontab_compose_or_filesystem(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    touched: list[str] = []
    monkeypatch.setattr(cron, "_read_crontab", lambda: touched.append("crontab") or "")
    monkeypatch.setattr(cron, "_compose_config", lambda _: touched.append("compose"))
    monkeypatch.setattr(cron, "_run_once", lambda *_args, **_kwargs: touched.append("run") or 0)

    assert cron.main(["status"]) == 0
    assert '"enabled": false' in capsys.readouterr().out
    assert cron.main(["install"]) == 2
    assert "market_filesystem_plane_removed" in capsys.readouterr().out
    assert touched == []


def test_legacy_helpers_are_not_reachable_through_the_disabled_entrypoint(
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
    assert commands[0][0][len(cron._compose_command(root))] == "--dry-run"
    assert commands[0][0][-1] == "portfell.shared_market_refresh"
    assert commands[0][1]["stdout"] is cron.subprocess.DEVNULL
    assert commands[1][0][-1] == "config"
    assert cron._read_crontab() == "existing"
    cron._write_crontab("managed\n")
    assert commands[-1][0] == ["crontab", "-"]

    assert cron.main(["status", "--project-root", str(tmp_path / "missing")]) == 0


def test_production_paths_require_the_final_bind_root_log_path(tmp_path: Path) -> None:
    root = tmp_path / "portfell"
    root.mkdir()
    log_path = root / "logs" / "different.log"

    with pytest.raises(ValueError, match="market_filesystem_plane_removed"):
        cron._validate_production_paths(root, log_path)


def test_production_paths_reject_an_unapproved_data_root(tmp_path: Path) -> None:
    root = tmp_path / "portfell"
    root.mkdir()
    log_path = root / "logs" / cron.PRODUCTION_LOG_NAME

    with pytest.raises(ValueError, match="market_filesystem_plane_removed"):
        cron._validate_production_paths(root, log_path)


def test_project_environment_must_select_the_same_data_root(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    with pytest.raises(ValueError, match="market_filesystem_plane_removed"):
        cron._validate_project_data_root(root, cron.PRODUCTION_DATA_ROOT)
