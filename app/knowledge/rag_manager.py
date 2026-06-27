"""RAG-based knowledge manager for enhanced FAQ search."""

from __future__ import annotations

from typing import Optional

from app.cache import EmbeddingCache
from app.config import Settings
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

    async def _load_faq_data(self) -> None:
        if not self._rag_pipeline:
            return

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

        chunks_added = await self._rag_pipeline.add_faq_data(faq_list)
        logger.info(f"Loaded {chunks_added} FAQ chunks into RAG pipeline")

    async def search(self, query: str, top_k: int = 3) -> list[dict]:
        if self._initialized and self._rag_pipeline:
            try:
                results = await self._rag_pipeline.search(query, top_k=top_k)
                if results:
                    return [
                        {
                            "question": result.chunk.metadata.get("question", ""),
                            "answer": result.chunk.metadata.get("answer", result.chunk.content),
                            "category": result.chunk.metadata.get("category", "general"),
                            "score": result.score,
                            "source": "rag",
                        }
                        for result in results
                    ]
            except Exception as exc:
                logger.warning(f"RAG search failed, falling back to keyword: {exc}")

        from app.knowledge.manager import KnowledgeManager

        fallback_manager = KnowledgeManager(self.config)
        results = await fallback_manager.search(query, top_k=top_k)
        for result in results:
            result["source"] = "keyword"
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
            logger.info("RAG vector store cleared")
