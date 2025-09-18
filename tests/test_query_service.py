"""Query service coverage for semantic and text search pathways."""
from __future__ import annotations

from typing import List

from graph_space_v2.core.services.query_service import QueryService

from tests.conftest import DummyEmbeddingService, DummyLLMService


def _populate_sample_data(knowledge_graph) -> List[str]:
    task_id = knowledge_graph.add_task({
        "title": "Write docs",
        "description": "Draft the API section",
        "tags": ["docs"],
    })
    knowledge_graph.add_note({
        "title": "Docs outline",
        "content": "Remember to cover authentication",
        "tags": ["docs"],
    })
    knowledge_graph.add_contact({
        "name": "Alex Writer",
        "email": "alex@example.com",
        "organization": "Docs Guild",
        "tags": ["docs"],
    })
    return [task_id]


def test_text_search_ranks_entities(knowledge_graph) -> None:
    """Text search should surface entities across all supported types."""
    task_id = _populate_sample_data(knowledge_graph)[0]
    service = QueryService(knowledge_graph)

    results = service.text_search("docs")
    result_types = {result["type"] for result in results}
    assert {"note", "task", "contact"}.issubset(result_types)
    assert any(result["id"] == task_id for result in results)


def test_semantic_search_uses_embeddings(knowledge_graph, dummy_embedding_service: DummyEmbeddingService) -> None:
    """Semantic search should delegate to the embedding service when available."""
    task_id = _populate_sample_data(knowledge_graph)[0]
    dummy_embedding_service.semantic_matches = [
        {
            "id": task_id,
            "score": 0.95,
            "metadata": {"type": "task"},
        }
    ]
    service = QueryService(knowledge_graph, dummy_embedding_service, DummyLLMService())

    results = service.semantic_search("docs")
    assert results[0]["id"] == task_id
    assert results[0]["type"] == "task"


def test_semantic_search_falls_back_to_text(knowledge_graph) -> None:
    """If embeddings are unavailable, semantic_search should reuse text search."""
    _populate_sample_data(knowledge_graph)
    service = QueryService(knowledge_graph, None, None)

    results = service.semantic_search("authentication")
    assert results  # falls back to text search
