"""Small, bounded SSE framing primitives for durable hosted status events."""

from __future__ import annotations

import json
from threading import Lock

from portfell.hosted_status_event_repository import HostedStatusEvent


class StatusEventStreamError(ValueError):
    """Raised when an SSE resume cursor is not a non-negative event ID."""


class StatusEventConnectionLimiter:
    """Bound concurrent event streams per authenticated application session."""

    def __init__(self, *, maximum_per_user: int = 2) -> None:
        self._maximum_per_user = maximum_per_user
        self._counts: dict[str, int] = {}
        self._lock = Lock()

    def acquire(self, user_id: str) -> bool:
        with self._lock:
            count = self._counts.get(user_id, 0)
            if count >= self._maximum_per_user:
                return False
            self._counts[user_id] = count + 1
            return True

    def release(self, user_id: str) -> None:
        with self._lock:
            count = self._counts.get(user_id, 0)
            if count <= 1:
                self._counts.pop(user_id, None)
            else:
                self._counts[user_id] = count - 1


def resume_cursor(last_event_id: str | None) -> int:
    """Parse the standard SSE resume header without accepting ambiguous cursors."""

    if last_event_id is None or last_event_id == "":
        return 0
    try:
        cursor = int(last_event_id)
    except ValueError as error:
        raise StatusEventStreamError("status_event_cursor_invalid") from error
    if cursor < 0:
        raise StatusEventStreamError("status_event_cursor_invalid")
    return cursor


def event_frame(event: HostedStatusEvent) -> str:
    """Encode one compact durable event as a standards-compatible SSE message."""

    data = json.dumps(
        {
            "event_type": event.event_type,
            "aggregate_ref": event.aggregate_ref,
            "projection_revision": event.projection_revision,
            "terminal_status": event.terminal_status,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"id: {event.event_id}\nevent: status\ndata: {data}\n\n"


def heartbeat_frame() -> str:
    """Return a comment frame that keeps reverse proxies and clients alive."""

    return ": heartbeat\n\n"


def reset_frame(*, cursor: int, reason: str) -> str:
    """Tell a reconnecting client to invalidate bounded queries and resume at ``cursor``."""

    data = json.dumps({"reason": reason}, sort_keys=True, separators=(",", ":"))
    return f"id: {cursor}\nevent: reset\ndata: {data}\n\n"
