"""SQLAlchemy ORM models for database tables."""

from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Enum, JSON, DECIMAL, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base


class Order(Base):
    """Order table."""
    __tablename__ = "orders"
    __table_args__ = {"extend_existing": True}

    id = Column(String(32), primary_key=True)
    user_id = Column(String(64), nullable=False, index=True)
    status = Column(
        Enum("pending", "paid", "shipped", "delivered", "cancelled", name="order_status"),
        nullable=False,
        default="pending"
    )
    items = Column(JSON, nullable=False)
    total_amount = Column(DECIMAL(10, 2), nullable=False)
    tracking_number = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationships
    return_orders = relationship("ReturnOrder", back_populates="order")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "status": self.status,
            "items": self.items,
            "total_amount": float(self.total_amount),
            "tracking_number": self.tracking_number,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ReturnOrder(Base):
    """Return order table."""
    __tablename__ = "return_orders"
    __table_args__ = {"extend_existing": True}

    id = Column(String(32), primary_key=True)
    order_id = Column(String(32), ForeignKey("orders.id"), nullable=False)
    type = Column(
        Enum("refund", "exchange", name="return_type"),
        nullable=False
    )
    reason = Column(Text, nullable=False)
    status = Column(
        Enum("pending", "approved", "rejected", "completed", name="return_status"),
        nullable=False,
        default="pending"
    )
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    order = relationship("Order", back_populates="return_orders")

    def to_dict(self):
        return {
            "id": self.id,
            "order_id": self.order_id,
            "type": self.type,
            "reason": self.reason,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class FAQ(Base):
    """FAQ knowledge base table."""
    __tablename__ = "faqs"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    category = Column(String(64), nullable=True)
    keywords = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def to_dict(self):
        return {
            "id": self.id,
            "question": self.question,
            "answer": self.answer,
            "category": self.category,
            "keywords": self.keywords,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class User(Base):
    """User table for user identification."""
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=True)
    phone = Column(String(20), nullable=True, unique=True, index=True)
    email = Column(String(128), nullable=True)
    avatar_url = Column(String(256), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    last_seen_at = Column(DateTime, default=datetime.now)

    # Relationships
    conversations = relationship("Conversation", back_populates="user")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "avatar_url": self.avatar_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
        }


class Conversation(Base):
    """Conversation session table."""
    __tablename__ = "conversations"
    __table_args__ = {"extend_existing": True}

    id = Column(String(64), primary_key=True)
    user_id = Column(String(64), ForeignKey("users.id"), nullable=True, index=True)
    status = Column(
        Enum("active", "resolved", "transferred", name="conversation_status"),
        nullable=False,
        default="active"
    )
    channel = Column(String(32), default="web")  # web, app, wechat, etc.
    started_at = Column(DateTime, default=datetime.now)
    ended_at = Column(DateTime, nullable=True)
    satisfaction_score = Column(Integer, nullable=True)  # 1-5
    resolved = Column(Boolean, default=False)

    # Relationships
    user = relationship("User", back_populates="conversations")
    messages = relationship("ChatMessage", back_populates="conversation", order_by="ChatMessage.created_at")

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "status": self.status,
            "channel": self.channel,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "satisfaction_score": self.satisfaction_score,
            "resolved": self.resolved,
        }


class ChatMessage(Base):
    """Individual chat message table."""
    __tablename__ = "chat_messages"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(64), ForeignKey("conversations.id"), nullable=False, index=True)
    role = Column(
        Enum("user", "assistant", "system", name="message_role"),
        nullable=False
    )
    content = Column(Text, nullable=False)
    tool_calls = Column(JSON, nullable=True)  # Tools used in this message
    created_at = Column(DateTime, default=datetime.now)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    def to_dict(self):
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "role": self.role,
            "content": self.content,
            "tool_calls": self.tool_calls,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AnalyticsEvent(Base):
    """Analytics event table for statistics."""
    __tablename__ = "analytics_events"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(32), nullable=False, index=True)  # message, tool_call, resolution, etc.
    conversation_id = Column(String(64), nullable=True, index=True)
    user_id = Column(String(64), nullable=True)
    event_metadata = Column("metadata", JSON, nullable=True)  # Additional event data
    created_at = Column(DateTime, default=datetime.now, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "event_type": self.event_type,
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "metadata": self.event_metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
