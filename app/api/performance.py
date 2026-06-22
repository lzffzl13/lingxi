"""Performance statistics API endpoints."""

from fastapi import APIRouter
from prometheus_client import generate_latest
import re

router = APIRouter(prefix="/performance", tags=["performance"])


@router.get("/stats")
async def get_performance_stats():
    """Get comprehensive performance statistics."""
    # Get Prometheus metrics
    metrics_output = generate_latest().decode('utf-8')

    # Parse key metrics
    stats = {
        "http": _parse_http_metrics(metrics_output),
        "llm": _parse_llm_metrics(metrics_output),
        "tools": _parse_tool_metrics(metrics_output),
        "cache": _parse_cache_metrics(metrics_output),
        "rag": _parse_rag_metrics(metrics_output),
        "sessions": _parse_session_metrics(metrics_output),
    }

    return stats


@router.get("/summary")
async def get_performance_summary():
    """Get performance summary with key indicators."""
    metrics_output = generate_latest().decode('utf-8')

    # Extract key metrics
    total_requests = _extract_counter(metrics_output, 'lingxi_http_requests_total')
    total_errors = _extract_counter(metrics_output, 'lingxi_errors_total')
    total_llm_calls = _extract_counter(metrics_output, 'lingxi_llm_requests_total')
    total_tokens = _extract_counter(metrics_output, 'lingxi_llm_tokens_total')

    # Calculate rates
    error_rate = (total_errors / total_requests * 100) if total_requests > 0 else 0
    avg_tokens_per_call = (total_tokens / total_llm_calls) if total_llm_calls > 0 else 0

    return {
        "total_requests": total_requests,
        "total_errors": total_errors,
        "error_rate_percent": round(error_rate, 2),
        "total_llm_calls": total_llm_calls,
        "total_tokens": total_tokens,
        "avg_tokens_per_call": round(avg_tokens_per_call, 1),
        "status": "healthy" if error_rate < 5 else "degraded" if error_rate < 20 else "unhealthy",
    }


def _parse_http_metrics(metrics: str) -> dict:
    """Parse HTTP metrics from Prometheus output."""
    request_count = _extract_counter(metrics, 'lingxi_http_requests_total')
    return {
        "total_requests": request_count,
    }


def _parse_llm_metrics(metrics: str) -> dict:
    """Parse LLM metrics."""
    call_count = _extract_counter(metrics, 'lingxi_llm_requests_total')
    token_count = _extract_counter(metrics, 'lingxi_llm_tokens_total')
    return {
        "total_calls": call_count,
        "total_tokens": token_count,
        "avg_tokens_per_call": round(token_count / call_count, 1) if call_count > 0 else 0,
    }


def _parse_tool_metrics(metrics: str) -> dict:
    """Parse tool metrics."""
    call_count = _extract_counter(metrics, 'lingxi_tool_calls_total')
    return {
        "total_calls": call_count,
    }


def _parse_cache_metrics(metrics: str) -> dict:
    """Parse cache metrics."""
    hits = _extract_counter(metrics, 'lingxi_cache_hits_total')
    misses = _extract_counter(metrics, 'lingxi_cache_misses_total')
    total = hits + misses
    hit_rate = (hits / total * 100) if total > 0 else 0

    return {
        "hits": hits,
        "misses": misses,
        "hit_rate_percent": round(hit_rate, 2),
    }


def _parse_rag_metrics(metrics: str) -> dict:
    """Parse RAG metrics."""
    search_count = _extract_counter(metrics, 'lingxi_rag_searches_total')
    document_count = _extract_gauge(metrics, 'lingxi_rag_documents_total')

    return {
        "total_searches": search_count,
        "total_documents": document_count,
    }


def _parse_session_metrics(metrics: str) -> dict:
    """Parse session metrics."""
    message_count = _extract_counter(metrics, 'lingxi_session_messages_total')
    return {
        "total_messages": message_count,
    }


def _extract_counter(metrics: str, name: str) -> int:
    """Extract counter value from metrics text."""
    pattern = rf'^{name}\s+(\d+(?:\.\d+)?)'
    matches = re.findall(pattern, metrics, re.MULTILINE)
    return int(sum(float(m) for m in matches)) if matches else 0


def _extract_gauge(metrics: str, name: str) -> int:
    """Extract gauge value from metrics text."""
    pattern = rf'^{name}\s+(\d+(?:\.\d+)?)'
    matches = re.findall(pattern, metrics, re.MULTILINE)
    return int(float(matches[-1])) if matches else 0
