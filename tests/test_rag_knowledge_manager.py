"""RAG knowledge manager tests."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.knowledge.rag_manager import RAGKnowledgeManager
from app.rag.text_splitter import TextChunk


def make_config(api_key="not-set"):
    config = Settings()
    config.LLM_API_KEY = SecretStr(api_key)
    config.KNOWLEDGE_TOP_K = 3
    config.VECTOR_BACKEND = "memory"
    return config


@pytest.mark.asyncio
async def test_initialize_creates_pipeline_and_loads_faq_data():
    manager = RAGKnowledgeManager(make_config(api_key="test-key"))

    with (
        patch.object(manager, "_create_embedding_func", return_value=AsyncMock()),
        patch("app.knowledge.rag_manager.RAGPipeline") as pipeline_cls,
    ):
        pipeline = AsyncMock()
        pipeline_cls.return_value = pipeline

        await manager.initialize()

    assert manager._initialized is True
    assert manager._rag_pipeline is pipeline
    pipeline.add_faq_data.assert_awaited_once()


@pytest.mark.asyncio
async def test_initialize_is_idempotent_when_already_initialized():
    manager = RAGKnowledgeManager(make_config())
    manager._initialized = True

    with patch.object(manager, "_create_embedding_func") as create_embedding:
        await manager.initialize()

    create_embedding.assert_not_called()


@pytest.mark.asyncio
async def test_initialize_falls_back_when_pipeline_creation_fails():
    manager = RAGKnowledgeManager(make_config())

    with patch("app.knowledge.rag_manager.RAGPipeline", side_effect=RuntimeError("boom")):
        await manager.initialize()

    assert manager._initialized is False


def test_create_embedding_func_prefers_openai_when_api_key_is_set():
    manager = RAGKnowledgeManager(make_config(api_key="test-key"))

    with (
        patch("app.knowledge.rag_manager.OpenAIEmbedding") as openai_embedding,
        patch("app.knowledge.rag_manager.CachedEmbeddingProvider") as cached_embedding,
    ):
        result = manager._create_embedding_func()

    openai_embedding.assert_called_once_with(
        api_key="test-key",
        model=manager.config.EMBEDDING_MODEL,
        base_url=manager.config.LLM_BASE_URL,
        dimension=manager.config.EMBEDDING_DIMENSION,
    )
    cached_embedding.assert_called_once()
    assert result == cached_embedding.return_value


def test_create_embedding_func_falls_back_to_local_embedding():
    manager = RAGKnowledgeManager(make_config(api_key="not-set"))

    with (
        patch("app.knowledge.rag_manager.LocalEmbedding") as local_embedding,
        patch("app.knowledge.rag_manager.CachedEmbeddingProvider") as cached_embedding,
    ):
        result = manager._create_embedding_func()

    local_embedding.assert_called_once_with(model_name="all-MiniLM-L6-v2")
    cached_embedding.assert_called_once()
    assert result == cached_embedding.return_value


def test_create_vector_store_uses_memory_backend():
    manager = RAGKnowledgeManager(make_config())

    store = manager._create_vector_store(384)

    assert store.__class__.__name__ == "InMemoryVectorStore"
    assert store.dimension == 384


@pytest.mark.asyncio
async def test_load_faq_data_noops_without_pipeline():
    manager = RAGKnowledgeManager(make_config())

    await manager._load_faq_data()

    assert manager._rag_pipeline is None


@pytest.mark.asyncio
async def test_search_returns_rag_results_when_available():
    manager = RAGKnowledgeManager(make_config())
    manager._initialized = True
    manager._rag_pipeline = AsyncMock()
    manager._rag_pipeline.search.return_value = [
        SimpleNamespace(
            chunk=TextChunk(
                content="Question\nAnswer text",
                metadata={"question": "Question", "category": "orders"},
                index=0,
            ),
            score=0.9,
        )
    ]

    results = await manager.search("question", top_k=2)

    assert results == [
        {
            "question": "Question",
            "answer": "Question\nAnswer text",
            "category": "orders",
            "score": 0.9,
            "source": "rag",
        }
    ]
    manager._rag_pipeline.search.assert_awaited_once_with("question", top_k=2)


@pytest.mark.asyncio
async def test_search_falls_back_to_keyword_when_rag_empty_or_fails():
    manager = RAGKnowledgeManager(make_config())
    manager._initialized = True
    manager._rag_pipeline = AsyncMock()
    manager._rag_pipeline.search.return_value = []

    results = await manager.search("q1", top_k=1)
    assert isinstance(results, list)

    manager._rag_pipeline.search.side_effect = RuntimeError("rag down")
    results = await manager.search("q1", top_k=1)
    assert isinstance(results, list)


@pytest.mark.asyncio
async def test_add_document_requires_initialized_pipeline():
    manager = RAGKnowledgeManager(make_config())

    assert await manager.add_document("content") == 0


@pytest.mark.asyncio
async def test_add_document_delegates_to_pipeline():
    manager = RAGKnowledgeManager(make_config())
    manager._initialized = True
    manager._rag_pipeline = AsyncMock()
    manager._rag_pipeline.add_documents.return_value = 1

    count = await manager.add_document("content", {"source": "manual"})

    assert count == 1
    manager._rag_pipeline.add_documents.assert_awaited_once_with(
        [{"content": "content", "metadata": {"source": "manual"}}]
    )


def test_get_stats_and_clear_cache():
    manager = RAGKnowledgeManager(make_config())

    assert manager.get_stats() == {"initialized": False}

    vector_store = MagicMock()
    manager._initialized = True
    manager._rag_pipeline = MagicMock()
    manager._rag_pipeline.get_stats.return_value = {"total_chunks": 2}
    manager._rag_pipeline.vector_store = vector_store

    assert manager.get_stats() == {"total_chunks": 2, "initialized": True}
    manager.clear_cache()
    vector_store.clear.assert_called_once()
