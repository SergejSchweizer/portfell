"""Authenticated durable status-event SSE transport."""

# ruff: noqa: B008

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse

from portfell.hosted_api_state import ApiUser
from portfell.hosted_postgres_request_scope import RequestScopedPostgresConnection
from portfell.hosted_status_event_repository import PostgresStatusEventRepository
from portfell.hosted_status_event_stream import (
    StatusEventConnectionLimiter,
    StatusEventStreamError,
    event_frame,
    heartbeat_frame,
    resume_cursor,
)


def status_event_router(
    *,
    request_scope: RequestScopedPostgresConnection,
    current_user: Callable[[], ApiUser],
    limiter: StatusEventConnectionLimiter,
) -> APIRouter:
    """Build the hosted-only stream route over the RLS-bound durable catalog."""

    router = APIRouter()

    @router.get("/status-events")
    async def status_events(  # pyright: ignore[reportUnusedFunction]
        request: Request,
        last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
        user: ApiUser = Depends(current_user),
    ) -> StreamingResponse:
        try:
            cursor = resume_cursor(last_event_id)
        except StatusEventStreamError as error:
            raise HTTPException(422, detail={"code": str(error)}) from error
        if not limiter.acquire(user.user_id):
            raise HTTPException(429, detail={"code": "status_event_stream_limit"})

        async def frames() -> AsyncIterator[str]:
            nonlocal cursor
            try:
                while not await request.is_disconnected():
                    with request_scope.background_request(user.user_id):
                        events = PostgresStatusEventRepository(request_scope).replay(
                            user_id=user.user_id, after_event_id=cursor
                        )
                    for event in events:
                        cursor = event.event_id
                        yield event_frame(event)
                    yield heartbeat_frame()
                    await asyncio.sleep(15)
            finally:
                limiter.release(user.user_id)

        return StreamingResponse(
            frames(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    return router
