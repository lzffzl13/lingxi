"""Agent and LLM client tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APIError, APITimeoutError, RateLimitError
from openai.types.chat import ChatCompletion, ChatCompletionMessage
from openai.types.chat.chat_completion import Choice

from app.agent.llm import LLMClient
from app.agent.prompts import SYSTEM_PROMPT, build_messages, detect_scene
from app.models.message import Message, MessageRole


@pytest.fixture
def mock_config():
    """Create mock config."""
    config = MagicMock()
    config.LLM_API_KEY = MagicMock()
    config.LLM_API_KEY.get_secret_value.return_value = "test-key"
    config.LLM_BASE_URL = "https://api.test.com/v1"
    config.LLM_MODEL = "test-model"
    config.LLM_TEMPERATURE = 0.7
    config.LLM_MAX_TOKENS = 1024
    config.LLM_MAX_RETRIES = 3
    config.LLM_RETRY_DELAY = 0.1
    config.LLM_REQUEST_TIMEOUT = 10.0
    return config


@pytest.fixture
def llm_client(mock_config):
    """Create LLMClient with mock config."""
    return LLMClient(mock_config)


def create_mock_completion(content: str = "test response", finish_reason: str = "stop"):
    """Create a mock ChatCompletion."""
    message = ChatCompletionMessage(
        role="assistant",
        content=content,
    )
    choice = Choice(
        index=0,
        message=message,
        finish_reason=finish_reason,
    )
    return MagicMock(spec=ChatCompletion, choices=[choice])


class TestLLMClient:
    """Tests for LLMClient."""

    @pytest.mark.asyncio
    async def test_chat_success(self, llm_client):
        """Test successful chat completion."""
        mock_response = create_mock_completion("Hello!")

        with patch.object(llm_client.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response
            result = await llm_client.chat([{"role": "user", "content": "hi"}])

            assert result.choices[0].message.content == "Hello!"
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_chat_with_tools(self, llm_client):
        """Test chat with tools parameter."""
        mock_response = create_mock_completion("test")
        tools = [{"type": "function", "function": {"name": "test_tool"}}]

        with patch.object(llm_client.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            mock_create.return_value = mock_response
            await llm_client.chat([{"role": "user", "content": "hi"}], tools=tools)

            call_kwargs = mock_create.call_args[1]
            assert "tools" in call_kwargs
            assert call_kwargs["tool_choice"] == "auto"

    @pytest.mark.asyncio
    async def test_retry_on_api_error(self, llm_client):
        """Test retry logic on API errors."""
        mock_response = create_mock_completion("success")

        with patch.object(llm_client.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = [
                APIError(message="Server error", request=MagicMock(), body=None),
                APIError(message="Server error", request=MagicMock(), body=None),
                mock_response,
            ]

            result = await llm_client.chat([{"role": "user", "content": "hi"}])
            assert result.choices[0].message.content == "success"
            assert mock_create.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, llm_client):
        """Test retry logic on timeout errors."""
        mock_response = create_mock_completion("success")

        with patch.object(llm_client.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = [
                APITimeoutError(request=MagicMock()),
                mock_response,
            ]

            result = await llm_client.chat([{"role": "user", "content": "hi"}])
            assert result.choices[0].message.content == "success"
            assert mock_create.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_exhausted(self, llm_client):
        """Test that exception is raised after all retries exhausted."""
        with patch.object(llm_client.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = APIError(
                message="Server error", request=MagicMock(), body=None
            )

            with pytest.raises(APIError):
                await llm_client.chat([{"role": "user", "content": "hi"}])

            assert mock_create.call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_client_error(self, llm_client):
        """Test that client errors are not retried when configured."""
        with patch.object(llm_client.client.chat.completions, "create", new_callable=AsyncMock) as mock_create:
            mock_create.side_effect = ValueError("Invalid parameter")

            with pytest.raises(ValueError):
                await llm_client.chat([{"role": "user", "content": "hi"}])

            assert mock_create.call_count == 1

    @pytest.mark.asyncio
    async def test_health_check_success(self, llm_client):
        """Test health check when LLM is available."""
        mock_response = create_mock_completion("pong")

        with patch.object(llm_client, "chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.return_value = mock_response
            result = await llm_client.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, llm_client):
        """Test health check when LLM is unavailable."""
        with patch.object(llm_client, "chat", new_callable=AsyncMock) as mock_chat:
            mock_chat.side_effect = Exception("Connection failed")
            result = await llm_client.health_check()
            assert result is False


class TestPrompts:
    """Tests for prompt utilities."""

    def test_detect_scene_order(self):
        """Test scene detection for order inquiries."""
        assert detect_scene("帮我查一下订单") == "order_inquiry"
        assert detect_scene("我的快递到哪了") == "order_inquiry"
        assert detect_scene("物流信息查询") == "order_inquiry"

    def test_detect_scene_return(self):
        """Test scene detection for return requests."""
        assert detect_scene("我想退货") == "return_request"
        assert detect_scene("可以换货吗") == "return_request"
        assert detect_scene("退款多久到账") == "return_request"

    def test_detect_scene_faq(self):
        """Test scene detection for FAQ questions."""
        assert detect_scene("怎么修改地址") == "faq_question"
        assert detect_scene("如何开发票") == "faq_question"

    def test_detect_scene_complaint(self):
        """Test scene detection for complaints."""
        assert detect_scene("我要投诉") == "complaint"
        assert detect_scene("太垃圾了") == "complaint"

    def test_detect_scene_none(self):
        """Test scene detection returns None for generic messages."""
        assert detect_scene("你好") is None
        assert detect_scene("谢谢") is None

    def test_build_messages_basic(self):
        """Test basic message building."""
        history = []
        messages = build_messages(SYSTEM_PROMPT, history, "你好")

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "你好"

    def test_build_messages_with_history(self):
        """Test message building with history."""
        history = [
            Message(role=MessageRole.USER, content="hi"),
            Message(role=MessageRole.ASSISTANT, content="hello"),
        ]
        messages = build_messages(SYSTEM_PROMPT, history, "你好")

        assert len(messages) == 4
        assert messages[1]["role"] == "user"
        assert messages[2]["role"] == "assistant"

    def test_build_messages_with_scene(self):
        """Test message building adds scene context."""
        messages = build_messages(SYSTEM_PROMPT, [], "帮我查一下订单")

        assert len(messages) == 3
        assert "场景提示" in messages[1]["content"]

    def test_build_messages_history_limit(self):
        """Test that history is limited to last 5 messages."""
        history = [
            Message(role=MessageRole.USER, content=f"msg{i}")
            for i in range(10)
        ]
        messages = build_messages(SYSTEM_PROMPT, history, "你好")

        assert len(messages) == 7

    def test_system_prompt_is_readable_chinese(self):
        """Test the system prompt contains readable guidance."""
        assert "你是「灵犀」智能客服" in SYSTEM_PROMPT
        assert "始终使用中文回复" in SYSTEM_PROMPT
