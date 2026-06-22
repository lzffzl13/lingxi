"""Tests for knowledge base tools."""

import json
from unittest.mock import AsyncMock

import pytest

from app.tools.search_faq import SearchFaqTool, set_knowledge_manager


@pytest.fixture(autouse=True)
def reset_knowledge_manager():
    """Reset the module-level knowledge manager around each test."""
    import app.tools.search_faq as module

    module._knowledge_manager = None
    yield
    module._knowledge_manager = None


@pytest.mark.asyncio
async def test_search_faq_tool_no_manager():
    """Search FAQ tool reports an error without a knowledge manager."""
    tool = SearchFaqTool()

    result = await tool.execute("test")
    data = json.loads(result)

    assert "error" in data


@pytest.mark.asyncio
async def test_search_faq_tool_with_mock():
    """Search FAQ tool returns serialized results from the manager."""
    mock_manager = AsyncMock()
    mock_manager.search.return_value = [
        {
            "question": "How do I check an order?",
            "answer": "Provide an order id.",
            "category": "orders",
            "score": 0.95,
        }
    ]
    set_knowledge_manager(mock_manager)
    tool = SearchFaqTool()

    result = await tool.execute("order status")
    data = json.loads(result)

    assert data == mock_manager.search.return_value
    mock_manager.search.assert_awaited_once_with("order status")


@pytest.mark.asyncio
async def test_search_faq_tool_no_results():
    """Search FAQ tool returns a message when no results match."""
    mock_manager = AsyncMock()
    mock_manager.search.return_value = []
    set_knowledge_manager(mock_manager)
    tool = SearchFaqTool()

    result = await tool.execute("unrelated question")
    data = json.loads(result)

    assert "message" in data
