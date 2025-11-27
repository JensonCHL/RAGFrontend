"""
Chat Backend for RAG Application
Handles streaming chat responses from n8n webhook, similar to OpenWebUI pipe
"""

import os
import json
import logging
import aiohttp
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, ".env")
load_dotenv(env_path)

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create router
router = APIRouter(prefix="/api/chat", tags=["chat"])

# Configuration from environment
N8N_WEBHOOK_URL = os.getenv(
    "N8N_WEBHOOK_URL",
    "https://n8n.cloudeka.ai/webhook-test/625ca468-9002-4a8d-83a3-ddbcf9bc9c16",
)
INPUT_FIELD = os.getenv("N8N_INPUT_FIELD", "chatInput")
RESPONSE_FIELD = os.getenv("N8N_RESPONSE_FIELD", "output")

# ============================================================================
# Pydantic Models
# ============================================================================


class ChatMessage(BaseModel):
    role: str  # 'user', 'assistant', 'system'
    content: str


class ChatRequest(BaseModel):
    message: str
    conversation_id: str
    user_id: str
    timestamp: str
    messages: Optional[List[ChatMessage]] = []
    context: Optional[Dict[str, Any]] = {}


# ============================================================================
# Streaming Parsing Functions (from OpenWebUI pipe)
# ============================================================================


def parse_n8n_streaming_chunk(chunk_text: str) -> Optional[str]:
    """
    Parse a streaming JSON/text chunk and extract content.
    This is the EXACT same logic as your OpenWebUI pipe.
    """
    if not chunk_text.strip():
        return None

    try:
        data = json.loads(chunk_text.strip())
        if isinstance(data, dict):
            # Skip control messages
            if data.get("type") in ["begin", "end", "error", "metadata"]:
                return None

            # Extract content from various possible fields
            content = (
                data.get("text")
                or data.get("content")
                or data.get("output")
                or data.get("message")
                or data.get("delta")
                or data.get("data")
            )

            # Handle OpenAI-style format
            if not content and "choices" in data:
                choices = data.get("choices", [])
                if choices and isinstance(choices[0], dict):
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")

            return str(content) if content else None
    except json.JSONDecodeError:
        # If not JSON, return as plain text
        if not chunk_text.startswith("{"):
            return chunk_text.strip()

    return None


def extract_content_from_mixed_stream(raw_text: str) -> str:
    """
    Handle concatenated JSON objects in leftover buffer.
    This is the EXACT same logic as your OpenWebUI pipe.
    """
    parts = raw_text.split("}{")
    out = []
    for i, part in enumerate(parts):
        if i > 0:
            part = "{" + part
        if i < len(parts) - 1:
            part = part + "}"
        piece = parse_n8n_streaming_chunk(part)
        if piece:
            out.append(piece)
    return "".join(out)


def extract_non_streaming_response(data: Any) -> str:
    """Parse non-streaming JSON/text reply"""
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            return (
                first.get(RESPONSE_FIELD)
                or first.get("text")
                or first.get("content")
                or first.get("output")
                or str(first)
            )
        return str(first)
    if isinstance(data, dict):
        return (
            data.get(RESPONSE_FIELD)
            or data.get("text")
            or data.get("content")
            or data.get("output")
            or str(data)
        )
    return str(data)


# ============================================================================
# Main Streaming Function
# ============================================================================


