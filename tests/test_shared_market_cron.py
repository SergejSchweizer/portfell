from __future__ import annotations

from pathlib import Path

import pytest

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
