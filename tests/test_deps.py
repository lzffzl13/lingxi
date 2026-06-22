"""Dependency injection tests."""

import pytest
from unittest.mock import MagicMock

from app.api.deps import (
    init_deps,
    get_redis,
    get_agent,
    get_session_manager,
    get_knowledge_manager,
)


class TestDeps:
    """Tests for dependency injection module."""

    def setup_method(self):
        """Reset module state before each test."""
        import app.api.deps as deps_module
        deps_module._redis = None
        deps_module._agent = None
        deps_module._session_mgr = None
        deps_module._knowledge_mgr = None

    def test_init_deps(self):
        """Test dependency initialization."""
        mock_redis = MagicMock()
        mock_agent = MagicMock()
        mock_session_mgr = MagicMock()
        mock_knowledge_mgr = MagicMock()

        init_deps(mock_redis, mock_agent, mock_session_mgr, mock_knowledge_mgr)

        assert get_redis() == mock_redis
        assert get_agent() == mock_agent
        assert get_session_manager() == mock_session_mgr
        assert get_knowledge_manager() == mock_knowledge_mgr

    def test_get_redis_not_initialized(self):
        """Test get_redis raises when not initialized."""
        with pytest.raises(AssertionError, match="Redis not initialized"):
            get_redis()

    def test_get_agent_not_initialized(self):
        """Test get_agent raises when not initialized."""
        with pytest.raises(AssertionError, match="Agent not initialized"):
            get_agent()

    def test_get_session_manager_not_initialized(self):
        """Test get_session_manager raises when not initialized."""
        with pytest.raises(AssertionError, match="SessionManager not initialized"):
            get_session_manager()

    def test_get_knowledge_manager_not_initialized(self):
        """Test get_knowledge_manager raises when not initialized."""
        with pytest.raises(AssertionError, match="KnowledgeManager not initialized"):
            get_knowledge_manager()


class TestExceptions:
    """Tests for custom exceptions."""

    def test_session_not_found_error(self):
        """Test SessionNotFoundError."""
        from app.exceptions import SessionNotFoundError

        error = SessionNotFoundError("test-123")
        assert error.status_code == 404
        assert error.code == "SESSION_NOT_FOUND"
        assert "test-123" in error.message

    def test_faq_not_found_error(self):
        """Test FAQNotFoundError."""
        from app.exceptions import FAQNotFoundError

        error = FAQNotFoundError(42)
        assert error.status_code == 404
        assert error.code == "FAQ_NOT_FOUND"
        assert "42" in error.message

    def test_llm_error(self):
        """Test LLMError."""
        from app.exceptions import LLMError

        error = LLMError("timeout")
        assert error.status_code == 502
        assert error.code == "LLM_ERROR"
        assert "timeout" in error.message

    def test_tool_execution_error(self):
        """Test ToolExecutionError."""
        from app.exceptions import ToolExecutionError

        error = ToolExecutionError("check_order", "connection failed")
        assert error.status_code == 500
        assert error.code == "TOOL_ERROR"
        assert "check_order" in error.message
        assert "connection failed" in error.message

    def test_rate_limit_error(self):
        """Test RateLimitError."""
        from app.exceptions import RateLimitError

        error = RateLimitError()
        assert error.status_code == 429
        assert error.code == "RATE_LIMIT_EXCEEDED"

    def test_authentication_error(self):
        """Test AuthenticationError."""
        from app.exceptions import AuthenticationError

        error = AuthenticationError()
        assert error.status_code == 401
        assert error.code == "AUTHENTICATION_ERROR"

    def test_validation_error(self):
        """Test ValidationError."""
        from app.exceptions import ValidationError

        error = ValidationError("invalid email format")
        assert error.status_code == 422
        assert error.code == "VALIDATION_ERROR"
        assert "invalid email format" in error.message
