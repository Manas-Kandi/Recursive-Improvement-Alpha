"""In-process event bus for SSE streaming"""

import asyncio
from typing import Dict, Any
from collections import deque


class EventBus:
    """Simple in-process event bus for SSE streaming"""
    
    def __init__(self):
        self.queue = deque(maxlen=1000)
        self.subscribers = []
    
    def publish(self, event_type: str, data: Dict[str, Any]):
        """Publish an event"""
        event = {
            "event": event_type,
            "data": data
        }
        self.queue.append(event)
    
    async def get_event(self):
        """Get next event (blocking for SSE)"""
        while len(self.queue) == 0:
            await asyncio.sleep(0.1)
        
        if self.queue:
            event = self.queue.popleft()
            return {
                "event": event["event"],
                "data": event["data"]
            }
        
        return None


# Global event bus instance
event_bus = EventBus()
