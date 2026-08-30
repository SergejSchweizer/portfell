"""Disabled compatibility entry point for the retired market-filesystem cron."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

BEGIN_MARKER = "# BEGIN PORTFELL SHARED MARKET REFRESH"
END_MARKER = "# END PORTFELL SHARED MARKET REFRESH"
SCHEDULE = "0 9 * * 0"
TIMEZONE = "Europe/Amsterdam"
PRODUCTION_DATA_ROOT = Path("/volume2/docker/portfell")
PRODUCTION_LOG_NAME = "shared-market-refresh.log"


def cron_block(project_root: Path, log_path: Path) -> str:
    """Render the one managed cron block without exposing any secret value."""

    root = _absolute(project_root, "project root")
    log = _absolute(log_path, "log path")
    lock_path = root / ".shared-market-refresh.cron.lock"
    command = " ".join(
        (
            f"/usr/bin/flock -n {lock_path}",
            *_compose_command(root),
            "exec -T project-bootstrap-worker python -m portfell.shared_market_refresh",
            f">> {log} 2>&1",
        )
    )
    return "\n".join(
        (
            BEGIN_MARKER,
            "SHELL=/bin/bash",
            f"CRON_TZ={TIMEZONE}",
            f"{SCHEDULE} {command}",
            END_MARKER,
        )
    )


def replace_managed_block(current: str, replacement: str | None) -> str:
    """Replace only Portfell's delimited cron block, retaining unrelated bytes."""

    start = current.find(BEGIN_MARKER)
    if start < 0:
        suffix = (("\n" if current else "") + replacement) if replacement else ""
        return current.rstrip("\n") + suffix + "\n"
    end = current.find(END_MARKER, start)
    if end < 0:
        raise ValueError("managed Portfell cron block is incomplete")
    end += len(END_MARKER)
    prefix = current[:start].rstrip("\n")
    suffix = current[end:].lstrip("\n")
    parts = [part for part in (prefix, replacement, suffix.rstrip("\n")) if part]
    return "\n".join(parts) + ("\n" if parts else "")


def main(argv: Sequence[str] | None = None) -> int:
    """Fail closed: the market filesystem cron is no longer an executable plane.

    The console-script name remains temporarily so existing operator automation
    receives a deterministic disabled result until PR327 removes the legacy
    refresh surface completely.  It must not inspect paths, install a cron
    block, execute Compose, or start a provider refresh.
    """

    parser = argparse.ArgumentParser(
        description="The retired Portfell shared-market cron is disabled."
    )
    parser.add_argument("action", choices=("install", "status", "run-once", "uninstall"))
    parser.add_argument("--project-root", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--data-root", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--log-path", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.action == "status":
        print(json.dumps({"enabled": False, "reason": "market_filesystem_plane_removed"}))
        return 0
    print("shared_market_cron_disabled: market_filesystem_plane_removed")
    return 2


def _run_once(project_root: Path, log_path: Path, *, dry_run: bool = False) -> int:
    command = [*_compose_command(project_root)]
    if dry_run:
        # This is a Docker Compose global option.  Passing it after the service
        # name turns it into the container command and can leave a failed
        # one-off container behind instead of validating the cron contract.
        command.append("--dry-run")
    command.extend(
        (
            "exec",
            "-T",
            "project-bootstrap-worker",
            "python",
            "-m",
            "portfell.shared_market_refresh",
        )
    )
    if dry_run:
        return subprocess.run(
            command, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT
        ).returncode
    with log_path.open("a", encoding="utf-8") as log:
        return subprocess.run(command, check=False, stdout=log, stderr=subprocess.STDOUT).returncode


def _compose_config(project_root: Path) -> None:
    subprocess.run(
        [
            *_compose_command(project_root),
            "config",
        ],
        check=True,
    )


def _read_crontab() -> str:
    result = subprocess.run(["crontab", "-l"], capture_output=True, check=False, text=True)
    return result.stdout if result.returncode in {0, 1} else ""


def _write_crontab(value: str) -> None:
    subprocess.run(["crontab", "-"], input=value, check=True, text=True)


def _absolute(path: Path, name: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_absolute():
        raise ValueError(f"{name} must be absolute")
    return resolved


def _compose_command(project_root: Path) -> tuple[str, ...]:
    """Return the absolute production Compose invocation shared by cron paths."""

    return (
        "/usr/bin/docker",
        "compose",
        "--project-directory",
        str(project_root),
        "--env-file",
        str(project_root / ".env.local"),
        "-f",
        str(project_root / "compose.yaml"),
        "-f",
        str(project_root / "compose.production.yaml"),
    )


def _validate_production_paths(data_root: Path, log_path: Path) -> None:
    """Reject the retired NAS validation path without reading the filesystem."""

    del data_root, log_path
    raise ValueError("market_filesystem_plane_removed")


def _validate_project_data_root(project_root: Path, data_root: Path) -> None:
    """Reject the retired NAS configuration path without reading `.env.local`."""

    del project_root, data_root
    raise ValueError("market_filesystem_plane_removed")


if __name__ == "__main__":
    raise SystemExit(main())
