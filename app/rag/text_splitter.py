"""Text splitting utilities for RAG."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TextChunk:
    """A chunk of text with metadata."""
    content: str
    metadata: dict
    index: int


class TextSplitter:
    """Split text into chunks for processing.

    Supports:
    - Recursive character splitting
    - Overlap between chunks
    - Custom separators
    """

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
        separators: Optional[list[str]] = None,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.separators = separators or ["\n\n", "\n", "。", "！", "？", ".", "!", "?", " ", ""]

    def split_text(self, text: str, metadata: Optional[dict] = None) -> list[TextChunk]:
        """Split text into chunks."""
        if not text:
            return []

        metadata = metadata or {}
        chunks = []
        current_chunks = self._recursive_split(text, self.separators)

        for i, chunk_text in enumerate(current_chunks):
            if chunk_text.strip():
                chunks.append(TextChunk(
                    content=chunk_text.strip(),
                    metadata={**metadata, "chunk_index": i},
                    index=i,
                ))

        return chunks

    def _recursive_split(self, text: str, separators: list[str]) -> list[str]:
        """Recursively split text using separators."""
        if len(text) <= self.chunk_size:
            return [text]

        # Find the best separator
        separator = self._find_best_separator(text, separators)
        if not separator:
            # No separator found, split by character count
            return self._split_by_size(text)

        # Split by separator
        splits = text.split(separator)
        chunks = []
        current_chunk = ""

        for split in splits:
            if len(current_chunk) + len(split) + len(separator) <= self.chunk_size:
                current_chunk += split + separator
            else:
                if current_chunk:
                    chunks.append(current_chunk.rstrip(separator))
                current_chunk = split + separator

        if current_chunk:
            chunks.append(current_chunk.rstrip(separator))

        # Apply overlap
        if self.chunk_overlap > 0:
            chunks = self._apply_overlap(chunks)

        return chunks

    def _find_best_separator(self, text: str, separators: list[str]) -> Optional[str]:
        """Find the best separator for splitting."""
        for sep in separators:
            if sep in text:
                return sep
        return None

    def _split_by_size(self, text: str) -> list[str]:
        """Split text by character count with overlap."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + self.chunk_size
            chunks.append(text[start:end])
            start = end - self.chunk_overlap
        return chunks

    def _apply_overlap(self, chunks: list[str]) -> list[str]:
        """Apply overlap between chunks."""
        if len(chunks) <= 1:
            return chunks

        result = [chunks[0]]
        for i in range(1, len(chunks)):
            # Add overlap from previous chunk
            prev_chunk = chunks[i - 1]
            overlap_text = prev_chunk[-self.chunk_overlap:] if len(prev_chunk) > self.chunk_overlap else prev_chunk
            result.append(overlap_text + chunks[i])

        return result

    def split_documents(self, documents: list[dict]) -> list[TextChunk]:
        """Split multiple documents into chunks.

        Args:
            documents: List of dicts with 'content' and 'metadata' keys
        """
        all_chunks = []
        for doc in documents:
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            chunks = self.split_text(content, metadata)
            all_chunks.extend(chunks)
        return all_chunks
