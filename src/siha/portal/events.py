"""In-process event bus with per-subscriber queues for SSE streaming."""

import asyncio
from typing import Dict, Any, Set
from uuid import uuid4


class EventBus:
    """In-process event bus where every subscriber gets its own queue.

    This allows multiple SSE clients to each receive a full copy of the
    event stream without missing events or interfering with each other.
    """

    def __init__(self, max_queue_size: int = 1000):
        self._max_queue_size = max_queue_size
        self._queues: Dict[str, asyncio.Queue] = {}

    def subscribe(self) -> str:
        """Register a new subscriber and return its subscriber id."""
        sid = str(uuid4())
        self._queues[sid] = asyncio.Queue(maxsize=self._max_queue_size)
        return sid

    def unsubscribe(self, sid: str) -> None:
        """Remove a subscriber and discard its queue."""
        self._queues.pop(sid, None)

    def publish(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish an event to every subscriber queue."""
        event = {"event": event_type, "data": data}
        for queue in list(self._queues.values()):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop oldest event to make room
                try:
                    queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    pass

    async def get_event(self, sid: str):
        """Get the next event for a specific subscriber (blocking)."""
        queue = self._queues.get(sid)
        if queue is None:
            return None
        return await queue.get()

    def get_subscriber_ids(self) -> Set[str]:
        """Return all active subscriber ids."""
        return set(self._queues.keys())


# Global event bus instance
event_bus = EventBus()
