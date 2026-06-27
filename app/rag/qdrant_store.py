"""Qdrant-backed vector store."""

from __future__ import annotations

import uuid

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models

from app.rag.text_splitter import TextChunk
from app.rag.vector_store import BaseVectorStore, SearchResult
from app.utils.logger import logger


class QdrantVectorStore(BaseVectorStore):
    """Vector store implementation backed by Qdrant."""

    def __init__(
        self,
        dimension: int,
        url: str,
        collection_name: str,
        api_key: str | None = None,
    ):
        super().__init__(dimension=dimension)
        self.collection_name = collection_name
        self.client = QdrantClient(
            url=url,
            api_key=api_key or None,
            check_compatibility=False,
        )
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if self.client.collection_exists(self.collection_name):
            collection = self.client.get_collection(self.collection_name)
            current_size = collection.config.params.vectors.size
            if current_size == self.dimension:
                return

            logger.warning(
                f"Recreating Qdrant collection {self.collection_name} due to dimension change "
                f"({current_size} -> {self.dimension})"
            )
            self.client.delete_collection(self.collection_name)
        else:
            current_size = None

        if current_size == self.dimension:
            return

        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=self.dimension,
                distance=models.Distance.COSINE,
            ),
        )
        logger.info(f"Created Qdrant collection: {self.collection_name}")

    def add_vectors(self, vectors: list[np.ndarray], chunks: list[TextChunk]) -> None:
        if len(vectors) != len(chunks):
            raise ValueError("Vectors and chunks must have same length")

        points = []
        for vector, chunk in zip(vectors, chunks):
            if len(vector) != self.dimension:
                raise ValueError(f"Vector dimension {len(vector)} doesn't match expected {self.dimension}")

            payload = {
                "content": chunk.content,
                "metadata": chunk.metadata,
                "index": chunk.index,
            }
            points.append(
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=np.array(vector, dtype=np.float32).tolist(),
                    payload=payload,
                )
            )

        if not points:
            return

        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

    def search(self, query_vector: np.ndarray, top_k: int = 5) -> list[SearchResult]:
        if len(query_vector) != self.dimension:
            raise ValueError(f"Query vector dimension {len(query_vector)} doesn't match {self.dimension}")

        if np.linalg.norm(query_vector) == 0:
            return []

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=np.array(query_vector, dtype=np.float32).tolist(),
            limit=top_k,
            with_payload=True,
        )

        results = []
        for point in response.points:
            payload = point.payload or {}
            score = float(point.score or 0.0)
            if score <= 0:
                continue

            results.append(
                SearchResult(
                    chunk=TextChunk(
                        content=payload.get("content", ""),
                        metadata=payload.get("metadata", {}),
                        index=payload.get("index", 0),
                    ),
                    score=score,
                )
            )

        return results

    def clear(self) -> None:
        self.client.delete_collection(self.collection_name)
        self._ensure_collection()

    @property
    def size(self) -> int:
        info = self.client.get_collection(self.collection_name)
        return int(info.points_count or 0)
