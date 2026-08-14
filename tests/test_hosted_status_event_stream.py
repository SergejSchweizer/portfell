from __future__ import annotations

import pytest

from portfell.hosted_status_event_repository import HostedStatusEvent
from portfell.hosted_status_event_stream import (
    StatusEventConnectionLimiter,
    StatusEventStreamError,
    event_frame,
    heartbeat_frame,
    reset_frame,
    resume_cursor,
)


def test_status_event_frames_are_compact_resumable_sse_messages() -> None:
    frame = event_frame(
        HostedStatusEvent(7, "workflow.changed", "project:p1", "revision", "complete")
    )

    assert frame.startswith("id: 7\nevent: status\ndata: {")
    assert '"aggregate_ref":"project:p1"' in frame
    assert frame.endswith("\n\n")
    assert heartbeat_frame() == ": heartbeat\n\n"
    assert reset_frame(cursor=7, reason="status_event_replay_reset") == (
        'id: 7\nevent: reset\ndata: {"reason":"status_event_replay_reset"}\n\n'
    )


@pytest.mark.parametrize(("header", "expected"), [(None, 0), ("", 0), ("42", 42)])
def test_resume_cursor_accepts_only_non_negative_event_ids(
    header: str | None, expected: int
) -> None:
    assert resume_cursor(header) == expected


@pytest.mark.parametrize("header", ["-1", "two", "1.2"])
def test_resume_cursor_rejects_invalid_event_ids(header: str) -> None:
    with pytest.raises(StatusEventStreamError, match="status_event_cursor_invalid"):
        resume_cursor(header)


def test_stream_limiter_releases_a_disconnected_user_slot() -> None:
    limiter = StatusEventConnectionLimiter()

    assert limiter.acquire("u1")
    assert limiter.acquire("u1")
    assert not limiter.acquire("u1")
    limiter.release("u1")
    assert limiter.acquire("u1")
