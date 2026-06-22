"""Input sanitization and validation utilities."""

import re
from typing import Optional
from fastapi import HTTPException


# Maximum lengths
MAX_MESSAGE_LENGTH = 10000
MAX_REQUEST_SIZE = 1024 * 1024  # 1MB


def sanitize_input(text: str) -> str:
    """Sanitize user input to prevent injection attacks.

    - Strips leading/trailing whitespace
    - Removes null bytes
    - Limits length
    """
    if not text:
        return ""

    # Remove null bytes
    text = text.replace('\x00', '')

    # Strip whitespace
    text = text.strip()

    # Limit length
    if len(text) > MAX_MESSAGE_LENGTH:
        text = text[:MAX_MESSAGE_LENGTH]

    return text


def sanitize_html(text: str) -> str:
    """Sanitize HTML content to prevent XSS.

    - Escapes HTML special characters
    - Removes script tags
    - Removes event handlers
    """
    if not text:
        return ""

    # Escape HTML special characters
    html_escape_table = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
    }
    text = ''.join(html_escape_table.get(c, c) for c in text)

    # Remove script tags and event handlers
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r'on\w+\s*=', '', text, flags=re.IGNORECASE)

    return text


def validate_message_length(message: str, max_length: int = MAX_MESSAGE_LENGTH) -> bool:
    """Validate message length."""
    return len(message) <= max_length


def validate_request_size(content_length: Optional[int], max_size: int = MAX_REQUEST_SIZE) -> bool:
    """Validate request body size."""
    if content_length is None:
        return True
    return content_length <= max_size


def validate_session_id(session_id: str) -> bool:
    """Validate session ID format.

    Must be alphanumeric with hyphens, 1-128 characters.
    """
    pattern = r'^[a-zA-Z0-9\-]{1,128}$'
    return bool(re.match(pattern, session_id))


def get_validated_session_id(session_id: str) -> str:
    """Get validated session ID or raise HTTP exception."""
    if not validate_session_id(session_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid session ID format"
        )
    return session_id
