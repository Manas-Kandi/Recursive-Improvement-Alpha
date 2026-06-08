"""SSE streaming endpoints."""

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from siha.portal.auth import verify_auth
from siha.portal.events import event_bus

router = APIRouter(tags=["stream"])


@router.get("/stream/logs")
async def stream_logs(token: str = Depends(verify_auth)):
    """SSE stream of live logs. Each client gets its own subscriber queue."""
    sid = event_bus.subscribe()

    async def event_generator():
        try:
            while True:
                event = await event_bus.get_event(sid)
                if event is None:
                    break
                yield event
        finally:
            event_bus.unsubscribe(sid)

    return EventSourceResponse(event_generator())
