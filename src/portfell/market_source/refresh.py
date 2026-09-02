"""Scheduled PostgreSQL-to-local market snapshot publication."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import date
from pathlib import Path

from portfell.hosted_database_connection import connect
from portfell.market_source.config import load_market_source_config, validate_market_database_url
from portfell.market_source.contracts import Dividend, EodQuote, Listing, Split
from portfell.market_source.gateway import MarketDataGateway


def _row(item: Listing | EodQuote | Dividend | Split) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in vars(item).items():
        if key == "key":
            result.update(vars(value))  # type: ignore[arg-type]
        elif isinstance(value, (date,)):
            result[key] = value.isoformat()
        else:
            result[key] = str(value) if value.__class__.__name__ == "Decimal" else value
    return result


def refresh(*, config_path: Path, root: Path) -> int:
    config = load_market_source_config(config_path)
    url = validate_market_database_url(config)
    gateway = MarketDataGateway(
        lambda: connect(url, autocommit=False, password_secret=config.password_secret),
        role=config.role,
        member_of=config.member_of,
    )
    listings = gateway.read_active_listings()
    keys = tuple(item.key for item in listings)
    snapshot = gateway.read_snapshot(keys, start=date.min, end=date.max)
    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="market-refresh-", dir=root.parent) as temp:
        staging = Path(temp)
        for name, rows in (
            ("listings", snapshot.listings),
            ("quotes", snapshot.quotes),
            ("dividends", snapshot.dividends),
            ("splits", snapshot.splits),
        ):
            (staging / f"{name}.jsonl").write_text(
                "".join(json.dumps(_row(item), sort_keys=True) + "\n" for item in rows),
                encoding="utf-8",
            )
        (staging / "manifest.json").write_text(
            json.dumps({"schema_version": 1, "listing_count": len(listings)}, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
        # The API runs as uid 10001 and must be able to traverse/read the
        # atomically published snapshot mounted read-only into its container.
        for path in staging.iterdir():
            path.chmod(0o644)
        staging.chmod(0o755)
        backup = root.with_name(root.name + ".previous")
        if backup.exists():
            import shutil

            shutil.rmtree(backup)
        if root.exists():
            root.rename(backup)
        staging.rename(root)
    return len(listings)


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish the PostgreSQL market snapshot locally")
    parser.add_argument(
        "--config", default=os.environ.get("PORTFELL_CONFIG_PATH", "config.yaml"), type=Path
    )
    parser.add_argument(
        "--root",
        default=os.environ.get("PORTFELL_MARKET_DATA_ROOT", "/var/lib/portfell/market-data"),
        type=Path,
    )
    args = parser.parse_args()
    print(json.dumps({"listings": refresh(config_path=args.config, root=args.root)}))


__all__ = ["main", "refresh"]

if __name__ == "__main__":
    main()
