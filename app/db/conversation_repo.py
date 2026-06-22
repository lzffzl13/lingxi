"""Conversation repository for persisting chat history."""

from datetime import datetime
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_factory
from app.db.models import Conversation, ChatMessage, User, AnalyticsEvent
from app.utils.logger import logger


class ConversationRepository:
    """Repository for conversation persistence operations."""

    @staticmethod
    async def create_conversation(
        conversation_id: str,
        user_id: Optional[str] = None,
        channel: str = "web",
    ) -> Optional[Conversation]:
        """Create a new conversation record."""
        if not async_session_factory:
            return None

        try:
            async with async_session_factory() as session:
                conversation = Conversation(
                    id=conversation_id,
                    user_id=user_id,
                    channel=channel,
                    started_at=datetime.now(),
                )
                session.add(conversation)
                await session.commit()
                return conversation
        except Exception as e:
            logger.error(f"Failed to create conversation: {e}")
            return None

    @staticmethod
    async def save_message(
        conversation_id: str,
        role: str,
        content: str,
        tool_calls: Optional[list] = None,
    ) -> Optional[ChatMessage]:
        """Save a chat message to database."""
        if not async_session_factory:
            return None

        try:
            async with async_session_factory() as session:
                message = ChatMessage(
                    conversation_id=conversation_id,
                    role=role,
                    content=content,
                    tool_calls=tool_calls,
                    created_at=datetime.now(),
                )
                session.add(message)
                await session.commit()
                return message
        except Exception as e:
            logger.error(f"Failed to save message: {e}")
            return None

    @staticmethod
    async def end_conversation(
        conversation_id: str,
        status: str = "resolved",
        satisfaction_score: Optional[int] = None,
    ) -> bool:
        """Mark a conversation as ended."""
        if not async_session_factory:
            return False

        try:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(Conversation).where(Conversation.id == conversation_id)
                )
                conversation = result.scalar_one_or_none()
                if conversation:
                    conversation.status = status
                    conversation.ended_at = datetime.now()
                    conversation.resolved = status == "resolved"
                    if satisfaction_score:
                        conversation.satisfaction_score = satisfaction_score
                    await session.commit()
                    return True
                return False
        except Exception as e:
            logger.error(f"Failed to end conversation: {e}")
            return False

    @staticmethod
    async def get_conversation(conversation_id: str) -> Optional[dict]:
        """Get conversation with messages."""
        if not async_session_factory:
            return None

        try:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(Conversation).where(Conversation.id == conversation_id)
                )
                conversation = result.scalar_one_or_none()
                if not conversation:
                    return None

                # Get messages
                msg_result = await session.execute(
                    select(ChatMessage)
                    .where(ChatMessage.conversation_id == conversation_id)
                    .order_by(ChatMessage.created_at)
                )
                messages = msg_result.scalars().all()

                return {
                    "conversation": conversation.to_dict(),
                    "messages": [m.to_dict() for m in messages],
                }
        except Exception as e:
            logger.error(f"Failed to get conversation: {e}")
            return None

    @staticmethod
    async def get_user_conversations(
        user_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict]:
        """Get conversations for a user."""
        if not async_session_factory:
            return []

        try:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(Conversation)
                    .where(Conversation.user_id == user_id)
                    .order_by(Conversation.started_at.desc())
                    .limit(limit)
                    .offset(offset)
                )
                conversations = result.scalars().all()
                return [c.to_dict() for c in conversations]
        except Exception as e:
            logger.error(f"Failed to get user conversations: {e}")
            return []


class UserRepository:
    """Repository for user operations."""

    @staticmethod
    async def get_or_create_user(
        user_id: str,
        name: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> Optional[User]:
        """Get existing user or create new one."""
        if not async_session_factory:
            return None

        try:
            async with async_session_factory() as session:
                # Try to find existing user
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()

                if user:
                    # Update last seen
                    user.last_seen_at = datetime.now()
                    if name:
                        user.name = name
                    if phone:
                        user.phone = phone
                else:
                    # Create new user
                    user = User(
                        id=user_id,
                        name=name,
                        phone=phone,
                        created_at=datetime.now(),
                        last_seen_at=datetime.now(),
                    )
                    session.add(user)

                await session.commit()
                return user
        except Exception as e:
            logger.error(f"Failed to get/create user: {e}")
            return None

    @staticmethod
    async def get_user(user_id: str) -> Optional[dict]:
        """Get user by ID."""
        if not async_session_factory:
            return None

        try:
            async with async_session_factory() as session:
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                return user.to_dict() if user else None
        except Exception as e:
            logger.error(f"Failed to get user: {e}")
            return None


class AnalyticsRepository:
    """Repository for analytics events."""

    @staticmethod
    async def track_event(
        event_type: str,
        conversation_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """Track an analytics event."""
        if not async_session_factory:
            return False

        try:
            async with async_session_factory() as session:
                event = AnalyticsEvent(
                    event_type=event_type,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    event_metadata=metadata,
                    created_at=datetime.now(),
                )
                session.add(event)
                await session.commit()
                return True
        except Exception as e:
            logger.error(f"Failed to track event: {e}")
            return False

    @staticmethod
    async def get_stats(days: int = 7) -> dict:
        """Get analytics statistics for the last N days."""
        if not async_session_factory:
            return {}

        try:
            from datetime import timedelta
            cutoff = datetime.now() - timedelta(days=days)

            async with async_session_factory() as session:
                # Total conversations
                conv_count = await session.execute(
                    select(func.count(Conversation.id))
                    .where(Conversation.started_at >= cutoff)
                )
                total_conversations = conv_count.scalar() or 0

                # Resolved conversations
                resolved_count = await session.execute(
                    select(func.count(Conversation.id))
                    .where(Conversation.started_at >= cutoff)
                    .where(Conversation.resolved == True)
                )
                resolved_conversations = resolved_count.scalar() or 0

                # Total messages
                msg_count = await session.execute(
                    select(func.count(ChatMessage.id))
                    .where(ChatMessage.created_at >= cutoff)
                )
                total_messages = msg_count.scalar() or 0

                # Average satisfaction
                avg_score = await session.execute(
                    select(func.avg(Conversation.satisfaction_score))
                    .where(Conversation.started_at >= cutoff)
                    .where(Conversation.satisfaction_score.isnot(None))
                )
                avg_satisfaction = avg_score.scalar()

                # Tool usage
                tool_events = await session.execute(
                    select(AnalyticsEvent.metadata)
                    .where(AnalyticsEvent.event_type == "tool_call")
                    .where(AnalyticsEvent.created_at >= cutoff)
                )
                tool_usage = {}
                for row in tool_events.scalars():
                    if row and "tool_name" in row:
                        tool_name = row["tool_name"]
                        tool_usage[tool_name] = tool_usage.get(tool_name, 0) + 1

                return {
                    "period_days": days,
                    "total_conversations": total_conversations,
                    "resolved_conversations": resolved_conversations,
                    "resolution_rate": resolved_conversations / total_conversations if total_conversations > 0 else 0,
                    "total_messages": total_messages,
                    "avg_satisfaction": round(avg_satisfaction, 2) if avg_satisfaction else None,
                    "tool_usage": tool_usage,
                }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}
