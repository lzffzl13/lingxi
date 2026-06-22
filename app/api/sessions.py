"""Session management API endpoints."""

import json

from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import RedisDep
from app.exceptions import SessionNotFoundError

router = APIRouter(prefix="/sessions", tags=["sessions"])


class SessionInfo(BaseModel):
    session_id: str
    message_count: int
    has_slots: bool


class SessionHistory(BaseModel):
    session_id: str
    messages: list[dict]


@router.get("", response_model=list[SessionInfo])
async def list_sessions(r: RedisDep):
    """List all active sessions."""
    # Get all session keys
    keys = []
    async for key in r.scan_iter("session:*:history"):
        keys.append(key)

    sessions = []
    for key in keys:
        session_id = key.split(":")[1]
        message_count = await r.llen(key)
        has_slots = await r.exists(f"session:{session_id}:slots")

        sessions.append(SessionInfo(
            session_id=session_id,
            message_count=message_count,
            has_slots=bool(has_slots),
        ))

    return sessions


@router.get("/{session_id}", response_model=SessionHistory)
async def get_session(session_id: str, r: RedisDep):
    """Get session history."""
    # Check if session exists
    if not await r.exists(f"session:{session_id}:history"):
        raise SessionNotFoundError(session_id)

    # Get messages
    messages = await r.lrange(f"session:{session_id}:history", 0, -1)
    parsed_messages = [json.loads(msg) for msg in messages]

    return SessionHistory(
        session_id=session_id,
        messages=parsed_messages,
    )


@router.delete("/{session_id}")
async def delete_session(session_id: str, r: RedisDep):
    """Delete a session."""
    # Check if session exists
    if not await r.exists(f"session:{session_id}:history"):
        raise SessionNotFoundError(session_id)

    # Delete session data
    await r.delete(f"session:{session_id}:history")
    await r.delete(f"session:{session_id}:slots")

    return {"message": f"Session {session_id} deleted"}


@router.get("/{session_id}/slots")
async def get_session_slots(session_id: str, r: RedisDep):
    """Get session slots."""
    # Check if session exists
    if not await r.exists(f"session:{session_id}:history"):
        raise SessionNotFoundError(session_id)

    # Get slots
    slots = await r.hgetall(f"session:{session_id}:slots")

    return {"session_id": session_id, "slots": slots}
