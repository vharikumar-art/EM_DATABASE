"""
In-memory SSE connection manager.
Each employee can have multiple browser tabs connected simultaneously.
"""
import asyncio
from collections import defaultdict

# employee_id -> list of queues (one per connected browser tab)
_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)


def subscribe(employee_id: str) -> asyncio.Queue:
    """Register a new SSE connection for an employee and return its queue."""
    q: asyncio.Queue = asyncio.Queue()
    _subscribers[employee_id].append(q)
    return q


def unsubscribe(employee_id: str, queue: asyncio.Queue) -> None:
    """Remove a disconnected SSE queue."""
    try:
        _subscribers[employee_id].remove(queue)
    except ValueError:
        pass


async def broadcast(employee_id: str, notification: dict) -> None:
    """Push a notification to all active SSE connections for an employee."""
    for q in list(_subscribers.get(employee_id, [])):
        await q.put(notification)
