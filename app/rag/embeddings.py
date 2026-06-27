"""Embedding providers for RAG."""

from __future__ import annotations

from typing import Optional, Protocol

from openai import AsyncOpenAI

from app.cache import EmbeddingCache


class EmbeddingProvider(Protocol):
    model: str
    dimension: int

    async def __call__(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for the given texts."""


class OpenAIEmbedding:
    """Embedding provider using an OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        base_url: str = "https://api.openai.com/v1",
        dimension: int = 1536,
    ):
        self.api_key = api_key
        self.model = model
        self.dimension = dimension
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=30.0,
        )

    async def __call__(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(
            model=self.model,
            input=texts,
        )
        return [item.embedding for item in response.data]


class LocalEmbedding:
    """Local embedding provider using sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2", dimension: int = 384):
        self.model = model_name
        self.dimension = dimension
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model)

    async def __call__(self, texts: list[str]) -> list[list[float]]:
        self._load_model()
        embeddings = self._model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()


class CachedEmbeddingProvider:
    """Embedding provider wrapper with Redis caching."""

    def __init__(self, provider: EmbeddingProvider, cache: Optional[EmbeddingCache] = None):
        self.provider = provider
        self.cache = cache
        self.model = provider.model
        self.dimension = provider.dimension

    async def __call__(self, texts: list[str]) -> list[list[float]]:
        if self.cache is None or not texts:
            return await self.provider(texts)

        cached_results: list[Optional[list[float]]] = [None] * len(texts)
        missing_indexes: list[int] = []
        missing_texts: list[str] = []

        for index, text in enumerate(texts):
            cached = await self.cache.get(self.model, text)
            if cached is None:
                missing_indexes.append(index)
                missing_texts.append(text)
            else:
                cached_results[index] = cached

        if missing_texts:
            generated = await self.provider(missing_texts)
            for index, text, embedding in zip(missing_indexes, missing_texts, generated):
                cached_results[index] = embedding
                await self.cache.set(self.model, text, embedding, self.dimension)

        return [embedding or [] for embedding in cached_results]
