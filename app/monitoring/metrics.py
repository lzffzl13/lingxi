"""Prometheus metrics for monitoring application performance."""

from prometheus_client import Counter, Histogram, Gauge, Info, Summary
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import time

# Application info
APP_INFO = Info('lingxi_service', 'LingXi Service Application Info')
APP_INFO.info({
    'version': '1.1.0',
    'environment': 'development',
})

# Request metrics
REQUEST_COUNT = Counter(
    'lingxi_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

REQUEST_LATENCY = Histogram(
    'lingxi_http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'endpoint'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)

REQUEST_SIZE = Summary(
    'lingxi_http_request_size_bytes',
    'HTTP request size in bytes',
    ['method', 'endpoint']
)

RESPONSE_SIZE = Summary(
    'lingxi_http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint']
)

# LLM metrics
LLM_REQUEST_COUNT = Counter(
    'lingxi_llm_requests_total',
    'Total LLM API requests',
    ['model', 'status']
)

LLM_LATENCY = Histogram(
    'lingxi_llm_request_duration_seconds',
    'LLM request latency in seconds',
    ['model'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

LLM_TOKENS = Counter(
    'lingxi_llm_tokens_total',
    'Total LLM tokens processed',
    ['model', 'type']  # type: prompt, completion
)

LLM_COST = Counter(
    'lingxi_llm_cost_usd_total',
    'Total LLM cost in USD',
    ['model']
)

# Tool metrics
TOOL_CALL_COUNT = Counter(
    'lingxi_tool_calls_total',
    'Total tool calls',
    ['tool_name', 'status']
)

TOOL_LATENCY = Histogram(
    'lingxi_tool_call_duration_seconds',
    'Tool call latency in seconds',
    ['tool_name'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

# Session metrics
ACTIVE_SESSIONS = Gauge(
    'lingxi_active_sessions',
    'Number of active sessions'
)

SESSION_MESSAGES = Counter(
    'lingxi_session_messages_total',
    'Total session messages',
    ['role']  # user, assistant
)

SESSION_DURATION = Histogram(
    'lingxi_session_duration_seconds',
    'Session duration in seconds',
    buckets=[60, 300, 600, 1800, 3600, 7200]
)

# Cache metrics
CACHE_HITS = Counter(
    'lingxi_cache_hits_total',
    'Total cache hits',
    ['cache_type']  # response, faq, rag
)

CACHE_MISSES = Counter(
    'lingxi_cache_misses_total',
    'Total cache misses',
    ['cache_type']
)

CACHE_SIZE = Gauge(
    'lingxi_cache_size',
    'Current cache size',
    ['cache_type']
)

# RAG metrics
RAG_SEARCH_COUNT = Counter(
    'lingxi_rag_searches_total',
    'Total RAG searches',
    ['status', 'source']
)

RAG_SEARCH_LATENCY = Histogram(
    'lingxi_rag_search_duration_seconds',
    'RAG search latency in seconds',
    ['source'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
)

RAG_DOCUMENTS = Gauge(
    'lingxi_rag_documents_total',
    'Total documents in RAG store'
)

# Error metrics
ERROR_COUNT = Counter(
    'lingxi_errors_total',
    'Total errors',
    ['error_type']
)

# Business metrics
CONVERSATION_RESOLVED = Counter(
    'lingxi_conversations_resolved_total',
    'Total resolved conversations',
    ['resolution_type']  # auto, human, abandoned
)

USER_SATISFACTION = Histogram(
    'lingxi_user_satisfaction_score',
    'User satisfaction score',
    buckets=[1, 2, 3, 4, 5]
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP request metrics."""

    async def dispatch(self, request: Request, call_next):
        # Skip metrics endpoint to avoid recursion
        if request.url.path == '/metrics':
            return await call_next(request)

        method = request.method
        path = request.url.path

        # Normalize path (remove IDs)
        normalized_path = self._normalize_path(path)

        # Get request size
        request_size = int(request.headers.get('content-length', 0))
        REQUEST_SIZE.labels(method=method, endpoint=normalized_path).observe(request_size)

        start_time = time.time()
        response = await call_next(request)
        duration = time.time() - start_time

        # Record metrics
        REQUEST_COUNT.labels(
            method=method,
            endpoint=normalized_path,
            status_code=response.status_code
        ).inc()

        REQUEST_LATENCY.labels(
            method=method,
            endpoint=normalized_path
        ).observe(duration)

        # Get response size
        response_size = int(response.headers.get('content-length', 0))
        RESPONSE_SIZE.labels(method=method, endpoint=normalized_path).observe(response_size)

        return response

    def _normalize_path(self, path: str) -> str:
        """Normalize URL path by replacing IDs with placeholders."""
        import re
        # Replace UUIDs and numeric IDs
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{id}', path)
        path = re.sub(r'/\d+', '/{id}', path)
        return path


def track_llm_call(model: str, duration: float, status: str = 'success', prompt_tokens: int = 0, completion_tokens: int = 0, cost: float = 0):
    """Track LLM API call metrics."""
    LLM_REQUEST_COUNT.labels(model=model, status=status).inc()
    LLM_LATENCY.labels(model=model).observe(duration)
    if prompt_tokens:
        LLM_TOKENS.labels(model=model, type='prompt').inc(prompt_tokens)
    if completion_tokens:
        LLM_TOKENS.labels(model=model, type='completion').inc(completion_tokens)
    if cost:
        LLM_COST.labels(model=model).inc(cost)


def track_tool_call(tool_name: str, duration: float, status: str = 'success'):
    """Track tool call metrics."""
    TOOL_CALL_COUNT.labels(tool_name=tool_name, status=status).inc()
    TOOL_LATENCY.labels(tool_name=tool_name).observe(duration)


def track_session_message(role: str):
    """Track session message."""
    SESSION_MESSAGES.labels(role=role).inc()


def track_session_duration(duration: float):
    """Track session duration."""
    SESSION_DURATION.observe(duration)


def track_cache_hit(cache_type: str):
    """Track cache hit."""
    CACHE_HITS.labels(cache_type=cache_type).inc()


def track_cache_miss(cache_type: str):
    """Track cache miss."""
    CACHE_MISSES.labels(cache_type=cache_type).inc()


def update_cache_size(cache_type: str, size: int):
    """Update cache size."""
    CACHE_SIZE.labels(cache_type=cache_type).set(size)


def track_rag_search(duration: float, status: str = 'success', source: str = 'rag'):
    """Track RAG search."""
    RAG_SEARCH_COUNT.labels(status=status, source=source).inc()
    RAG_SEARCH_LATENCY.labels(source=source).observe(duration)


def update_rag_documents(count: int):
    """Update RAG document count."""
    RAG_DOCUMENTS.set(count)


def track_error(error_type: str):
    """Track error occurrence."""
    ERROR_COUNT.labels(error_type=error_type).inc()


def track_conversation_resolved(resolution_type: str):
    """Track conversation resolution."""
    CONVERSATION_RESOLVED.labels(resolution_type=resolution_type).inc()


def track_user_satisfaction(score: int):
    """Track user satisfaction score."""
    USER_SATISFACTION.observe(score)


def update_active_sessions(count: int):
    """Update active sessions gauge."""
    ACTIVE_SESSIONS.set(count)
