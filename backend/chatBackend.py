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
import psycopg2
from psycopg2.extras import RealDictCursor

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


class ConversationCreateRequest(BaseModel):
    user_id: str
    title: str


class ConversationUpdateRequest(BaseModel):
    user_id: str
    title: str


class MessageCreateRequest(BaseModel):
    user_id: str
    role: str
    content: str
    sources: Optional[List[Dict]] = None
    metadata: Optional[Dict] = None


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
# Conversation Storage Endpoints (PostgreSQL)
# ============================================================================

# Import database utilities
import psycopg2
from psycopg2.extras import RealDictCursor


def get_db_connection():
    """Get PostgreSQL database connection"""
    import os

    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME", "rag_db"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
    )


@router.get("/conversations")
async def get_conversations(user_id: str):
    """
    Get all conversations for a user.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT id, user_id, title, created_at, updated_at
            FROM chat_conversations
            WHERE user_id = %s
            ORDER BY updated_at DESC
            """,
            (user_id,),
        )

        conversations = cursor.fetchall()
        cursor.close()
        conn.close()

        # Convert to list of dicts and format dates
        result = []
        for conv in conversations:
            result.append(
                {
                    "id": str(conv["id"]),
                    "user_id": conv["user_id"],
                    "title": conv["title"],
                    "created_at": conv["created_at"].isoformat()
                    if conv["created_at"]
                    else None,
                    "updated_at": conv["updated_at"].isoformat()
                    if conv["updated_at"]
                    else None,
                    "messages": [],  # Messages loaded separately
                }
            )

        return {"conversations": result}
    except Exception as e:
        logger.error(f"Error fetching conversations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations")
async def create_conversation(request: ConversationCreateRequest):
    """
    Create new conversation.
    """
    try:
        import uuid

        user_id = request.user_id
        title = request.title
        conversation_id = str(uuid.uuid4())

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO chat_conversations (id, user_id, title, created_at, updated_at)
            VALUES (%s, %s, %s, NOW(), NOW())
            RETURNING id, created_at, updated_at
            """,
            (conversation_id, user_id, title),
        )

        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        return {
            "id": conversation_id,
            "user_id": user_id,
            "title": title,
            "created_at": result[1].isoformat() if result[1] else None,
            "updated_at": result[2].isoformat() if result[2] else None,
            "messages": [],
        }
    except Exception as e:
        logger.error(f"Error creating conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, user_id: str):
    """
    Get conversation with messages.
    Includes user_id check for security.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Get conversation (with user_id check)
        cursor.execute(
            """
            SELECT id, user_id, title, created_at, updated_at
            FROM chat_conversations
            WHERE id = %s AND user_id = %s
            """,
            (conversation_id, user_id),
        )

        conversation = cursor.fetchone()
        if not conversation:
            cursor.close()
            conn.close()
            raise HTTPException(status_code=404, detail="Conversation not found")

        # Get messages
        cursor.execute(
            """
            SELECT id, conversation_id, role, content, sources, metadata, created_at
            FROM chat_messages
            WHERE conversation_id = %s
            ORDER BY created_at ASC
            """,
            (conversation_id,),
        )

        messages = cursor.fetchall()
        cursor.close()
        conn.close()

        # Format response
        return {
            "conversation": {
                "id": str(conversation["id"]),
                "user_id": conversation["user_id"],
                "title": conversation["title"],
                "created_at": conversation["created_at"].isoformat()
                if conversation["created_at"]
                else None,
                "updated_at": conversation["updated_at"].isoformat()
                if conversation["updated_at"]
                else None,
            },
            "messages": [
                {
                    "id": str(msg["id"]),
                    "conversation_id": str(msg["conversation_id"]),
                    "role": msg["role"],
                    "content": msg["content"],
                    "sources": msg["sources"],
                    "metadata": msg["metadata"],
                    "timestamp": msg["created_at"].isoformat()
                    if msg["created_at"]
                    else None,
                }
                for msg in messages
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str, user_id: str):
    """
    Delete conversation (with user_id check for security).
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Delete only if user owns the conversation
        cursor.execute(
            """
            DELETE FROM chat_conversations
            WHERE id = %s AND user_id = %s
            RETURNING id
            """,
            (conversation_id, user_id),
        )

        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        if not result:
            raise HTTPException(
                status_code=404, detail="Conversation not found or unauthorized"
            )

        return {"success": True, "id": conversation_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/conversations/{conversation_id}")
async def update_conversation(conversation_id: str, request: ConversationUpdateRequest):
    """
    Update conversation title (with user_id check for security).
    """
    try:
        user_id = request.user_id
        title = request.title

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            UPDATE chat_conversations
            SET title = %s, updated_at = NOW()
            WHERE id = %s AND user_id = %s
            RETURNING id
            """,
            (title, conversation_id, user_id),
        )

        result = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()

        if not result:
            raise HTTPException(
                status_code=404, detail="Conversation not found or unauthorized"
            )

        return {"success": True, "title": title}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating conversation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Message Storage Endpoints (PostgreSQL)
# ============================================================================


