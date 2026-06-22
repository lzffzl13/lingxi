"""Dependency injection for FastAPI endpoints."""

from typing import Annotated

import redis.asyncio as aioredis
from fastapi import Depends

from app.agent.react import ReActAgent
from app.knowledge.manager import KnowledgeManager
from app.session.manager import SessionManager
from app.utils.logger import logger

# Module-level singletons (initialized during app lifespan)
_redis: aioredis.Redis | None = None
_agent: ReActAgent | None = None
_session_mgr: SessionManager | None = None
_knowledge_mgr: KnowledgeManager | None = None


def init_deps(
    redis_client: aioredis.Redis,
    agent: ReActAgent,
    session_mgr: SessionManager,
    knowledge_mgr: KnowledgeManager,
) -> None:
    """Initialize dependencies during app startup."""
    global _redis, _agent, _session_mgr, _knowledge_mgr
    _redis = redis_client
    _agent = agent
    _session_mgr = session_mgr
    _knowledge_mgr = knowledge_mgr
    logger.info("Dependencies initialized")


def get_redis() -> aioredis.Redis:
    """Get Redis client dependency."""
    assert _redis is not None, "Redis not initialized"
    return _redis


def get_agent() -> ReActAgent:
    """Get ReAct agent dependency."""
    assert _agent is not None, "Agent not initialized"
    return _agent


def get_session_manager() -> SessionManager:
    """Get session manager dependency."""
    assert _session_mgr is not None, "SessionManager not initialized"
    return _session_mgr


def get_knowledge_manager() -> KnowledgeManager:
    """Get knowledge manager dependency."""
    assert _knowledge_mgr is not None, "KnowledgeManager not initialized"
    return _knowledge_mgr


# Type aliases for dependency injection
RedisDep = Annotated[aioredis.Redis, Depends(get_redis)]
AgentDep = Annotated[ReActAgent, Depends(get_agent)]
SessionManagerDep = Annotated[SessionManager, Depends(get_session_manager)]
KnowledgeManagerDep = Annotated[KnowledgeManager, Depends(get_knowledge_manager)]
