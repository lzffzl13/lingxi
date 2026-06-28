"""ReAct agent flow tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agent.react import ReActAgent
from app.config import Settings


def make_agent(history=None):
    llm = MagicMock()
    llm.chat = AsyncMock()
    llm.chat_stream = MagicMock()
    session_mgr = AsyncMock()
    session_mgr.get_history.return_value = history or []
    session_mgr.get_pending_db_messages.return_value = []
    config = Settings()
    agent = ReActAgent(llm, session_mgr, config)
    agent._response_cache = MagicMock()
    agent._response_cache.get.return_value = None
    return agent, llm, session_mgr


def stop_response(content="final reply"):
    message = MagicMock()
    message.content = content
    message.tool_calls = None
    choice = MagicMock()
    choice.finish_reason = "stop"
    choice.message = message
    return MagicMock(choices=[choice])


def tool_response(name="check_order", arguments='{"order_id": "ORD-1"}', call_id="call-1"):
    tool_call = SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(name=name, arguments=arguments),
    )
    message = MagicMock()
    message.tool_calls = [tool_call]
    message.model_dump.return_value = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": call_id,
                "type": "function",
                "function": {"name": name, "arguments": arguments},
            }
        ],
    }
    choice = MagicMock()
    choice.finish_reason = "tool_calls"
    choice.message = message
    return MagicMock(choices=[choice])


def stream_chunk(content=None, finish_reason=None, tool_calls=None):
    delta = SimpleNamespace(content=content, tool_calls=tool_calls)
    choice = SimpleNamespace(delta=delta, finish_reason=finish_reason)
    return SimpleNamespace(choices=[choice])


async def async_stream(chunks):
    for chunk in chunks:
        yield chunk


@pytest.fixture
def patched_react_dependencies():
    with (
        patch("app.agent.react.ConversationRepository.create_conversation", new_callable=AsyncMock) as create_conversation,
        patch("app.agent.react.ConversationRepository.save_message", new_callable=AsyncMock) as save_message,
        patch("app.agent.react.AnalyticsRepository.track_event", new_callable=AsyncMock) as track_event,
        patch("app.agent.react.get_all_tools", return_value=[]),
        patch("app.agent.react.track_tool_call"),
        patch("app.agent.react.track_session_message"),
    ):
        yield {
            "create_conversation": create_conversation,
            "save_message": save_message,
            "track_event": track_event,
        }


@pytest.mark.asyncio
async def test_run_returns_final_answer_and_persists_messages(patched_react_dependencies):
    agent, llm, session_mgr = make_agent()
    llm.chat.return_value = stop_response("hello")

    response = await agent.run("s1", "hi")

    assert response.session_id == "s1"
    assert response.reply == "hello"
    assert response.status == "active"
    assert response.tool_calls_made == []
    patched_react_dependencies["create_conversation"].assert_awaited_once_with(
        conversation_id="s1",
        user_id=None,
    )
    assert session_mgr.append_message.await_count == 2
    assert patched_react_dependencies["save_message"].await_count == 2
    agent._response_cache.set.assert_called_once()


@pytest.mark.asyncio
async def test_run_uses_cached_response_for_first_turn(patched_react_dependencies):
    agent, llm, session_mgr = make_agent(history=[])
    agent._response_cache.get.return_value = "cached answer"

    response = await agent.run("s1", "hi")

    assert response.reply == "cached answer"
    assert response.tool_calls_made == []
    llm.chat.assert_not_called()
    assert session_mgr.append_message.await_count == 2
    assert patched_react_dependencies["save_message"].await_count == 2


@pytest.mark.asyncio
async def test_run_ignores_cache_when_history_exists(patched_react_dependencies):
    agent, llm, _ = make_agent(history=[MagicMock()])
    agent._response_cache.get.return_value = "cached answer"
    llm.chat.return_value = stop_response("fresh answer")

    response = await agent.run("s1", "hi")

    assert response.reply == "fresh answer"
    llm.chat.assert_awaited_once()
    agent._response_cache.set.assert_not_called()


@pytest.mark.asyncio
async def test_run_executes_tool_then_returns_final_answer(patched_react_dependencies):
    agent, llm, session_mgr = make_agent()
    llm.chat.side_effect = [tool_response("check_order"), stop_response("order found")]

    with patch("app.agent.react.execute_tool", new_callable=AsyncMock) as execute_tool:
        execute_tool.return_value = '{"status": "ok"}'
        response = await agent.run("s1", "where is my order?")

    assert response.reply == "order found"
    assert response.status == "active"
    assert response.tool_calls_made == ["check_order"]
    execute_tool.assert_awaited_once_with("check_order", {"order_id": "ORD-1"})
    session_mgr.update_slot.assert_not_called()
    assert llm.chat.await_count == 2


@pytest.mark.asyncio
async def test_run_transfer_tool_marks_session_transferred(patched_react_dependencies):
    agent, llm, session_mgr = make_agent()
    llm.chat.side_effect = [
        tool_response("transfer_to_human", '{"reason": "complaint"}'),
        stop_response("transferring"),
    ]

    with patch("app.agent.react.execute_tool", new_callable=AsyncMock) as execute_tool:
        execute_tool.return_value = '{"status": "transferred"}'
        response = await agent.run("s1", "complaint")

    assert response.status == "transferred"
    assert response.tool_calls_made == ["transfer_to_human"]
    session_mgr.update_slot.assert_awaited_once_with("s1", transferred=True)


@pytest.mark.asyncio
async def test_run_max_iterations_returns_transfer_fallback(patched_react_dependencies):
    agent, llm, session_mgr = make_agent()
    agent.MAX_ITERATIONS = 2
    llm.chat.return_value = tool_response("check_order")

    with patch("app.agent.react.execute_tool", new_callable=AsyncMock) as execute_tool:
        execute_tool.return_value = "{}"
        response = await agent.run("s1", "loop")

    assert response.status == "transferred"
    assert response.tool_calls_made == ["check_order", "check_order"]
    assert session_mgr.append_message.await_count == 2
    assert patched_react_dependencies["save_message"].await_count == 2


@pytest.mark.asyncio
async def test_run_stream_yields_tokens_and_done(patched_react_dependencies):
    agent, llm, session_mgr = make_agent()
    llm.chat_stream.return_value = async_stream(
        [
            stream_chunk(content="hel"),
            stream_chunk(content="lo", finish_reason="stop"),
        ]
    )

    events = [event async for event in agent.run_stream("s1", "hi", user_id="u1")]

    assert events[0].startswith("event: token")
    assert events[1].startswith("event: token")
    assert events[2].startswith("event: done")
    assert session_mgr.append_message.await_count == 2
    patched_react_dependencies["create_conversation"].assert_awaited_once_with(
        conversation_id="s1",
        user_id="u1",
    )
    assert patched_react_dependencies["save_message"].await_count == 2


@pytest.mark.asyncio
async def test_run_stream_executes_tool_then_finishes(patched_react_dependencies):
    agent, llm, session_mgr = make_agent()
    tool_delta = SimpleNamespace(
        index=0,
        id="call-1",
        function=SimpleNamespace(name="check_order", arguments='{"order_id": "ORD-1"}'),
    )
    llm.chat_stream.side_effect = [
        async_stream([stream_chunk(tool_calls=[tool_delta], finish_reason="tool_calls")]),
        async_stream([stream_chunk(content="done", finish_reason="stop")]),
    ]

    with patch("app.agent.react.execute_tool", new_callable=AsyncMock) as execute_tool:
        execute_tool.return_value = '{"status": "ok"}'
        events = [event async for event in agent.run_stream("s1", "tool please")]

    assert any(event.startswith("event: tool") for event in events)
    assert events[-1].startswith("event: done")
    execute_tool.assert_awaited_once_with("check_order", {"order_id": "ORD-1"})
    session_mgr.update_slot.assert_not_called()


@pytest.mark.asyncio
async def test_record_stream_interruption_persists_partial_reply(patched_react_dependencies):
    agent, _, session_mgr = make_agent()

    await agent.record_stream_interruption("s1", "partial", ["check_order"])

    assert session_mgr.append_message.await_count == 1
    patched_react_dependencies["save_message"].assert_awaited_once_with(
        conversation_id="s1",
        role="assistant",
        content="partial",
        tool_calls=["check_order"],
    )
    patched_react_dependencies["track_event"].assert_awaited_once()


@pytest.mark.asyncio
async def test_failed_database_persistence_is_queued_in_redis(patched_react_dependencies):
    agent, llm, session_mgr = make_agent()
    patched_react_dependencies["create_conversation"].return_value = None
    llm.chat.return_value = stop_response("hello")

    await agent.run("s1", "hi")

    assert session_mgr.append_pending_db_message.await_count == 2


@pytest.mark.asyncio
async def test_pending_messages_are_flushed_before_new_turn(patched_react_dependencies):
    agent, llm, session_mgr = make_agent()
    session_mgr.get_pending_db_messages.return_value = [
        {"role": "user", "content": "old", "tool_calls": None}
    ]
    llm.chat.return_value = stop_response("hello")

    await agent.run("s1", "hi")

    session_mgr.ack_pending_db_messages.assert_awaited_once_with("s1", 1)
