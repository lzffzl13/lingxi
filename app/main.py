from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import settings
from app.api.router import api_router
from app.session.redis_client import get_redis, close_redis
from app.session.manager import SessionManager
from app.agent.llm import LLMClient
from app.agent.react import ReActAgent

# Global singletons
_agent: ReActAgent | None = None
_redis = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management - initialize on startup, cleanup on shutdown."""
    global _agent, _redis

    # Startup
    _redis = get_redis()
    session_mgr = SessionManager(_redis, settings)
    llm_client = LLMClient(settings)
    _agent = ReActAgent(llm_client, session_mgr, settings)

    yield

    # Shutdown
    await close_redis(_redis)


app = FastAPI(
    title="LingXi Service",
    description="智能客服 Agent",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router)


def get_agent() -> ReActAgent:
    """Get the global agent instance."""
    assert _agent is not None, "Agent not initialized"
    return _agent


def get_redis_client():
    """Get the global Redis client."""
    assert _redis is not None, "Redis not initialized"
    return _redis
