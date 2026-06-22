"""RAG component tests."""

import json

import numpy as np
import pytest

from app.rag.document_loader import DocumentLoader
from app.rag.rag_pipeline import RAGPipeline
from app.rag.text_splitter import TextChunk, TextSplitter
from app.rag.vector_store import VectorStore, cosine_similarity


class TestTextSplitter:
    def test_split_text_returns_empty_for_empty_text(self):
        splitter = TextSplitter(chunk_size=10)

        assert splitter.split_text("") == []

    def test_split_text_preserves_metadata_and_chunk_indexes(self):
        splitter = TextSplitter(chunk_size=12, chunk_overlap=0, separators=[" "])

        chunks = splitter.split_text("alpha beta gamma delta", {"source": "doc"})

        assert [chunk.index for chunk in chunks] == list(range(len(chunks)))
        assert all(chunk.metadata["source"] == "doc" for chunk in chunks)
        assert all(chunk.metadata["chunk_index"] == chunk.index for chunk in chunks)
        assert all(chunk.content for chunk in chunks)

    def test_split_by_size_uses_overlap_when_no_separator_matches(self):
        splitter = TextSplitter(chunk_size=5, chunk_overlap=2, separators=["|"])

        chunks = splitter.split_text("abcdefghijk")

        assert [chunk.content for chunk in chunks] == ["abcde", "defgh", "ghijk", "jk"]

    def test_split_documents_combines_all_chunks(self):
        splitter = TextSplitter(chunk_size=50, chunk_overlap=0)
        documents = [
            {"content": "first document", "metadata": {"id": 1}},
            {"content": "", "metadata": {"id": 2}},
            {"content": "second document", "metadata": {"id": 3}},
        ]

        chunks = splitter.split_documents(documents)

        assert len(chunks) == 2
        assert [chunk.metadata["id"] for chunk in chunks] == [1, 3]


class TestVectorStore:
    def test_add_vectors_validates_lengths(self):
        store = VectorStore(dimension=2)

        with pytest.raises(ValueError, match="same length"):
            store.add_vectors([np.array([1, 0])], [])

    def test_add_vectors_validates_dimension(self):
        store = VectorStore(dimension=2)

        with pytest.raises(ValueError, match="dimension"):
            store.add_vectors([np.array([1, 0, 0])], [TextChunk("bad", {}, 0)])

    def test_search_returns_results_ordered_by_similarity(self):
        store = VectorStore(dimension=2)
        chunks = [
            TextChunk("x-axis", {"id": "x"}, 0),
            TextChunk("y-axis", {"id": "y"}, 1),
        ]
        store.add_vectors([np.array([1, 0]), np.array([0, 1])], chunks)

        results = store.search(np.array([1, 0]), top_k=2)

        assert [result.chunk.content for result in results] == ["x-axis"]
        assert results[0].score == pytest.approx(1.0)

    def test_search_rejects_wrong_query_dimension(self):
        store = VectorStore(dimension=2)
        store.add_vectors([np.array([1, 0])], [TextChunk("x", {}, 0)])

        with pytest.raises(ValueError, match="Query vector dimension"):
            store.search(np.array([1, 0, 0]))

    def test_search_returns_empty_for_zero_query_or_empty_store(self):
        store = VectorStore(dimension=2)
        assert store.search(np.array([1, 0])) == []

        store.add_vectors([np.array([1, 0])], [TextChunk("x", {}, 0)])
        assert store.search(np.array([0, 0])) == []

    def test_save_and_load_round_trips_vectors_and_chunks(self, tmp_path):
        store = VectorStore(dimension=2)
        store.add_vectors(
            [np.array([1, 0]), np.array([0, 1])],
            [TextChunk("first", {"a": 1}, 0), TextChunk("second", {"b": 2}, 1)],
        )

        store.save(str(tmp_path))
        loaded = VectorStore()

        assert loaded.load(str(tmp_path)) is True
        assert loaded.size == 2
        assert loaded.dimension == 2
        assert loaded.chunks[1].content == "second"

    def test_load_returns_false_when_files_missing(self, tmp_path):
        assert VectorStore().load(str(tmp_path)) is False

    def test_clear_removes_vectors_and_chunks(self):
        store = VectorStore(dimension=2)
        store.add_vectors([np.array([1, 0])], [TextChunk("x", {}, 0)])

        store.clear()

        assert store.size == 0
        assert store.chunks == []

    def test_cosine_similarity_handles_zero_vectors(self):
        assert cosine_similarity(np.array([0, 0]), np.array([1, 0])) == 0.0
        assert cosine_similarity(np.array([1, 0]), np.array([1, 0])) == pytest.approx(1.0)


