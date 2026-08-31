from __future__ import annotations

import os
import re
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from portfell.hosted_database_connection import connect
from portfell.market_source.config import load_market_source_config, validate_market_database_url
from portfell.market_source.gateway import MarketDataGateway

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = Path(os.environ.get("PORTFELL_CONFIG_PATH", ROOT / "config.yaml"))
LIVE = os.environ.get("PORTFELL_LIVE_XETRA_LOADER_V2") == "1"
requires_live = pytest.mark.skipif(
    not LIVE,
    reason="live xetra-loader V2 acceptance requires PORTFELL_LIVE_XETRA_LOADER_V2=1",
)


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        pytest.fail(f"missing required live-QA environment variable: {name}")
    return value


def _market_connection():
    dsn = _required("PORTFELL_MARKET_DATABASE_URL")
    return connect(
        dsn,
        autocommit=False,
        password_secret="PORTFELL_MARKET_DATABASE_PASSWORD_FILE",
    )


def _market_config():
    """Use the runtime-mounted config when this suite runs in a container."""

    return load_market_source_config(CONFIG_PATH)


@requires_live
def test_live_gate_is_pinned_to_expected_loader_sha_and_endpoint() -> None:
    expected_sha = _required("PORTFELL_EXPECTED_XETRA_LOADER_SHA")
    observed_sha = _required("PORTFELL_LIVE_XETRA_LOADER_SHA")
    assert re.fullmatch(r"[0-9a-f]{40}", expected_sha)
    assert observed_sha == expected_sha

    dsn = _required("PORTFELL_MARKET_DATABASE_URL")
    parsed = urlsplit(dsn)
    assert parsed.hostname == "10.10.1.3"
    assert parsed.port == 54321
    assert parsed.path == "/xetra_loader"

    config = _market_config()
    validate_market_database_url(config, url=dsn)
    assert config.database == "xetra_loader"
    assert config.schema == "xetra_loader"
    assert config.tables == ("listings", "eod_quotes", "dividends", "splits")


@requires_live
def test_live_reader_is_non_superuser_group_member_and_selects_all_business_tables() -> None:
    config = _market_config()
    with closing(_market_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT rolcanlogin, rolsuper, pg_has_role(current_user, %s, 'member') "
            "FROM pg_roles WHERE rolname = current_user",
            (config.member_of,),
        )
        assert cursor.fetchone() == (True, False, True)

        for table in config.tables:
            cursor.execute(f'SELECT 1 FROM "{config.schema}"."{table}" LIMIT 1')
            assert cursor.fetchone() in {(1,), None}
        connection.rollback()


@requires_live
def test_live_gateway_materializes_representative_rows() -> None:
    config = _market_config()
    gateway = MarketDataGateway(
        _market_connection,
        role=config.role,
        member_of=config.member_of,
    )
    active = gateway.read_active_listings()
    assert active
    keys = tuple(listing.key for listing in active[: min(5, len(active))])
    end = date.today()
    snapshot = gateway.read_snapshot(keys, start=end - timedelta(days=45), end=end)

    assert snapshot.listings
    assert {listing.key for listing in snapshot.listings}.issubset(set(keys))
    assert all(quote.key in keys for quote in snapshot.quotes)
    assert all(dividend.key in keys for dividend in snapshot.dividends)
    assert all(split.key in keys for split in snapshot.splits)


def _expect_insufficient_privilege(sql: str) -> None:
    import psycopg

    with closing(_market_connection()) as connection:
        cursor = connection.cursor()
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            cursor.execute(sql)
        connection.rollback()


@requires_live
def test_live_market_dml_and_ddl_are_denied() -> None:
    _expect_insufficient_privilege('UPDATE "xetra_loader"."listings" SET isin = isin WHERE false')
    _expect_insufficient_privilege(
        'CREATE TABLE "xetra_loader"."__portfell_pr340_forbidden" (id integer)'
    )


@requires_live
def test_live_sync_schema_access_is_denied_and_counts_as_pass() -> None:
    with closing(_market_connection()) as connection:
        cursor = connection.cursor()
        cursor.execute("SELECT has_schema_privilege(current_user, 'xetra_loader_sync', 'USAGE')")
        assert cursor.fetchone() == (False,)
        connection.rollback()


def test_live_qa_source_contains_no_secret_or_full_dsn_evidence_output() -> None:
    source = Path(__file__).read_text(encoding="utf-8")
    assert ("print" + "(") not in source
    assert ("logger" + ".") not in source
    assert ("password" + "=") not in source.lower()
    assert ("postgres" + "ql://") not in source.lower()