async def stream_n8n_response(chat_request: ChatRequest):
    """
    Stream response from n8n webhook.
    This matches the OpenWebUI pipe logic exactly.
    """

    # Build payload for n8n (same format as OpenWebUI)
    system_prompt = ""
    if chat_request.messages and chat_request.messages[0].role == "system":
        system_prompt = chat_request.messages[0].content

    # Build message history
    history = [
        {"role": m.role, "content": m.content}
        for m in chat_request.messages
        if m.role in ["user", "assistant"]
    ]

    payload = {
        "systemPrompt": system_prompt,
        "messages": history,
        "currentMessage": chat_request.message,
        "chat_id": chat_request.conversation_id,
        "sessionId": chat_request.user_id,  # n8n expects sessionId
        INPUT_FIELD: chat_request.message,
    }

    # Add context if provided
    if chat_request.context:
        payload.update(chat_request.context)

    logger.info(
        f"Sending chat request to n8n: conversation_id={chat_request.conversation_id}"
    )

    try:
        async with aiohttp.ClientSession(
            trust_env=True, timeout=aiohttp.ClientTimeout(total=None)
        ) as session:
            async with session.post(
                N8N_WEBHOOK_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
            ) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"n8n error {resp.status}: {error_text}")
                    yield f"data: {json.dumps({'error': f'n8n error: {resp.status}'})}\n\n"
                    return

                content_type = resp.headers.get("Content-Type", "").lower()
                is_streaming = (
                    "stream" in content_type
                    or "text/plain" in content_type
                    or resp.headers.get("Transfer-Encoding") == "chunked"
                )

                if is_streaming:
                    logger.info("Processing streaming response from n8n")
                    # Stream response with proper JSON chunk parsing (EXACT OpenWebUI logic)
                    buffer = ""
                    async for chunk in resp.content.iter_any():
                        if not chunk:
                            continue

                        buffer += chunk.decode(errors="ignore")

                        # Parse complete JSON objects using brace counting
                        while True:
                            start = buffer.find("{")
                            if start == -1:
                                break

                            brace_count, end = 0, -1
                            for i, ch in enumerate(buffer[start:], start=start):
                                if ch == "{":
                                    brace_count += 1
                                elif ch == "}":
                                    brace_count -= 1
                                    if brace_count == 0:
                                        end = i
                                        break

                            if end == -1:
                                break

                            json_chunk = buffer[start : end + 1]
                            buffer = buffer[end + 1 :]

                            piece = parse_n8n_streaming_chunk(json_chunk)
                            if piece:
                                # Yield in SSE format for frontend
                                yield f"data: {json.dumps({'token': piece})}\n\n"

                    # Handle leftover buffer
                    if buffer.strip():
                        leftover = extract_content_from_mixed_stream(buffer)
                        if leftover:
                            yield f"data: {json.dumps({'token': leftover})}\n\n"

                    # Send completion signal
                    yield "data: [DONE]\n\n"
                    logger.info("Streaming completed successfully")
                else:
                    logger.info("Processing non-streaming response from n8n")
                    # Non-streaming response
                    try:
                        data = await resp.json()
                        content = extract_non_streaming_response(data)
                        yield f"data: {json.dumps({'response': content, 'conversation_id': chat_request.conversation_id})}\n\n"
                        yield "data: [DONE]\n\n"
                    except Exception:
                        raw = await resp.text()
                        content = extract_content_from_mixed_stream(raw) or raw
                        yield f"data: {json.dumps({'response': content, 'conversation_id': chat_request.conversation_id})}\n\n"
                        yield "data: [DONE]\n\n"

    except Exception as e:
        logger.error(f"Error streaming from n8n: {e}", exc_info=True)
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/send")
async def send_chat_message(chat_request: ChatRequest):
    """
    Send message to n8n and stream response.
    This endpoint mimics the OpenWebUI pipe behavior.
    """
    logger.info(
        f"Received chat request: user={chat_request.user_id}, conversation={chat_request.conversation_id}"
    )

    return StreamingResponse(
        stream_n8n_response(chat_request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "n8n_url": N8N_WEBHOOK_URL,
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================================
# Conversation Storage Endpoints (PostgreSQL - TODO)
# ============================================================================


@router.get("/conversations")
async def get_conversations(user_id: str):
    """
    Get all conversations for a user.
    TODO: Implement PostgreSQL query
    """
    # For now, return empty list
    # Later: SELECT * FROM chat_conversations WHERE user_id = ? ORDER BY updated_at DESC
    return {"conversations": []}


@router.post("/conversations")
async def create_conversation(user_id: str, title: str):
    """
    Create new conversation.
    TODO: Implement PostgreSQL insert
    """
    # For now, generate UUID
    import uuid

    conversation_id = str(uuid.uuid4())

    # Later: INSERT INTO chat_conversations (id, user_id, title, created_at, updated_at)
    return {"conversation_id": conversation_id, "title": title}


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """
    Get conversation with messages.
    TODO: Implement PostgreSQL query
    """
    # Later:
    # SELECT * FROM chat_conversations WHERE id = ?
    # SELECT * FROM chat_messages WHERE conversation_id = ? ORDER BY created_at ASC
    return {"conversation": {}, "messages": []}


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """
    Delete conversation.
    TODO: Implement PostgreSQL delete
    """
    # Later: DELETE FROM chat_conversations WHERE id = ? (CASCADE will delete messages)
    return {"success": True}


@router.patch("/conversations/{conversation_id}")
async def update_conversation(conversation_id: str, title: str):
    """
    Update conversation title.
    TODO: Implement PostgreSQL update
    """
    # Later: UPDATE chat_conversations SET title = ?, updated_at = NOW() WHERE id = ?
    return {"success": True, "title": title}


# ============================================================================
# Message Storage Endpoints (PostgreSQL - TODO)
# ============================================================================


@router.post("/conversations/{conversation_id}/messages")
async def save_message(
    conversation_id: str,
    role: str,
    content: str,
    sources: Optional[List[Dict]] = None,
    metadata: Optional[Dict] = None,
):
    """
    Save a message to the conversation.
    TODO: Implement PostgreSQL insert
    """
    # Later: INSERT INTO chat_messages (conversation_id, role, content, sources, metadata, created_at)
    import uuid

    message_id = str(uuid.uuid4())
    return {"message_id": message_id}


logger.info("Chat backend initialized successfully")
