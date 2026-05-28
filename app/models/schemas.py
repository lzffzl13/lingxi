from pydantic import BaseModel, Field
from typing import Optional


class ChatRequest(BaseModel):
    """Request model for chat endpoint."""
    session_id: str = Field(..., min_length=1, max_length=128)
    message: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    """Response model for chat endpoint."""
    session_id: str
    reply: str
    status: str = "active"  # "active" | "transferred" | "resolved"
    tool_calls_made: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """Response model for health endpoint."""
    status: str  # "ok" | "degraded"
    redis: str  # "connected" | "disconnected"
    llm: str  # "available" | "unavailable"
    version: str