@router.post("/conversations/{conversation_id}/messages")
async def save_message(
    conversation_id: str,
    request: MessageCreateRequest,
):
    """
    Save a message to the conversation.
    Includes user_id check to ensure user owns the conversation.
    """
    try:
        import uuid
        import json

        user_id = request.user_id
        role = request.role
        content = request.content
        sources = request.sources
        metadata = request.metadata

        message_id = str(uuid.uuid4())

        conn = get_db_connection()
        cursor = conn.cursor()

        # First verify user owns this conversation
        cursor.execute(
            "SELECT id FROM chat_conversations WHERE id = %s AND user_id = %s",
            (conversation_id, user_id),
        )
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=404, detail="Conversation not found or unauthorized"
            )

        # Insert message
        cursor.execute(
            """
            INSERT INTO chat_messages (id, conversation_id, role, content, sources, metadata, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            RETURNING id, created_at
            """,
            (
                message_id,
                conversation_id,
                role,
                content,
                json.dumps(sources) if sources else None,
                json.dumps(metadata) if metadata else None,
            ),
        )

        result = cursor.fetchone()

        # Update conversation updated_at
        cursor.execute(
            "UPDATE chat_conversations SET updated_at = NOW() WHERE id = %s",
            (conversation_id,),
        )

        conn.commit()
        cursor.close()
        conn.close()

        return {
            "id": message_id,
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "timestamp": result[1].isoformat() if result[1] else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


logger.info("Chat backend initialized successfully")

# ============================================================================
# User Management Endpoints (RBAC)
# ============================================================================

from passlib.context import CryptContext

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserCreateRequest(BaseModel):
    username: str
    email: str
    password: str


class UserUpdateRequest(BaseModel):
    username: str


class AuthVerifyRequest(BaseModel):
    username: str
    password: str


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


@router.post("/admin/users")
async def create_user(request: UserCreateRequest):
    """
    Create a new user (Admin only).
    """
    try:
        import uuid

        user_id = str(uuid.uuid4())
        hashed_password = get_password_hash(request.password)

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                INSERT INTO users (id, username, email, password_hash, role, created_at, updated_at)
                VALUES (%s, %s, %s, %s, 'user', NOW(), NOW())
                RETURNING id, username, email, role, created_at
                """,
                (user_id, request.username, request.email, hashed_password),
            )
            new_user = cursor.fetchone()
            conn.commit()

            return {
                "id": str(new_user[0]),
                "username": new_user[1],
                "email": new_user[2],
                "role": new_user[3],
                "created_at": new_user[4].isoformat() if new_user[4] else None,
            }
        except psycopg2.IntegrityError:
            conn.rollback()
            raise HTTPException(
                status_code=400, detail="Username or email already exists"
            )
        finally:
            cursor.close()
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admin/users")
async def list_users():
    """
    List all users (Admin only).
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        cursor.execute(
            """
            SELECT id, username, email, role, created_at, updated_at
            FROM users
            ORDER BY created_at DESC
            """
        )
        users = cursor.fetchall()
        cursor.close()
        conn.close()

        result = []
        for user in users:
            result.append(
                {
                    "id": str(user["id"]),
                    "username": user["username"],
                    "email": user["email"],
                    "role": user["role"],
                    "created_at": user["created_at"].isoformat()
                    if user["created_at"]
                    else None,
                    "updated_at": user["updated_at"].isoformat()
                    if user["updated_at"]
                    else None,
                }
            )

        return {"users": result}
    except Exception as e:
        logger.error(f"Error listing users: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/auth/verify")
async def verify_user(request: AuthVerifyRequest):
    """
    Verify user credentials (for NextAuth).
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)

        # Allow login by username OR email
        cursor.execute(
            """
            SELECT id, username, email, password_hash, role
            FROM users
            WHERE username = %s OR email = %s
            """,
            (request.username, request.username),
        )
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if not verify_password(request.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        return {
            "id": str(user["id"]),
            "username": user["username"],
            "email": user["email"],
            "role": user["role"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/users/me")
async def update_own_username(user_id: str, request: UserUpdateRequest):
    """
    Update own username.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE users
                SET username = %s, updated_at = NOW()
                WHERE id = %s
                RETURNING username
                """,
                (request.username, user_id),
            )
            updated_user = cursor.fetchone()
            conn.commit()

            if not updated_user:
                raise HTTPException(status_code=404, detail="User not found")

            return {"success": True, "username": updated_user[0]}
        except psycopg2.IntegrityError:
            conn.rollback()
            raise HTTPException(status_code=400, detail="Username already taken")
        finally:
            cursor.close()
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating username: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/admin/users/{user_id}")
async def delete_user(user_id: str):
    """
    Delete a user (Admin only).
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Check if user exists
            cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            if not cursor.fetchone():
                raise HTTPException(status_code=404, detail="User not found")

            # Delete user and all associated chat data
            # Since there's no foreign key constraint between users and chat_conversations,
            # we need to manually delete in the correct order to avoid orphaned data

            # Step 1: Delete all messages in conversations belonging to this user
            # (This will cascade automatically due to ON DELETE CASCADE on conversation_id)
            cursor.execute(
                "DELETE FROM chat_messages WHERE conversation_id IN (SELECT id FROM chat_conversations WHERE user_id = %s)",
                (user_id,),
            )

            # Step 2: Delete all conversations belonging to this user
            cursor.execute(
                "DELETE FROM chat_conversations WHERE user_id = %s", (user_id,)
            )

            # Step 3: Delete the user record
            cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()

            return {"success": True, "message": "User deleted successfully"}
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()
            conn.close()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting user: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
