from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from typing import Optional


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Message(BaseModel):
    """Chat message with role, content, and optional tool call info."""
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    tool_call_id: Optional[str] = None
    tool_name: Optional[str] = None


class SessionSlot(BaseModel):
    """Session slots for storing structured information during conversation."""
    order_id: Optional[str] = None
    customer_name: Optional[str] = None
    issue_type: Optional[str] = None
    intent: Optional[str] = None
    transferred: bool = False
    collected_info: dict = Field(default_factory=dict)
