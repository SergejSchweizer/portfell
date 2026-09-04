"""Hosted container runtime entry points."""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Sequence

from portfell.logging import get_logger, log_event, setup_logging

LOGGER = get_logger(__name__)


def health() -> int:
    """Return a process health status for container health checks."""

    print(json.dumps({"status": "ok"}, sort_keys=True))
    return 0


def run_api_placeholder() -> int:
    """Start the hosted FastAPI application."""

    import uvicorn

    log_event(LOGGER, 20, module="hosted-runtime", event="api_starting")
    uvicorn.run(
        "portfell.hosted_api:create_runtime_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        # Keep HTTP/Dash responsive while a CPU-heavy analysis job runs in
        # another worker. Durable PostgreSQL job claims prevent duplicate work.
        workers=max(2, int(os.environ.get("PORTFELL_API_WORKERS", "2"))),
        log_level="info",
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the hosted runtime parser."""

    parser = argparse.ArgumentParser(description="Portfell hosted container runtime.")
    parser.add_argument("command", choices=("api", "health"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a hosted container entry point."""

    args = build_parser().parse_args(argv)
    setup_logging(debug=os.environ.get("PORTFELL_LOG_LEVEL", "").upper() == "DEBUG")
    if args.command == "health":
        return health()
    return run_api_placeholder()


if __name__ == "__main__":
    raise SystemExit(main())
