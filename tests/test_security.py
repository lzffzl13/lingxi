"""Security utility tests."""

import pytest
from fastapi import HTTPException

from app.security.input_sanitizer import (
    MAX_MESSAGE_LENGTH,
    get_validated_session_id,
    sanitize_html,
    sanitize_input,
    validate_message_length,
    validate_request_size,
    validate_session_id,
)


def test_sanitize_input_strips_whitespace_and_null_bytes():
    assert sanitize_input("  he\x00llo  ") == "hello"


def test_sanitize_input_handles_empty_values():
    assert sanitize_input("") == ""
    assert sanitize_input(None) == ""


def test_sanitize_input_truncates_long_text():
    text = "x" * (MAX_MESSAGE_LENGTH + 10)

    assert len(sanitize_input(text)) == MAX_MESSAGE_LENGTH


def test_sanitize_html_escapes_special_characters():
    result = sanitize_html("<b onclick='x'>hello</b>")

    assert "&lt;b" in result
    assert "&#x27;" in result
    assert "<b" not in result


def test_validate_message_length():
    assert validate_message_length("short", max_length=5) is True
    assert validate_message_length("too long", max_length=5) is False


def test_validate_request_size():
    assert validate_request_size(None, max_size=10) is True
    assert validate_request_size(10, max_size=10) is True
    assert validate_request_size(11, max_size=10) is False


def test_validate_session_id():
    assert validate_session_id("abc-123") is True
    assert validate_session_id("abc_123") is False
    assert validate_session_id("") is False
    assert validate_session_id("x" * 129) is False


def test_get_validated_session_id_returns_valid_id():
    assert get_validated_session_id("abc-123") == "abc-123"


def test_get_validated_session_id_rejects_invalid_id():
    with pytest.raises(HTTPException) as exc_info:
        get_validated_session_id("abc_123")

    assert exc_info.value.status_code == 400
