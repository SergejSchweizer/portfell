"""Install and operate the local nightly shared-market refresh cron job."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

BEGIN_MARKER = "# BEGIN PORTFELL SHARED MARKET REFRESH"
END_MARKER = "# END PORTFELL SHARED MARKET REFRESH"
SCHEDULE = "15 2 * * *"
TIMEZONE = "Europe/Amsterdam"


def cron_block(project_root: Path, log_path: Path) -> str:
    """Render the one managed cron block without exposing any secret value."""

    root = _absolute(project_root, "project root")
    log = _absolute(log_path, "log path")
    lock_path = root / ".shared-market-refresh.cron.lock"
    command = (
        f"/usr/bin/flock -n {lock_path} /usr/bin/docker compose --project-directory {root} "
        f"--env-file {root / '.env.local'} --profile operations run --rm --no-deps "
        f"shared-market-refresh >> {log} 2>&1"
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
    """Install, inspect, run once, or remove the managed local cron entry."""

    parser = argparse.ArgumentParser(
        description="Manage Portfell's shared-market refresh cron job."
    )
    parser.add_argument("action", choices=("install", "status", "run-once", "uninstall"))
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--log-path", type=Path, default=Path("/var/log/portfell/shared-market-refresh.log")
    )
    args = parser.parse_args(argv)
    root = _absolute(args.project_root, "project root")
    log_path = _absolute(args.log_path, "log path")
    if not (root / "compose.yaml").is_file():
        raise SystemExit("project root must contain compose.yaml")
    if args.action == "run-once":
        return _run_once(root, log_path)
    current = _read_crontab()
    installed = BEGIN_MARKER in current and END_MARKER in current
    if args.action == "status":
        print(json.dumps({"installed": installed, "schedule": SCHEDULE, "timezone": TIMEZONE}))
        return 0 if installed else 1
    replacement = cron_block(root, log_path) if args.action == "install" else None
    if args.action == "install":
        _compose_config(root)
        _run_once(root, log_path, dry_run=True)
    _write_crontab(replace_managed_block(current, replacement))
    return 0


def _run_once(project_root: Path, log_path: Path, *, dry_run: bool = False) -> int:
    command = [
        "/usr/bin/docker",
        "compose",
        "--project-directory",
        str(project_root),
        "--env-file",
        str(project_root / ".env.local"),
        "--profile",
        "operations",
        "run",
        "--rm",
        "--no-deps",
        "shared-market-refresh",
    ]
    if dry_run:
        command.append("--dry-run")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        return subprocess.run(command, check=False, stdout=log, stderr=subprocess.STDOUT).returncode


def _compose_config(project_root: Path) -> None:
    subprocess.run(
        [
            "/usr/bin/docker",
            "compose",
            "--project-directory",
            str(project_root),
            "--env-file",
            str(project_root / ".env.local"),
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


if __name__ == "__main__":
    raise SystemExit(main())
