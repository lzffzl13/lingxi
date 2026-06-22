"""RAG-based knowledge manager for enhanced FAQ search."""

from typing import Optional

from app.config import Settings
from app.rag import RAGPipeline, DocumentLoader
from app.rag.rag_pipeline import OpenAIEmbedding, LocalEmbedding
from app.utils.logger import logger


class RAGKnowledgeManager:
    """Knowledge manager with RAG support.

    Features:
    - Semantic search using embeddings
    - Fallback to keyword search
    - Automatic FAQ indexing
    - Configurable embedding model
    """

    def __init__(self, config: Settings):
        self.config = config
        self._rag_pipeline: Optional[RAGPipeline] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the RAG pipeline."""
        if self._initialized:
            return

        try:
            # Choose embedding function based on config
            embedding_func = self._create_embedding_func()

            # Create RAG pipeline
            self._rag_pipeline = RAGPipeline(
                embedding_func=embedding_func,
                chunk_size=500,
                chunk_overlap=50,
                vector_dimension=1536,
                persist_directory="./data/rag_vectors",
            )

            # Load FAQ data
            await self._load_faq_data()

            self._initialized = True
            logger.info("RAG Knowledge Manager initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize RAG: {e}")
            # Fallback to no RAG
            self._initialized = False

    def _create_embedding_func(self):
        """Create embedding function based on configuration."""
        # Try to use OpenAI embedding if API key is available
        api_key = self.config.LLM_API_KEY.get_secret_value()
        if api_key and api_key != "not-set":
            return OpenAIEmbedding(api_key=api_key)

        # Fallback to local embedding
        try:
            return LocalEmbedding(model_name="all-MiniLM-L6-v2")
        except ImportError:
            logger.warning("No embedding model available, RAG disabled")
            return None

    async def _load_faq_data(self) -> None:
        """Load FAQ data into RAG pipeline."""
        if not self._rag_pipeline:
            return

        # Import FAQ data from existing knowledge manager
        from app.knowledge.manager import FAQ_DATABASE

        # Convert to RAG format
        faq_list = []
        for faq in FAQ_DATABASE:
            faq_list.append({
                "id": faq.get("question", ""),
                "question": faq["question"],
                "answer": faq["answer"],
                "category": faq.get("category", "general"),
            })

        # Add to RAG pipeline
        chunks_added = await self._rag_pipeline.add_faq_data(faq_list)
        logger.info(f"Loaded {chunks_added} FAQ chunks into RAG pipeline")

    async def search(self, query: str, top_k: int = 3) -> list[dict]:
        """Search FAQ using RAG with fallback to keyword matching.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of matching FAQ entries with scores
        """
        # Try RAG search first
        if self._initialized and self._rag_pipeline:
            try:
                results = await self._rag_pipeline.search(query, top_k=top_k)
                if results:
                    return [
                        {
                            "question": result.chunk.metadata.get("question", ""),
                            "answer": result.chunk.content.split("答案：")[-1] if "答案：" in result.chunk.content else result.chunk.content,
                            "category": result.chunk.metadata.get("category", "general"),
                            "score": result.score,
                            "source": "rag",
                        }
                        for result in results
                    ]
            except Exception as e:
                logger.warning(f"RAG search failed, falling back to keyword: {e}")

        # Fallback to keyword search
        from app.knowledge.manager import KnowledgeManager
        fallback_manager = KnowledgeManager(self.config)
        results = await fallback_manager.search(query, top_k=top_k)

        # Add source tag
        for result in results:
            result["source"] = "keyword"

        return results

    async def add_document(self, content: str, metadata: Optional[dict] = None) -> int:
        """Add a document to the RAG pipeline.

        Args:
            content: Document content
            metadata: Optional metadata

        Returns:
            Number of chunks added
        """
        if not self._initialized or not self._rag_pipeline:
            logger.warning("RAG pipeline not initialized")
            return 0

        document = {
            "content": content,
            "metadata": metadata or {},
        }

        return await self._rag_pipeline.add_documents([document])

    def get_stats(self) -> dict:
        """Get RAG pipeline statistics."""
        if not self._rag_pipeline:
            return {"initialized": False}

        stats = self._rag_pipeline.get_stats()
        stats["initialized"] = self._initialized
        return stats

    def clear_cache(self) -> None:
        """Clear all caches."""
        if self._rag_pipeline:
            self._rag_pipeline.vector_store.clear()
            logger.info("RAG vector store cleared")
