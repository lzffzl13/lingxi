"""RAG Pipeline - main entry point for retrieval augmented generation."""

from typing import Optional, Callable
import numpy as np

from app.rag.text_splitter import TextSplitter, TextChunk
from app.rag.vector_store import VectorStore, SearchResult
from app.rag.document_loader import DocumentLoader
from app.utils.logger import logger


class RAGPipeline:
    """RAG Pipeline for document retrieval and augmentation.

    Features:
    - Document loading and chunking
    - Vector embedding and storage
    - Semantic search
    - Context augmentation for LLM
    """

    def __init__(
        self,
        embedding_func: Optional[Callable] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        vector_dimension: int = 1536,
        persist_directory: Optional[str] = None,
    ):
        self.embedding_func = embedding_func
        self.text_splitter = TextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        self.vector_store = VectorStore(dimension=vector_dimension)
        self.persist_directory = persist_directory

        # Load existing vectors if available
        if persist_directory:
            self.vector_store.load(persist_directory)

    async def add_documents(self, documents: list[dict]) -> int:
        """Add documents to the RAG pipeline.

        Args:
            documents: List of dicts with 'content' and 'metadata' keys

        Returns:
            Number of chunks added
        """
        # Split documents into chunks
        chunks = self.text_splitter.split_documents(documents)

        if not chunks:
            return 0

        # Generate embeddings
        if self.embedding_func:
            embeddings = await self._generate_embeddings(chunks)
            self.vector_store.add_vectors(embeddings, chunks)
        else:
            logger.warning("No embedding function provided, storing chunks without vectors")

        # Persist if directory specified
        if self.persist_directory:
            self.vector_store.save(self.persist_directory)

        return len(chunks)

    async def add_faq_data(self, faq_list: list[dict]) -> int:
        """Add FAQ data to the pipeline."""
        documents = DocumentLoader.load_faq_data(faq_list)
        return await self.add_documents(documents)

    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """Search for relevant documents.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of search results with scores
        """
        if not self.embedding_func:
            logger.warning("No embedding function provided, cannot search")
            return []

        # Generate query embedding
        query_embedding = await self._generate_query_embedding(query)

        # Search vector store
        results = self.vector_store.search(query_embedding, top_k=top_k)

        return results

    async def get_context(self, query: str, top_k: int = 3) -> str:
        """Get relevant context for a query.

        Returns formatted context string for LLM prompt augmentation.
        """
        results = await self.search(query, top_k=top_k)

        if not results:
            return ""

        # Format context
        context_parts = []
        for i, result in enumerate(results, 1):
            context_parts.append(f"[参考文档 {i}] (相似度: {result.score:.2f})\n{result.chunk.content}")

        return "\n\n".join(context_parts)

    async def _generate_embeddings(self, chunks: list[TextChunk]) -> list[np.ndarray]:
        """Generate embeddings for chunks."""
        if not self.embedding_func:
            return []

        texts = [chunk.content for chunk in chunks]
        embeddings = await self.embedding_func(texts)
        return [np.array(emb, dtype=np.float32) for emb in embeddings]

    async def _generate_query_embedding(self, query: str) -> np.ndarray:
        """Generate embedding for query."""
        if not self.embedding_func:
            return np.zeros(self.vector_store.dimension, dtype=np.float32)

        embeddings = await self.embedding_func([query])
        return np.array(embeddings[0], dtype=np.float32)

    def get_stats(self) -> dict:
        """Get pipeline statistics."""
        return {
            "total_chunks": self.vector_store.size,
            "chunk_size": self.text_splitter.chunk_size,
            "chunk_overlap": self.text_splitter.chunk_overlap,
            "vector_dimension": self.vector_store.dimension,
            "has_embedding_func": self.embedding_func is not None,
            "persist_directory": self.persist_directory,
        }


class OpenAIEmbedding:
    """OpenAI embedding function."""

    def __init__(self, api_key: str, model: str = "text-embedding-ada-002"):
        self.api_key = api_key
        self.model = model

    async def __call__(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using OpenAI API."""
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "input": texts,
                },
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            # Extract embeddings
            embeddings = [item["embedding"] for item in data["data"]]
            return embeddings


class LocalEmbedding:
    """Local embedding function using sentence-transformers."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self.model = None

    def _load_model(self):
        """Lazy load the model."""
        if self.model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self.model = SentenceTransformer(self.model_name)
            except ImportError:
                raise ImportError("sentence-transformers not installed. Run: pip install sentence-transformers")

    async def __call__(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings using local model."""
        self._load_model()
        embeddings = self.model.encode(texts, show_progress_bar=False)
        return embeddings.tolist()
