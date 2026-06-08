"""SSE streaming endpoints."""

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from siha.portal.auth import verify_auth
from siha.portal.events import event_bus

router = APIRouter(tags=["stream"])


@router.get("/stream/logs")
async def stream_logs(token: str = Depends(verify_auth)):
    """SSE stream of live logs."""
    async def event_generator():
        while True:
            event = await event_bus.get_event()
            yield event

    return EventSourceResponse(event_generator())
