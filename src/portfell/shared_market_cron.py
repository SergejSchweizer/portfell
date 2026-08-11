"""Install and operate the local nightly shared-market refresh cron job."""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

from portfell.ugreen_nas_data_root_preflight import validate_data_root

BEGIN_MARKER = "# BEGIN PORTFELL SHARED MARKET REFRESH"
END_MARKER = "# END PORTFELL SHARED MARKET REFRESH"
SCHEDULE = "15 2 * * *"
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
            "--profile operations run --rm --no-deps shared-market-refresh",
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
    """Install, inspect, run once, or remove the managed local cron entry."""

    parser = argparse.ArgumentParser(
        description="Manage Portfell's shared-market refresh cron job."
    )
    parser.add_argument("action", choices=("install", "status", "run-once", "uninstall"))
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-root", type=Path, default=PRODUCTION_DATA_ROOT)
    parser.add_argument(
        "--log-path",
        type=Path,
        default=PRODUCTION_DATA_ROOT / "logs" / PRODUCTION_LOG_NAME,
    )
    args = parser.parse_args(argv)
    root = _absolute(args.project_root, "project root")
    log_path = _absolute(args.log_path, "log path")
    if not (root / "compose.yaml").is_file():
        raise SystemExit("project root must contain compose.yaml")
    if args.action == "run-once":
        _validate_production_paths(args.data_root, log_path)
        _validate_project_data_root(root, args.data_root)
        return _run_once(root, log_path)
    current = _read_crontab()
    installed = BEGIN_MARKER in current and END_MARKER in current
    if args.action == "status":
        print(json.dumps({"installed": installed, "schedule": SCHEDULE, "timezone": TIMEZONE}))
        return 0 if installed else 1
    replacement = cron_block(root, log_path) if args.action == "install" else None
    if args.action == "install":
        _validate_production_paths(args.data_root, log_path)
        _validate_project_data_root(root, args.data_root)
        _compose_config(root)
        _run_once(root, log_path, dry_run=True)
    _write_crontab(replace_managed_block(current, replacement))
    return 0


def _run_once(project_root: Path, log_path: Path, *, dry_run: bool = False) -> int:
    command = [*_compose_command(project_root)]
    if dry_run:
        # This is a Docker Compose global option.  Passing it after the service
        # name turns it into the container command and can leave a failed
        # one-off container behind instead of validating the cron contract.
        command.append("--dry-run")
    command.extend(
        (
        "--profile",
        "operations",
        "run",
        "--rm",
        "--no-deps",
        "shared-market-refresh",
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
    """Reject a cron mutation or refresh outside the one approved bind root."""

    root = _absolute(data_root, "data root")
    expected_log = root / "logs" / PRODUCTION_LOG_NAME
    if log_path != expected_log:
        raise ValueError(f"log path must be {expected_log}")
    checks = validate_data_root(
        root, minimum_free_bytes=20 * 1024**3, expected_root=PRODUCTION_DATA_ROOT
    )
    if not all(check.passed for check in checks):
        raise ValueError("production data-root preflight failed")


def _validate_project_data_root(project_root: Path, data_root: Path) -> None:
    """Require Compose's env file to select the same approved data root."""

    environment_file = project_root / ".env.local"
    try:
        lines = environment_file.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise ValueError("production environment file is unavailable") from error
    expected = str(_absolute(data_root, "data root"))
    configured = next(
        (
            line.partition("=")[2].strip().strip("\"'")
            for line in lines
            if line.strip().startswith("PORTFELL_DATA_ROOT=")
        ),
        None,
    )
    if configured != expected:
        raise ValueError("PORTFELL_DATA_ROOT must match the approved production data root")


if __name__ == "__main__":
    raise SystemExit(main())
