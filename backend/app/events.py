# backend/app/events.py
"""
Event streaming endpoints for the FastAPI application.
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from typing import Set
import json
import asyncio
import queue
from threading import Lock

from services.processing_service import processing_lock

router = APIRouter()

# Global variables for SSE
processing_listeners: Set[queue.Queue] = set()


def notify_processing_update(data):
    """Notify all listeners of a processing update"""
    with processing_lock:
        # Create a copy of the set to avoid modification during iteration
        listeners_copy = processing_listeners.copy()
    
    for listener_queue in listeners_copy:
        try:
            listener_queue.put(json.dumps(data))
        except Exception as e:
            print(f"ERROR: Failed to notify listener: {e}")
            # Remove dead queues
            with processing_lock:
                processing_listeners.discard(listener_queue)


@router.get("/events/processing-updates")
async def processing_updates():
    """Server-Sent Events endpoint for real-time processing updates"""
    async def event_stream():
        # Create a queue for this connection
        listener_queue = queue.Queue()

        # Add this connection to listeners
        with processing_lock:
            processing_listeners.add(listener_queue)

        try:
            # Send initial connection message
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to processing updates'})}\n\n"

            # Keep connection alive and send updates
            while True:
                try:
                    # Wait for update (with timeout to keep connection alive)
                    # Use a short timeout to allow periodic checking
                    data = listener_queue.get(timeout=1)
                    yield f"data: {data}\n\n"
                except queue.Empty:
                    # Send keep-alive
                    yield ": keep-alive\n\n"
                    
                    # Check if client disconnected
                    # In a real implementation, you might want to check the client connection
                    await asyncio.sleep(0.1)
                    
        except asyncio.CancelledError:
            # Client disconnected
            pass
        except Exception as e:
            print(f"ERROR in event_stream: {e}")
        finally:
            # Remove this connection from listeners
            with processing_lock:
                processing_listeners.discard(listener_queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")