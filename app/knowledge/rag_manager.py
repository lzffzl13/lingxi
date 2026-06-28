"""RAG-based knowledge manager for enhanced FAQ search."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Iterable
from typing import Optional

from app.cache import EmbeddingCache
from app.config import Settings
from app.db import database
from app.db.repositories import FAQRepository
from app.knowledge.manager import KnowledgeManager
from app.monitoring import track_rag_search, update_rag_documents
from app.rag import RAGPipeline
from app.rag.embeddings import CachedEmbeddingProvider, LocalEmbedding, OpenAIEmbedding
from app.rag.vector_store import InMemoryVectorStore
from app.session.redis_client import get_redis
from app.utils.logger import logger


class RAGKnowledgeManager:
    """Knowledge manager with RAG support."""

    def __init__(self, config: Settings):
        self.config = config
        self._rag_pipeline: Optional[RAGPipeline] = None
        self._initialized = False
        self._keyword_manager = KnowledgeManager(config)
        self._refresh_lock = asyncio.Lock()

    async def initialize(self) -> None:
        if self._initialized:
            return

        try:
            embedding_provider = self._create_embedding_func()
            await self._initialize_pipeline(embedding_provider)
        except Exception as exc:
            logger.warning(f"Primary embedding provider failed, retrying with local embeddings: {exc}")
            try:
                embedding_provider = self._create_local_embedding_func()
                await self._initialize_pipeline(embedding_provider)
            except Exception as fallback_exc:
                logger.error(f"Failed to initialize RAG: {fallback_exc}")
                self._initialized = False

    async def _initialize_pipeline(self, embedding_provider) -> None:
        vector_dimension = getattr(embedding_provider, "dimension", self.config.EMBEDDING_DIMENSION)
        vector_store = self._create_vector_store(vector_dimension)

        self._rag_pipeline = RAGPipeline(
            embedding_func=embedding_provider,
            chunk_size=500,
            chunk_overlap=50,
            vector_dimension=vector_dimension,
            persist_directory=self.config.VECTOR_PERSIST_DIRECTORY,
            vector_store=vector_store,
        )

        await self._load_faq_data()
        self._initialized = True
        logger.info("RAG Knowledge Manager initialized successfully")

    def _create_embedding_func(self):
        api_key = self.config.EMBEDDING_API_KEY.get_secret_value()
        base_url = self.config.EMBEDDING_BASE_URL
        if api_key == "not-set":
            api_key = self.config.LLM_API_KEY.get_secret_value()
            base_url = self.config.LLM_BASE_URL

        provider = None
        if api_key and api_key != "not-set":
            provider = OpenAIEmbedding(
                api_key=api_key,
                model=self.config.EMBEDDING_MODEL,
                base_url=base_url,
                dimension=self.config.EMBEDDING_DIMENSION,
            )
        else:
            try:
                provider = LocalEmbedding(model_name=self.config.EMBEDDING_LOCAL_MODEL)
            except ImportError:
                logger.warning("No embedding model available, RAG disabled")
                return None

        if not self.config.EMBEDDING_CACHE_ENABLED:
            return provider

        return CachedEmbeddingProvider(
            provider=provider,
            cache=EmbeddingCache(
                redis_client=get_redis(),
                ttl_seconds=self.config.EMBEDDING_CACHE_TTL_SECONDS,
            ),
        )

    def _create_local_embedding_func(self):
        provider = LocalEmbedding(model_name=self.config.EMBEDDING_LOCAL_MODEL)
        if not self.config.EMBEDDING_CACHE_ENABLED:
            return provider

        return CachedEmbeddingProvider(
            provider=provider,
            cache=EmbeddingCache(
                redis_client=get_redis(),
                ttl_seconds=self.config.EMBEDDING_CACHE_TTL_SECONDS,
            ),
        )

    def _create_vector_store(self, vector_dimension: int):
        backend = self.config.VECTOR_BACKEND.lower()

        if backend == "memory":
            return InMemoryVectorStore(dimension=vector_dimension)

        if backend == "qdrant":
            from app.rag.qdrant_store import QdrantVectorStore

            api_key = self.config.QDRANT_API_KEY.get_secret_value()
            return QdrantVectorStore(
                dimension=vector_dimension,
                url=self.config.QDRANT_URL,
                collection_name=self.config.QDRANT_COLLECTION,
                api_key=None if api_key == "not-set" else api_key,
            )

        raise ValueError(f"Unsupported vector backend: {self.config.VECTOR_BACKEND}")

    async def _load_faq_data(self, skip_existing: bool = True) -> None:
        if not self._rag_pipeline:
            return

        vector_store_size = getattr(self._rag_pipeline.vector_store, "size", 0)
        if skip_existing and isinstance(vector_store_size, int) and vector_store_size > 0:
            logger.info("Vector store already contains data, skipping FAQ reload")
            return

        faq_list = await self._load_faq_source()
        chunks_added = await self._rag_pipeline.add_faq_data(faq_list)
        update_rag_documents(self._rag_pipeline.vector_store.size)
        logger.info(f"Loaded {chunks_added} FAQ chunks into RAG pipeline")

    async def _load_faq_source(self) -> list[dict]:
        """Load FAQ source records from database first, then bundled defaults."""
        if database.async_session_factory:
            try:
                async with database.async_session_factory() as session:
                    repo = FAQRepository(session)
                    db_faqs = await repo.get_all(active_only=True)
                    if db_faqs:
                        return [
                            {
                                "id": str(faq.id),
                                "question": faq.question,
                                "answer": faq.answer,
                                "category": faq.category or "general",
                            }
                            for faq in db_faqs
                        ]
            except Exception as exc:
                logger.warning(f"Failed to load FAQ data from database, using bundled defaults: {exc}")

        from app.knowledge.manager import FAQ_DATABASE

        faq_list = []
        for faq in FAQ_DATABASE:
            faq_list.append(
                {
                    "id": faq.get("question", ""),
                    "question": faq["question"],
                    "answer": faq["answer"],
                    "category": faq.get("category", "general"),
                }
            )
        return faq_list

    async def search(self, query: str, top_k: int = 3) -> list[dict]:
        start_time = time.monotonic()
        rag_results: list[dict] = []
        rag_failed = False

        if self._initialized and self._rag_pipeline:
            try:
                results = await self._rag_pipeline.search(query, top_k=top_k)
                rag_results = self._format_rag_results(results)
            except Exception as exc:
                rag_failed = True
                logger.warning(f"RAG search failed, falling back to keyword: {exc}")

        keyword_results = await self._keyword_manager.search(query, top_k=top_k)
        for result in keyword_results:
            result["source"] = "keyword"
            result["match_reason"] = "keyword_match"

        results = self._merge_results(rag_results, keyword_results, top_k)
        source = self._derive_result_source(results)
        status = "fallback" if rag_failed else "success"
        track_rag_search(time.monotonic() - start_time, status=status, source=source)
        return results

    async def add_document(self, content: str, metadata: Optional[dict] = None) -> int:
        if not self._initialized or not self._rag_pipeline:
            logger.warning("RAG pipeline not initialized")
            return 0

        document = {
            "content": content,
            "metadata": metadata or {},
        }
        return await self._rag_pipeline.add_documents([document])

    def get_stats(self) -> dict:
        if not self._rag_pipeline:
            return {"initialized": False}

        stats = self._rag_pipeline.get_stats()
        stats["initialized"] = self._initialized
        return stats

    def clear_cache(self) -> None:
        if self._rag_pipeline:
            self._rag_pipeline.vector_store.clear()
            update_rag_documents(self._rag_pipeline.vector_store.size)
        self._keyword_manager.clear_cache()
        logger.info("RAG vector store cleared")

    async def refresh_index(self) -> int:
        """Rebuild the vector index from the current FAQ source."""
        if not self._initialized or not self._rag_pipeline:
            logger.warning("RAG pipeline not initialized, cannot refresh index")
            return 0

        async with self._refresh_lock:
            self._rag_pipeline.vector_store.clear()
            self._keyword_manager.clear_cache()
            await self._load_faq_data(skip_existing=False)
            count = self._rag_pipeline.vector_store.size
            update_rag_documents(count)
            logger.info(f"RAG vector index refreshed with {count} chunks")
            return count

    def _format_rag_results(self, results: Iterable) -> list[dict]:
        formatted_results = []
        for result in results:
            if result.score < self.config.RAG_SCORE_THRESHOLD:
                continue

            formatted_results.append(
                {
                    "question": result.chunk.metadata.get("question", ""),
                    "answer": result.chunk.metadata.get("answer", result.chunk.content),
                    "category": result.chunk.metadata.get("category", "general"),
                    "score": result.score,
                    "source": "rag",
                    "match_reason": f"semantic_similarity:{result.score:.3f}",
                }
            )

        return formatted_results

    def _merge_results(self, rag_results: list[dict], keyword_results: list[dict], top_k: int) -> list[dict]:
        merged: dict[tuple[str, str], dict] = {}

        for result in rag_results:
            key = (result["question"], result["answer"])
            merged[key] = {**result, "score": result["score"] * self.config.HYBRID_RAG_WEIGHT}

        for result in keyword_results:
            key = (result["question"], result["answer"])
            weighted_score = result["score"] * self.config.HYBRID_KEYWORD_WEIGHT
            if key in merged:
                merged_result = merged[key]
                merged_result["score"] += weighted_score
                merged_result["source"] = "hybrid"
                merged_result["match_reason"] = "semantic_similarity+keyword_match"
                continue

            merged[key] = {**result, "score": weighted_score}

        return sorted(merged.values(), key=lambda item: item["score"], reverse=True)[:top_k]

    def _derive_result_source(self, results: list[dict]) -> str:
        if not results:
            return "none"
        sources = {result.get("source", "unknown") for result in results}
        if "hybrid" in sources or len(sources) > 1:
            return "hybrid"
        return next(iter(sources))
