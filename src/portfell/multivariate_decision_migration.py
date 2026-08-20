"""Fail-closed runtime entry point for the Multivariate evidence schema."""

from __future__ import annotations

import json
import os
import sys

from portfell.hosted_database_connection import connect as connect_database
from portfell.multivariate_decision_schema import apply_multivariate_decision_schema


def main() -> int:
    """Apply the idempotent Multivariate decision/history schema."""

    database_url = os.environ.get("PORTFELL_DATABASE_URL")
    if not database_url:
        print("database_url_required", file=sys.stderr)
        return 1
    try:
        connection = connect_database(database_url, autocommit=True)
        try:
            apply_multivariate_decision_schema(connection)
        finally:
            connection.close()
    except Exception:
        print("multivariate_decision_migration_failed", file=sys.stderr)
        return 1
    print(json.dumps({"multivariate_decision_schema": "ready"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
