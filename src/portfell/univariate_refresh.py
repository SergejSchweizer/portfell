"""Cron entry point for recomputing persisted project univariate statistics."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from portfell.app_services.workspace import WorkspaceApplicationService
from portfell.app_state.migration import migrate_to_head
from portfell.app_state.repository import PostgresAppStateRepository
from portfell.hosted_database_connection import connect
from portfell.market_source.config import load_app_database_config, validate_app_database_url
from portfell.market_source.local_gateway import LocalMarketDataGateway


def refresh(*, config_path: Path, market_root: Path) -> dict[str, object]:
    config = load_app_database_config(config_path)
    app_url = validate_app_database_url(config)
    connection = connect(app_url, autocommit=False, password_secret=config.password_secret)
    try:
        migrate_to_head(connection)
        state = PostgresAppStateRepository(connection)
        service = WorkspaceApplicationService(state, LocalMarketDataGateway(market_root))
        universes = state.list_metadata_universes(limit=1)
        succeeded: list[str] = []
        failed: dict[str, str] = {}
        for universe in universes:
            try:
                result = service.run_univariate(universe.universe_id)
                if result.get("status") == "succeeded":
                    run_id = result.get("run_id")
                    if isinstance(run_id, str):
                        # Keep only instruments with at least one quote in the
                        # persisted downstream selection; no-quote rows remain
                        # available in the run artifact as explicit evidence.
                        # The persisted Univariate run already contains only
                        # listings with usable return history. Activate the
                        # complete computed universe; UI filters are applied
                        # explicitly by the user afterwards.
                        service.create_univariate_selection(run_id)
                    succeeded.append(universe.universe_id)
                else:
                    failed[universe.universe_id] = str(result.get("status", "failed"))
            except Exception as error:  # noqa: BLE001 - cron must continue across projects
                failed[universe.universe_id] = str(error) or type(error).__name__
        return {"projects": len(universes), "succeeded": len(succeeded), "failed": failed}
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compute and persist Portfell univariate statistics"
    )
    parser.add_argument(
        "--config", default=os.environ.get("PORTFELL_CONFIG_PATH", "config.yaml"), type=Path
    )
    parser.add_argument(
        "--market-root",
        default=os.environ.get("PORTFELL_MARKET_DATA_ROOT", "/var/lib/portfell/market-data"),
        type=Path,
    )
    args = parser.parse_args()
    print(
        json.dumps(refresh(config_path=args.config, market_root=args.market_root), sort_keys=True)
    )


__all__ = ["main", "refresh"]

if __name__ == "__main__":
    main()
