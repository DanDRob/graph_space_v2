import pytest
from unittest.mock import MagicMock, patch
from graph_space_v2.core.services.query_service import QueryService
from graph_space_v2.core.models.note import Note
from graph_space_v2.core.models.task import Task
from datetime import datetime

@pytest.fixture
def mock_kg():
    return MagicMock()

@pytest.fixture
def mock_embedding_service():
    mock = MagicMock()
    mock.model = None
    mock.embed_text.return_value = [0.1, 0.2, 0.3]
    mock.search.return_value = {"matches": []}
    return mock

@pytest.fixture
def mock_llm_service():
    mock = MagicMock()
    mock.api_key = None
    return mock

@pytest.fixture
def query_service(mock_kg, mock_embedding_service, mock_llm_service):
    return QueryService(
        knowledge_graph=mock_kg,
        embedding_service=mock_embedding_service,
        llm_service=mock_llm_service
    )

def test_text_search_basic_keyword(query_service, mock_kg):
    query = "test keyword"

    note_data = Note(id="note1", title="Test Note", content="Contains test keyword here", created_at=datetime.now(), updated_at=datetime.now()).to_dict()
    task_data = Task(id="task1", title="Task with test keyword", description="This task also contains the test keyword.", created_at=datetime.now(), updated_at=datetime.now()).to_dict()
    non_match_note = Note(id="note2", title="Another", content="No match", created_at=datetime.now(), updated_at=datetime.now()).to_dict()

    mock_kg.data = {
        "notes": [note_data, non_match_note],
        "tasks": [task_data],
        "contacts": []
    }

    results = query_service.text_search(query)

    assert len(results) == 2
    result_ids = [r['id'] for r in results]
    assert "note1" in result_ids
    assert "task1" in result_ids
    assert isinstance(results[0]['entity'], dict)


def test_semantic_search_embedding_service_present_but_model_none(query_service, mock_embedding_service, mock_kg):
    query = "semantic query"
    # mock_embedding_service.model is None via fixture
    # EmbeddingService.embed_text will use random embeddings.
    # QueryService will then call search with these.
    # Default mock for search returns no matches.

    # If QueryService.semantic_search has a fallback due to an exception during embedding/search,
    # that would be tested by test_semantic_search_embedding_service_errors.
    # Here, we test the path where embedding proceeds but yields no results.

    results = query_service.semantic_search(query)

    assert results == []
    mock_embedding_service.embed_text.assert_called_with(query)
    # QueryService initializes filter_by to {} if entity_types is None
    mock_embedding_service.search.assert_called_with([0.1,0.2,0.3], 5, filter_by={})


def test_semantic_search_embedding_service_errors(query_service, mock_embedding_service, mock_kg):
    query = "semantic query causing error"
    mock_embedding_service.embed_text.side_effect = Exception("Embedding failed")

    fallback_results = [{"id": "fallback_note", "type": "note", "entity": {"title": "Fallback"}, "score": 0.5, "snippet": "Fallback snippet"}]
    # Mock the text_search method that it should fall back to
    query_service.text_search = MagicMock(return_value=fallback_results)

    results = query_service.semantic_search(query)

    assert results == fallback_results
    mock_embedding_service.embed_text.assert_called_with(query)
    query_service.text_search.assert_called_with(query, None, 5)


def test_semantic_search_available_and_finds_results(query_service, mock_embedding_service, mock_kg):
    query = "semantic query"
    mock_embedding_service.model = MagicMock() # Simulate embedding model is available

    mock_query_embedding = [0.1, 0.2, 0.3]
    mock_embedding_service.embed_text.return_value = mock_query_embedding

    # QueryService uses match["id"] to fetch from KG via _get_entity.
    # So, match["id"] from embedding_service.search must be the actual entity ID.
    search_matches_from_embedding = [
        {"id": "sem1_actual_id", "text": "Semantic Note Content", "score": 0.9, "metadata": {"type": "note"}}, # No separate metadata.id needed if "id" is the key
        {"id": "sem2_actual_id", "text": "Semantic Task Content", "score": 0.85, "metadata": {"type": "task"}}
    ]
    mock_embedding_service.search.return_value = {"matches": search_matches_from_embedding}

    note_kg_data = Note(id="sem1_actual_id", title="Semantic Note", content="Content").to_dict()
    task_kg_data = Task(id="sem2_actual_id", title="Semantic Task", description="Desc").to_dict()

    def get_entity_side_effect(entity_type, entity_id):
        # This function is called by mock_kg.get_note and mock_kg.get_task
        if entity_type == "note" and entity_id == "sem1_actual_id": return note_kg_data
        if entity_type == "task" and entity_id == "sem2_actual_id": return task_kg_data
        return None

    mock_kg.get_note.side_effect = lambda id_param: get_entity_side_effect("note", id_param)
    mock_kg.get_task.side_effect = lambda id_param: get_entity_side_effect("task", id_param)

    results = query_service.semantic_search(query) # Call the method under test

    assert len(results) == 2
    mock_embedding_service.embed_text.assert_called_with(query)
    mock_embedding_service.search.assert_called_with(mock_query_embedding, 5, filter_by={}) # Corrected here

    mock_kg.get_note.assert_any_call("sem1_actual_id")
    mock_kg.get_task.assert_any_call("sem2_actual_id")

    # QueryService._get_entity returns a dict, so results[x]['entity'] is a dict
    assert isinstance(results[0]['entity'], dict)
    assert results[0]['entity']['id'] == "sem1_actual_id"
    assert results[0]['entity']['title'] == "Semantic Note" # Check a field from the dict
    assert isinstance(results[1]['entity'], dict)
    assert results[1]['entity']['id'] == "sem2_actual_id"
