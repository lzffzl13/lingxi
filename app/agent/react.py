import json
from app.agent.llm import LLMClient
from app.agent.prompts import SYSTEM_PROMPT, build_messages
from app.config import Settings
from app.models.message import Message, MessageRole
from app.models.schemas import ChatResponse
from app.session.manager import SessionManager
from app.tools.base import execute_tool, get_all_tools


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

    async def run(self, session_id: str, user_message: str) -> ChatResponse:
        """Execute a complete ReAct loop for one user turn."""

        # 1. Load history and slots
        history = await self.session_mgr.get_history(session_id)

        # 2. Save user message to history
        user_msg = Message(role=MessageRole.USER, content=user_message)
        await self.session_mgr.append_message(session_id, user_msg)

        # 3. Build messages for LLM
        messages = build_messages(SYSTEM_PROMPT, history, user_message)

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
                assistant_msg = Message(role=MessageRole.ASSISTANT, content=reply)
                await self.session_mgr.append_message(session_id, assistant_msg)
                status = self._determine_status(tool_calls_made)
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

                    # Execute tool
                    result = await execute_tool(tool_name, tool_args)

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
        assistant_msg = Message(role=MessageRole.ASSISTANT, content=fallback)
        await self.session_mgr.append_message(session_id, assistant_msg)
        return ChatResponse(
            session_id=session_id,
            reply=fallback,
            status="transferred",
            tool_calls_made=tool_calls_made,
        )

    def _determine_status(self, tool_calls_made: list[str]) -> str:
        """Determine session status based on tool calls."""
        if "transfer_to_human" in tool_calls_made:
            return "transferred"
        return "active"
