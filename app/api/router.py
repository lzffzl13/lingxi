"""API router aggregation."""

from fastapi import APIRouter
from app.api.chat import router as chat_router
from app.api.health import router as health_router
from app.api.sessions import router as sessions_router
from app.api.knowledge import router as knowledge_router
from app.api.analytics import router as analytics_router
from app.api.metrics import router as metrics_router
from app.api.prompt import router as prompt_router
from app.api.performance import router as performance_router

api_router = APIRouter()
api_router.include_router(chat_router, tags=["chat"])
api_router.include_router(health_router, tags=["health"])
api_router.include_router(sessions_router, tags=["sessions"])
api_router.include_router(knowledge_router, tags=["knowledge"])
api_router.include_router(analytics_router, tags=["analytics"])
api_router.include_router(metrics_router, tags=["monitoring"])
api_router.include_router(prompt_router, tags=["prompt"])
api_router.include_router(performance_router, tags=["performance"])
