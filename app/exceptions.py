"""Custom exceptions for LingXi Service."""


class LingXiError(Exception):
    """Base exception for LingXi Service."""

    def __init__(self, message: str, code: str = "INTERNAL_ERROR", status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


class SessionNotFoundError(LingXiError):
    """Session not found."""

    def __init__(self, session_id: str):
        super().__init__(
            message=f"Session {session_id} not found",
            code="SESSION_NOT_FOUND",
            status_code=404,
        )


class FAQNotFoundError(LingXiError):
    """FAQ not found."""

    def __init__(self, faq_id: int):
        super().__init__(
            message=f"FAQ {faq_id} not found",
            code="FAQ_NOT_FOUND",
            status_code=404,
        )


class LLMError(LingXiError):
    """LLM service error."""

    def __init__(self, detail: str = ""):
        message = f"LLM service error: {detail}" if detail else "LLM service error"
        super().__init__(
            message=message,
            code="LLM_ERROR",
            status_code=502,
        )


class ToolExecutionError(LingXiError):
    """Tool execution error."""

    def __init__(self, tool_name: str, detail: str = ""):
        message = f"Tool '{tool_name}' execution failed"
        if detail:
            message += f": {detail}"
        super().__init__(
            message=message,
            code="TOOL_ERROR",
            status_code=500,
        )


class RateLimitError(LingXiError):
    """Rate limit exceeded."""

    def __init__(self):
        super().__init__(
            message="Rate limit exceeded, please try again later",
            code="RATE_LIMIT_EXCEEDED",
            status_code=429,
        )


class AuthenticationError(LingXiError):
    """Authentication failed."""

    def __init__(self):
        super().__init__(
            message="Invalid or missing API key",
            code="AUTHENTICATION_ERROR",
            status_code=401,
        )


class ValidationError(LingXiError):
    """Request validation error."""

    def __init__(self, detail: str):
        super().__init__(
            message=f"Validation error: {detail}",
            code="VALIDATION_ERROR",
            status_code=422,
        )
