"""FastAPI application entry point with production-level features."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.agent.llm import LLMClient
from app.agent.react import ReActAgent
from app.api import deps
from app.api.middleware import APIKeyMiddleware, RateLimitMiddleware, RequestLoggingMiddleware
from app.api.router import api_router
from app.cache import init_response_cache
from app.config import settings
from app.db.database import close_db, init_db
from app.exceptions import LingXiError
from app.knowledge.rag_manager import RAGKnowledgeManager
from app.monitoring import MetricsMiddleware
from app.security import XSSProtectionMiddleware
from app.session.manager import SessionManager
from app.session.redis_client import close_redis, get_redis
from app.tools.search_faq import set_knowledge_manager
from app.utils.logger import logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management - initialize on startup, cleanup on shutdown."""
    logger.info("Starting LingXi Service...")

    await init_db()

    redis_client = get_redis()
    session_mgr = SessionManager(redis_client, settings)
    llm_client = LLMClient(settings)

    knowledge_mgr = RAGKnowledgeManager(settings)
    await knowledge_mgr.initialize()
    set_knowledge_manager(knowledge_mgr)

    init_response_cache(
        max_size=settings.CACHE_MAX_SIZE,
        ttl_seconds=settings.CACHE_TTL_SECONDS,
    )

    agent = ReActAgent(llm_client, session_mgr, settings)
    deps.init_deps(redis_client, agent, session_mgr, knowledge_mgr)

    logger.info("LingXi Service started successfully")

    yield

    logger.info("Shutting down LingXi Service...")
    await close_redis(redis_client)
    await close_db()
    logger.info("LingXi Service stopped")


app = FastAPI(
    title="LingXi Service",
    description="智能客服 Agent - 生产级 API",
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.APP_ENV != "production" else None,
    redoc_url="/redoc" if settings.APP_ENV != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if settings.AUTH_ENABLED:
    app.add_middleware(APIKeyMiddleware)

_rate_limit = int(settings.RATE_LIMIT.split("/")[0]) if settings.RATE_LIMIT else 60
app.add_middleware(RateLimitMiddleware, requests_per_minute=_rate_limit)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(XSSProtectionMiddleware)

static_dir = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
app.include_router(api_router)


@app.get("/")
async def root():
    """Serve the chat interface."""
    return FileResponse(str(static_dir / "index.html"))


@app.get("/admin")
async def admin():
    """Serve the admin dashboard."""
    return FileResponse(str(static_dir / "admin.html"))


@app.exception_handler(LingXiError)
async def lingxi_error_handler(request: Request, exc: LingXiError):
    """Handle custom LingXi errors."""
    logger.warning(f"LingXi error: {exc.code} - {exc.message}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unexpected errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "服务器内部错误，请稍后再试",
        },
    )
