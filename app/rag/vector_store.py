"""Vector store for RAG using embeddings."""

import json
import numpy as np
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from app.rag.text_splitter import TextChunk
from app.utils.logger import logger


@dataclass
class SearchResult:
    """Search result with similarity score."""
    chunk: TextChunk
    score: float


class VectorStore:
    """Simple vector store using numpy for similarity search.

    Features:
    - Cosine similarity search
    - Persistent storage to disk
    - Support for any embedding model
    """

    def __init__(self, dimension: int = 1536):
        self.dimension = dimension
        self.vectors: list[np.ndarray] = []
        self.chunks: list[TextChunk] = []
        self._index_built = False

    def add_vectors(self, vectors: list[np.ndarray], chunks: list[TextChunk]) -> None:
        """Add vectors and corresponding chunks to store."""
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
        """Search for similar vectors using cosine similarity."""
        if not self.vectors:
            return []

        if len(query_vector) != self.dimension:
            raise ValueError(f"Query vector dimension {len(query_vector)} doesn't match {self.dimension}")

        # Calculate cosine similarity
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

        # Get top-k indices
        similarities = np.array(similarities)
        top_k = min(top_k, len(similarities))
        top_indices = np.argsort(similarities)[-top_k:][::-1]

        results = []
        for idx in top_indices:
            if similarities[idx] > 0:  # Only return positive similarities
                results.append(SearchResult(
                    chunk=self.chunks[idx],
                    score=float(similarities[idx]),
                ))

        return results

    def save(self, directory: str) -> None:
        """Save vectors and chunks to disk."""
        save_dir = Path(directory)
        save_dir.mkdir(parents=True, exist_ok=True)

        # Save vectors
        vectors_array = np.array(self.vectors)
        np.save(save_dir / "vectors.npy", vectors_array)

        # Save chunks
        chunks_data = []
        for chunk in self.chunks:
            chunks_data.append({
                "content": chunk.content,
                "metadata": chunk.metadata,
                "index": chunk.index,
            })
        with open(save_dir / "chunks.json", "w", encoding="utf-8") as f:
            json.dump(chunks_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Saved {len(self.vectors)} vectors to {directory}")

    def load(self, directory: str) -> bool:
        """Load vectors and chunks from disk."""
        save_dir = Path(directory)

        vectors_path = save_dir / "vectors.npy"
        chunks_path = save_dir / "chunks.json"

        if not vectors_path.exists() or not chunks_path.exists():
            return False

        try:
            # Load vectors
            vectors_array = np.load(vectors_path)
            self.vectors = [vectors_array[i] for i in range(len(vectors_array))]
            self.dimension = vectors_array.shape[1]

            # Load chunks
            with open(chunks_path, "r", encoding="utf-8") as f:
                chunks_data = json.load(f)

            self.chunks = [
                TextChunk(
                    content=cd["content"],
                    metadata=cd["metadata"],
                    index=cd["index"],
                )
                for cd in chunks_data
            ]

            logger.info(f"Loaded {len(self.vectors)} vectors from {directory}")
            return True
        except Exception as e:
            logger.error(f"Failed to load vectors: {e}")
            return False

    def clear(self) -> None:
        """Clear all vectors and chunks."""
        self.vectors.clear()
        self.chunks.clear()
        self._index_built = False

    @property
    def size(self) -> int:
        """Get number of vectors in store."""
        return len(self.vectors)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))