class TestDocumentLoader:
    def test_load_text_file(self, tmp_path):
        path = tmp_path / "doc.txt"
        path.write_text("hello", encoding="utf-8")

        doc = DocumentLoader.load_text_file(str(path), {"kind": "test"})

        assert doc["content"] == "hello"
        assert doc["metadata"]["filename"] == "doc.txt"
        assert doc["metadata"]["kind"] == "test"

    def test_load_json_file_extracts_dict_content_key(self, tmp_path):
        path = tmp_path / "doc.json"
        path.write_text(json.dumps({"content": "hello", "other": 1}), encoding="utf-8")

        doc = DocumentLoader.load_json_file(str(path))

        assert doc["content"] == "hello"
        assert doc["metadata"]["file_type"] == ".json"

    def test_load_json_file_handles_lists(self, tmp_path):
        path = tmp_path / "list.json"
        path.write_text(json.dumps(["a", "b"]), encoding="utf-8")

        doc = DocumentLoader.load_json_file(str(path))

        assert doc["content"] == "a\nb"

    def test_load_faq_data(self):
        docs = DocumentLoader.load_faq_data(
            [{"id": "faq-1", "question": "Q?", "answer": "A.", "category": "cat"}]
        )

        assert len(docs) == 1
        assert "Q?" in docs[0]["content"]
        assert "A." in docs[0]["content"]
        assert docs[0]["metadata"]["faq_id"] == "faq-1"

    def test_load_directory_filters_supported_files(self, tmp_path):
        (tmp_path / "a.txt").write_text("text", encoding="utf-8")
        (tmp_path / "b.md").write_text("markdown", encoding="utf-8")
        (tmp_path / "c.skip").write_text("skip", encoding="utf-8")

        docs = DocumentLoader.load_directory(str(tmp_path), extensions=[".txt", ".md"])

        assert sorted(doc["metadata"]["filename"] for doc in docs) == ["a.txt", "b.md"]

    def test_load_missing_paths_raise(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            DocumentLoader.load_text_file(str(tmp_path / "missing.txt"))

        with pytest.raises(FileNotFoundError):
            DocumentLoader.load_directory(str(tmp_path / "missing"))


class TestRAGPipeline:
    @pytest.mark.asyncio
    async def test_add_documents_without_embedding_returns_chunk_count(self):
        pipeline = RAGPipeline(chunk_size=20, chunk_overlap=0, vector_dimension=2)

        count = await pipeline.add_documents([{"content": "hello world", "metadata": {}}])

        assert count == 1
        assert pipeline.vector_store.size == 0

    @pytest.mark.asyncio
    async def test_add_documents_with_embedding_indexes_chunks(self):
        async def embedding_func(texts):
            return [[1.0, 0.0] for _ in texts]

        pipeline = RAGPipeline(
            embedding_func=embedding_func,
            chunk_size=20,
            chunk_overlap=0,
            vector_dimension=2,
        )

        count = await pipeline.add_documents([{"content": "hello world", "metadata": {}}])

        assert count == 1
        assert pipeline.vector_store.size == 1

    @pytest.mark.asyncio
    async def test_search_and_context_with_embedding(self):
        async def embedding_func(texts):
            return [[1.0, 0.0] for _ in texts]

        pipeline = RAGPipeline(
            embedding_func=embedding_func,
            chunk_size=20,
            chunk_overlap=0,
            vector_dimension=2,
        )
        await pipeline.add_documents([{"content": "return policy", "metadata": {}}])

        results = await pipeline.search("return", top_k=1)
        context = await pipeline.get_context("return", top_k=1)

        assert len(results) == 1
        assert "return policy" in context

    @pytest.mark.asyncio
    async def test_search_and_context_without_embedding_are_empty(self):
        pipeline = RAGPipeline(vector_dimension=2)

        assert await pipeline.search("hello") == []
        assert await pipeline.get_context("hello") == ""

    @pytest.mark.asyncio
    async def test_add_faq_data_uses_document_loader(self):
        async def embedding_func(texts):
            return [[1.0, 0.0] for _ in texts]

        pipeline = RAGPipeline(
            embedding_func=embedding_func,
            chunk_size=100,
            chunk_overlap=0,
            vector_dimension=2,
        )

        count = await pipeline.add_faq_data([{"question": "Q?", "answer": "A."}])

        assert count == 1
        assert pipeline.vector_store.size == 1

    def test_get_stats(self):
        pipeline = RAGPipeline(chunk_size=123, chunk_overlap=7, vector_dimension=2)

        stats = pipeline.get_stats()

        assert stats["total_chunks"] == 0
        assert stats["chunk_size"] == 123
        assert stats["chunk_overlap"] == 7
        assert stats["vector_dimension"] == 2
        assert stats["has_embedding_func"] is False
