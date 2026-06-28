import json
from contextlib import suppress
from collections.abc import AsyncGenerator

from app.agent.llm import LLMClient
from app.agent.prompts import SYSTEM_PROMPT, build_messages
from app.config import Settings
from app.db.conversation_repo import ConversationRepository, AnalyticsRepository
from app.models.message import Message, MessageRole
from app.models.schemas import ChatResponse
from app.session.manager import SessionManager
from app.tools.base import execute_tool, get_all_tools
from app.monitoring import track_tool_call, track_session_message
from app.cache import get_response_cache
from app.utils.logger import logger


class ReActAgent:
    """ReAct loop agent for multi-turn conversation with tool calling."""

    MAX_ITERATIONS = 5

    def __init__(
        self,
        llm: LLMClient,
        session_mgr: SessionManager,
        config: Settings,
    ):
        self.llm = llm
        self.session_mgr = session_mgr
        self.config = config
        self._active_conversations: dict[str, bool] = {}  # Track if conversation is persisted
        self._response_cache = get_response_cache()

    async def _ensure_conversation(self, session_id: str, user_id: str | None = None) -> bool:
        """Ensure conversation record exists in database."""
        if session_id not in self._active_conversations:
            conversation = await ConversationRepository.create_conversation(
                conversation_id=session_id,
                user_id=user_id,
            )
            if not conversation:
                return False
            self._active_conversations[session_id] = True
        return True

    async def _persist_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: list[str] | None = None,
    ) -> bool:
        """Persist message to database."""
        message = await ConversationRepository.save_message(
            conversation_id=session_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
        )
        return message is not None

    async def _flush_pending_messages(self, session_id: str, user_id: str | None = None) -> int:
        """Persist queued database messages for this session."""
        if not await self._ensure_conversation(session_id, user_id):
            return 0

        pending_messages = await self.session_mgr.get_pending_db_messages(session_id)
        persisted_count = 0
        for payload in pending_messages:
            saved = await self._persist_message(
                session_id=session_id,
                role=payload["role"],
                content=payload["content"],
                tool_calls=payload.get("tool_calls"),
            )
            if not saved:
                break
            persisted_count += 1

        if persisted_count:
            await self.session_mgr.ack_pending_db_messages(session_id, persisted_count)

        return persisted_count

    async def _persist_or_queue_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: list[str] | None = None,
        user_id: str | None = None,
    ) -> None:
        """Persist a message to DB, or queue it in Redis if DB is unavailable."""
        if await self._ensure_conversation(session_id, user_id):
            if await self._persist_message(session_id, role, content, tool_calls):
                return

        await self.session_mgr.append_pending_db_message(
            session_id,
            {
                "role": role,
                "content": content,
                "tool_calls": tool_calls,
            },
        )

    async def _record_message(
        self,
        session_id: str,
        role: MessageRole,
        content: str,
        tool_calls: list[str] | None = None,
        user_id: str | None = None,
    ) -> None:
        """Record a message in Redis immediately and persist it for audit."""
        message = Message(role=role, content=content)
        await self.session_mgr.append_message(session_id, message)
        await self._persist_or_queue_message(
            session_id=session_id,
            role=role.value,
            content=content,
            tool_calls=tool_calls,
            user_id=user_id,
        )

    async def run(self, session_id: str, user_message: str) -> ChatResponse:
        """Execute a complete ReAct loop for one user turn."""

        # 0. Ensure conversation exists in database
        await self._ensure_conversation(session_id)
        await self._flush_pending_messages(session_id)

        # 1. Load history and slots
        history = await self.session_mgr.get_history(session_id)

        # 2. Save user message to history (Redis + DB)
        await self._record_message(session_id, MessageRole.USER, user_message)

        # Track analytics
        await AnalyticsRepository.track_event(
            "user_message",
            conversation_id=session_id,
        )

        # Track metrics
        track_session_message(role="user")

        # 3. Build messages for LLM
        messages = build_messages(SYSTEM_PROMPT, history, user_message)

        # 3.5 Check response cache (only for simple queries without tool calls)
        cached_response = self._response_cache.get(messages)
        if cached_response and not history:  # Only cache first message in conversation
            await self._record_message(session_id, MessageRole.ASSISTANT, cached_response)
            track_session_message(role="assistant")
            return ChatResponse(
                session_id=session_id,
                reply=cached_response,
                status="active",
                tool_calls_made=[],
            )

        # 4. ReAct loop
        tool_calls_made: list[str] = []
        for _ in range(self.MAX_ITERATIONS):
            response = await self.llm.chat(
                messages=messages,
                tools=get_all_tools(),
            )

            choice = response.choices[0]

            # 4a. LLM returns final answer (no tool calls)
            if choice.finish_reason == "stop":
                reply = choice.message.content or ""
                await self._record_message(
                    session_id, MessageRole.ASSISTANT, reply,
                    tool_calls=tool_calls_made if tool_calls_made else None,
                )

                # Cache response for simple queries (no tool calls)
                if not tool_calls_made and not history:
                    self._response_cache.set(messages, reply)

                status = self._determine_status(tool_calls_made)
                track_session_message(role="assistant")
                return ChatResponse(
                    session_id=session_id,
                    reply=reply,
                    status=status,
                    tool_calls_made=tool_calls_made,
                )

            # 4b. LLM requests tool calls
            if choice.message.tool_calls:
                # Add assistant message with tool_calls to context
                messages.append(choice.message.model_dump())

                for tc in choice.message.tool_calls:
                    tool_name = tc.function.name
                    tool_args = json.loads(tc.function.arguments)
                    tool_calls_made.append(tool_name)

                    # Execute tool with timing
                    import time
                    tool_start = time.time()
                    result = await execute_tool(tool_name, tool_args)
                    tool_duration = time.time() - tool_start

                    # Track tool call metrics
                    track_tool_call(tool_name=tool_name, duration=tool_duration, status='success')

                    # Add tool result to context
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })

                    # Special: mark session as transferred
                    if tool_name == "transfer_to_human":
                        await self.session_mgr.update_slot(
                            session_id, transferred=True
                        )

        # Max iterations exceeded - fallback
        fallback = "抱歉，我暂时无法处理您的问题，正在为您转接人工客服。"
        await self._record_message(
            session_id,
            MessageRole.ASSISTANT,
            fallback,
            tool_calls=tool_calls_made if tool_calls_made else None,
        )
        return ChatResponse(
            session_id=session_id,
            reply=fallback,
            status="transferred",
            tool_calls_made=tool_calls_made,
        )

    async def run_stream(
        self, session_id: str, user_message: str, user_id: str | None = None
    ) -> AsyncGenerator[str, None]:
        """Execute ReAct loop with streaming response.

        Yields SSE-formatted strings:
        - event: token\ndata: {"content": "..."}\n\n
        - event: tool\ndata: {"name": "...", "result": "..."}\n\n
        - event: done\ndata: {"session_id": "...", "status": "...", "tool_calls": [...]}\n\n
        """

        # 0. Ensure conversation exists
        await self._ensure_conversation(session_id, user_id)
        await self._flush_pending_messages(session_id, user_id)

        # 1. Load history
        history = await self.session_mgr.get_history(session_id)

        # 2. Save user message (Redis + DB)
        await self._record_message(session_id, MessageRole.USER, user_message, user_id=user_id)

        # Track analytics
        await AnalyticsRepository.track_event("user_message", conversation_id=session_id)

        # 3. Build messages for LLM
        messages = build_messages(SYSTEM_PROMPT, history, user_message)

        # 4. ReAct loop
        tool_calls_made: list[str] = []
        final_reply = ""

        for _ in range(self.MAX_ITERATIONS):
            # Stream LLM response
            collected_content = ""
            collected_tool_calls: list[dict] = []
            finish_reason = None

            async for chunk in self.llm.chat_stream(
                messages=messages,
                tools=get_all_tools(),
            ):
                if not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = choice.delta
                finish_reason = choice.finish_reason

                # Stream text content
                if delta.content:
                    collected_content += delta.content
                    yield f"event: token\ndata: {json.dumps({'content': delta.content})}\n\n"

                # Collect tool calls
                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        # Extend existing tool call or create new one
                        while len(collected_tool_calls) <= tc_delta.index:
                            collected_tool_calls.append({
                                "id": "",
                                "function": {"name": "", "arguments": ""},
                            })
                        tc = collected_tool_calls[tc_delta.index]
                        if tc_delta.id:
                            tc["id"] += tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tc["function"]["name"] += tc_delta.function.name
                            if tc_delta.function.arguments:
                                tc["function"]["arguments"] += tc_delta.function.arguments

            # Process completed response
            if finish_reason == "stop":
                # Final answer - save and finish
                final_reply = collected_content
                await self._record_message(
                    session_id, MessageRole.ASSISTANT, final_reply,
                    tool_calls=tool_calls_made if tool_calls_made else None,
                    user_id=user_id,
                )

                status = self._determine_status(tool_calls_made)
                yield f"event: done\ndata: {json.dumps({'session_id': session_id, 'status': status, 'tool_calls': tool_calls_made})}\n\n"
                return

            if collected_tool_calls:
                # Execute tool calls
                messages.append({
                    "role": "assistant",
                    "content": collected_content or None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": tc["function"],
                        }
                        for tc in collected_tool_calls
                    ],
                })

                for tc in collected_tool_calls:
                    tool_name = tc["function"]["name"]
                    tool_args = json.loads(tc["function"]["arguments"])
                    tool_calls_made.append(tool_name)

                    # Execute tool with timing
                    import time
                    tool_start = time.time()
                    result = await execute_tool(tool_name, tool_args)
                    tool_duration = time.time() - tool_start

                    # Track tool call metrics
                    track_tool_call(tool_name=tool_name, duration=tool_duration, status='success')

                    # Send tool event
                    yield f"event: tool\ndata: {json.dumps({'name': tool_name, 'result': result})}\n\n"

                    # Track tool usage
                    await AnalyticsRepository.track_event(
                        "tool_call",
                        conversation_id=session_id,
                        metadata={"tool_name": tool_name},
                    )

                    # Add tool result to context
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result,
                    })

                    # Special: mark session as transferred
                    if tool_name == "transfer_to_human":
                        await self.session_mgr.update_slot(
                            session_id, transferred=True
                        )

        # Max iterations exceeded
        fallback = "抱歉，我暂时无法处理您的问题，正在为您转接人工客服。"
        await self._record_message(
            session_id,
            MessageRole.ASSISTANT,
            fallback,
            tool_calls=tool_calls_made if tool_calls_made else None,
            user_id=user_id,
        )
        yield f"event: token\ndata: {json.dumps({'content': fallback})}\n\n"
        yield f"event: done\ndata: {json.dumps({'session_id': session_id, 'status': 'transferred', 'tool_calls': tool_calls_made})}\n\n"

    async def record_stream_interruption(
        self,
        session_id: str,
        partial_reply: str,
        tool_calls_made: list[str] | None = None,
    ) -> None:
        """Persist partial assistant output when an SSE client disconnects early."""
        if not partial_reply:
            return

        await self._record_message(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=partial_reply,
            tool_calls=tool_calls_made,
        )
        await AnalyticsRepository.track_event(
            "stream_interrupted",
            conversation_id=session_id,
            metadata={"partial_reply_length": len(partial_reply)},
        )
        logger.info(f"Persisted interrupted stream partial reply for session {session_id}")

    def _determine_status(self, tool_calls_made: list[str]) -> str:
        """Determine session status based on tool calls."""
        if "transfer_to_human" in tool_calls_made:
            return "transferred"
        return "active"
