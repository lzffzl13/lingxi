"""RAG Pipeline - main entry point for retrieval augmented generation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Optional

import numpy as np

from app.rag.document_loader import DocumentLoader
from app.rag.text_splitter import TextChunk, TextSplitter
from app.rag.vector_store import BaseVectorStore, InMemoryVectorStore, SearchResult
from app.utils.logger import logger


class RAGPipeline:
    """RAG Pipeline for document retrieval and augmentation."""

    def __init__(
        self,
        embedding_func: Optional[Callable] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        vector_dimension: int = 1536,
        persist_directory: Optional[str] = None,
        vector_store: Optional[BaseVectorStore] = None,
    ):
        self.embedding_func = embedding_func
        self.text_splitter = TextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        self.vector_store = vector_store or InMemoryVectorStore(dimension=vector_dimension)
        self.persist_directory = persist_directory

        if persist_directory and isinstance(self.vector_store, InMemoryVectorStore):
            self.vector_store.load(persist_directory)

    async def add_documents(self, documents: list[dict]) -> int:
        chunks = self.text_splitter.split_documents(documents)
        if not chunks:
            return 0

        if self.embedding_func:
            embeddings = await self._generate_embeddings(chunks)
            self.vector_store.add_vectors(embeddings, chunks)
        else:
            logger.warning("No embedding function provided, storing chunks without vectors")

        if self.persist_directory and isinstance(self.vector_store, InMemoryVectorStore):
            self.vector_store.save(self.persist_directory)

        return len(chunks)

    async def add_faq_data(self, faq_list: list[dict]) -> int:
        documents = DocumentLoader.load_faq_data(faq_list)
        return await self.add_documents(documents)

    async def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        if not self.embedding_func:
            logger.warning("No embedding function provided, cannot search")
            return []

        query_embedding = await self._generate_query_embedding(query)
        return self.vector_store.search(query_embedding, top_k=top_k)

    async def get_context(self, query: str, top_k: int = 3) -> str:
        results = await self.search(query, top_k=top_k)
        if not results:
            return ""

        context_parts = []
        for index, result in enumerate(results, 1):
            context_parts.append(f"[Reference {index}] (similarity {result.score:.2f})\n{result.chunk.content}")

        return "\n\n".join(context_parts)

    async def _generate_embeddings(self, chunks: list[TextChunk]) -> list[np.ndarray]:
        if not self.embedding_func:
            return []

        texts = [chunk.content for chunk in chunks]
        embeddings = await self.embedding_func(texts)
        return [np.array(embedding, dtype=np.float32) for embedding in embeddings]

    async def _generate_query_embedding(self, query: str) -> np.ndarray:
        if not self.embedding_func:
            return np.zeros(self.vector_store.dimension, dtype=np.float32)

        embeddings = await self.embedding_func([query])
        return np.array(embeddings[0], dtype=np.float32)

    def get_stats(self) -> dict:
        return {
            "total_chunks": self.vector_store.size,
            "chunk_size": self.text_splitter.chunk_size,
            "chunk_overlap": self.text_splitter.chunk_overlap,
            "vector_dimension": self.vector_store.dimension,
            "has_embedding_func": self.embedding_func is not None,
            "persist_directory": self.persist_directory,
            "vector_backend": self.vector_store.__class__.__name__,
        }
