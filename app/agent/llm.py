import asyncio
from collections.abc import AsyncGenerator

from openai import AsyncOpenAI, APIError, APITimeoutError, RateLimitError
from openai.types.chat import ChatCompletion, ChatCompletionChunk

from app.config import Settings
from app.utils.logger import logger
from app.monitoring import track_llm_call


class LLMClient:
    """Async LLM client compatible with OpenAI API.

    Features:
    - Automatic retry with exponential backoff
    - Configurable timeout
    - Streaming support
    """

    def __init__(self, config: Settings):
        self.max_retries = config.LLM_MAX_RETRIES
        self.retry_delay = config.LLM_RETRY_DELAY
        self.client = AsyncOpenAI(
            api_key=config.LLM_API_KEY.get_secret_value(),
            base_url=config.LLM_BASE_URL,
            timeout=config.LLM_REQUEST_TIMEOUT,
        )
        self.model = config.LLM_MODEL
        self.temperature = config.LLM_TEMPERATURE
        self.max_tokens = config.LLM_MAX_TOKENS

    def _build_kwargs(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> dict:
        """Build common kwargs for chat completion."""
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": stream,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return kwargs

    async def _retry_with_backoff(self, coro_func, *args, **kwargs):
        """Execute async function with retry and exponential backoff.

        Retries on:
        - APIError (server errors)
        - APITimeoutError
        - RateLimitError (429)
        """
        last_exception = None

        for attempt in range(self.max_retries):
            try:
                return await coro_func(*args, **kwargs)
            except (APIError, APITimeoutError, RateLimitError) as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    # Always retry on these errors
                    if isinstance(e, (RateLimitError, APITimeoutError, APIError)):
                        delay = self.retry_delay * (2 ** attempt)
                        logger.warning(
                            f"LLM request failed (attempt {attempt + 1}/{self.max_retries}), "
                            f"retrying in {delay}s: {type(e).__name__}: {e}"
                        )
                        await asyncio.sleep(delay)
                        continue
                raise
            except Exception:
                raise

        raise last_exception  # type: ignore[misc]

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> ChatCompletion:
        """Call LLM with messages and optional tools.

        Includes retry logic for transient failures.
        """
        import time
        kwargs = self._build_kwargs(messages, tools, stream=False)
        start_time = time.time()
        try:
            result = await self._retry_with_backoff(
                self.client.chat.completions.create, **kwargs
            )
            duration = time.time() - start_time
            # Track successful LLM call
            usage = getattr(result, 'usage', None)
            track_llm_call(
                model=self.model,
                duration=duration,
                status='success',
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
            )
            return result
        except Exception as e:
            duration = time.time() - start_time
            track_llm_call(
                model=self.model,
                duration=duration,
                status='error',
            )
            raise

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncGenerator[ChatCompletionChunk, None]:
        """Call LLM with streaming response.

        Note: Streaming requests are not retried mid-stream.
        """
        kwargs = self._build_kwargs(messages, tools, stream=True)
        stream = await self._retry_with_backoff(
            self.client.chat.completions.create, **kwargs
        )
        async for chunk in stream:
            yield chunk

    async def health_check(self) -> bool:
        """Test LLM connectivity."""
        try:
            await self.chat([{"role": "user", "content": "ping"}])
            return True
        except Exception:
            return False
