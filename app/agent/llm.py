from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion

from app.config import Settings


class LLMClient:
    """Async LLM client compatible with OpenAI API."""

    def __init__(self, config: Settings):
        self.client = AsyncOpenAI(
            api_key=config.LLM_API_KEY.get_secret_value(),
            base_url=config.LLM_BASE_URL,
        )
        self.model = config.LLM_MODEL
        self.temperature = config.LLM_TEMPERATURE
        self.max_tokens = config.LLM_MAX_TOKENS

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> ChatCompletion:
        """Call LLM with messages and optional tools."""
        kwargs: dict = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return await self.client.chat.completions.create(**kwargs)

    async def health_check(self) -> bool:
        """Test LLM connectivity."""
        try:
            await self.chat([{"role": "user", "content": "ping"}])
            return True
        except Exception:
            return False
