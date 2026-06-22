"""Analytics and statistics API endpoints."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.api.deps import RedisDep
from app.db.conversation_repo import ConversationRepository, AnalyticsRepository

router = APIRouter(prefix="/analytics", tags=["analytics"])


class StatsResponse(BaseModel):
    period_days: int
    total_conversations: int
    resolved_conversations: int
    resolution_rate: float
    total_messages: int
    avg_satisfaction: Optional[float]
    tool_usage: dict[str, int]


class ConversationDetail(BaseModel):
    conversation: dict
    messages: list[dict]


@router.get("/stats", response_model=StatsResponse)
async def get_stats(days: int = Query(default=7, ge=1, le=90)):
    """Get analytics statistics for the last N days."""
    stats = await AnalyticsRepository.get_stats(days)
    return StatsResponse(**stats)


@router.get("/conversations/{conversation_id}")
async def get_conversation_detail(conversation_id: str):
    """Get conversation with all messages."""
    result = await ConversationRepository.get_conversation(conversation_id)
    if not result:
        return {"error": "Conversation not found"}
    return result


@router.get("/users/{user_id}/conversations")
async def get_user_conversations(
    user_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    """Get conversations for a specific user."""
    conversations = await ConversationRepository.get_user_conversations(
        user_id, limit, offset
    )
    return {"user_id": user_id, "conversations": conversations}
