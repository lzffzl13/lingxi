"""Vector store interfaces and in-memory implementation."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.rag.text_splitter import TextChunk
from app.utils.logger import logger


@dataclass
class SearchResult:
    """Search result with similarity score."""

    chunk: TextChunk
    score: float


class BaseVectorStore(ABC):
    """Common vector store contract."""

    def __init__(self, dimension: int):
        self.dimension = dimension

    @abstractmethod
    def add_vectors(self, vectors: list[np.ndarray], chunks: list[TextChunk]) -> None:
        """Store vectors and their chunks."""

    @abstractmethod
    def search(self, query_vector: np.ndarray, top_k: int = 5) -> list[SearchResult]:
        """Search the store for similar chunks."""

    def load(self, directory: str) -> bool:
        return False

    def save(self, directory: str) -> None:
        return None

    @abstractmethod
    def clear(self) -> None:
        """Clear all stored vectors."""

    @property
    @abstractmethod
    def size(self) -> int:
        """Get number of stored vectors."""


class InMemoryVectorStore(BaseVectorStore):
    """Simple vector store using numpy for similarity search."""

    def __init__(self, dimension: int = 1536):
        super().__init__(dimension=dimension)
        self.vectors: list[np.ndarray] = []
        self.chunks: list[TextChunk] = []
        self._index_built = False

    def add_vectors(self, vectors: list[np.ndarray], chunks: list[TextChunk]) -> None:
        if len(vectors) != len(chunks):
            raise ValueError("Vectors and chunks must have same length")

        for vec, chunk in zip(vectors, chunks):
            if len(vec) != self.dimension:
                raise ValueError(f"Vector dimension {len(vec)} doesn't match expected {self.dimension}")

            self.vectors.append(np.array(vec, dtype=np.float32))
            self.chunks.append(chunk)

        self._index_built = False
        logger.info(f"Added {len(vectors)} vectors to store. Total: {len(self.vectors)}")

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> list[SearchResult]:
        if not self.vectors:
            return []

        if len(query_vector) != self.dimension:
            raise ValueError(f"Query vector dimension {len(query_vector)} doesn't match {self.dimension}")

        query_norm = np.linalg.norm(query_vector)
        if query_norm == 0:
            return []

        similarities = []
        for vec in self.vectors:
            vec_norm = np.linalg.norm(vec)
            if vec_norm == 0:
                similarities.append(0.0)
            else:
                similarity = np.dot(query_vector, vec) / (query_norm * vec_norm)
                similarities.append(float(similarity))

        similarity_array = np.array(similarities)
        top_k = min(top_k, len(similarity_array))
        top_indices = np.argsort(similarity_array)[-top_k:][::-1]

        results = []
        for idx in top_indices:
            if similarity_array[idx] > 0:
                results.append(
                    SearchResult(
                        chunk=self.chunks[idx],
                        score=float(similarity_array[idx]),
                    )
                )

        return results

    def save(self, directory: str) -> None:
        save_dir = Path(directory)
        save_dir.mkdir(parents=True, exist_ok=True)

        vectors_array = np.array(self.vectors)
        np.save(save_dir / "vectors.npy", vectors_array)

        chunks_data = [
            {
                "content": chunk.content,
                "metadata": chunk.metadata,
                "index": chunk.index,
            }
            for chunk in self.chunks
        ]
        with open(save_dir / "chunks.json", "w", encoding="utf-8") as file:
            json.dump(chunks_data, file, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(self.vectors)} vectors to {directory}")

    def load(self, directory: str) -> bool:
        save_dir = Path(directory)
        vectors_path = save_dir / "vectors.npy"
        chunks_path = save_dir / "chunks.json"

        if not vectors_path.exists() or not chunks_path.exists():
            return False

        try:
            vectors_array = np.load(vectors_path)
            self.vectors = [vectors_array[i] for i in range(len(vectors_array))]
            self.dimension = vectors_array.shape[1]

            with open(chunks_path, "r", encoding="utf-8") as file:
                chunks_data = json.load(file)

            self.chunks = [
                TextChunk(
                    content=item["content"],
                    metadata=item["metadata"],
                    index=item["index"],
                )
                for item in chunks_data
            ]

            logger.info(f"Loaded {len(self.vectors)} vectors from {directory}")
            return True
        except Exception as exc:
            logger.error(f"Failed to load vectors: {exc}")
            return False

    def clear(self) -> None:
        self.vectors.clear()
        self.chunks.clear()
        self._index_built = False

    @property
    def size(self) -> int:
        return len(self.vectors)


VectorStore = InMemoryVectorStore


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors."""

    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
