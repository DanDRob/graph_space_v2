"""Knowledge graph storage and relationship tests."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph
from graph_space_v2.utils.errors.exceptions import EntityNotFoundError


def _load_persisted_data(path: Path) -> dict:
    return json.loads(path.read_text())


def test_add_update_delete_note_persists_changes(knowledge_graph: KnowledgeGraph, data_file: Path) -> None:
    """Notes should be stored, updated, and deleted both in memory and on disk."""
    note_id = knowledge_graph.add_note({
        "title": "Research",
        "content": "Investigate vector databases",
        "tags": ["ai", "research"],
    })
    assert knowledge_graph.get_note(note_id)["title"] == "Research"

    knowledge_graph.update_note(note_id, {"title": "Updated title"})
    assert knowledge_graph.get_note(note_id)["title"] == "Updated title"

    persisted = _load_persisted_data(data_file)
    assert persisted["notes"][0]["title"] == "Updated title"

    assert knowledge_graph.delete_note(note_id) is True
    assert knowledge_graph.get_note(note_id) is None


def test_task_and_note_relationships_support_lookup(knowledge_graph: KnowledgeGraph) -> None:
    """Shared tags should link notes and tasks and surface via graph queries."""
    note_id = knowledge_graph.add_note({
        "title": "Project plan",
        "content": "Outline tasks for launch",
        "tags": ["launch"],
    })
    task_id = knowledge_graph.add_task({
        "title": "Launch prep",
        "description": "Finalize checklist",
        "tags": ["launch"],
    })

    related = knowledge_graph.get_related_entities(note_id, "note")
    assert any(entity["id"] == task_id for entity in related)

    tag_results = knowledge_graph.search_by_tag("launch")
    found_ids = {result["id"] for result in tag_results}
    assert {note_id, task_id}.issubset(found_ids)

    path = knowledge_graph.find_path(note_id, "note", task_id, "task")
    assert [segment["id"] for segment in path][:2] == [note_id, task_id]


def test_manual_relationship_creation_updates_graph(knowledge_graph: KnowledgeGraph) -> None:
    """Explicit relationships should be represented as graph edges."""
    first = knowledge_graph.add_note({"title": "A", "content": "", "tags": []})
    second = knowledge_graph.add_note({"title": "B", "content": "", "tags": []})

    created = knowledge_graph.add_relationship(first, second, "linked")
    assert created is True
    assert knowledge_graph.graph.has_edge(f"note_{first}", f"note_{second}")


def test_update_node_and_delete_node_manage_entities(knowledge_graph: KnowledgeGraph, data_file: Path) -> None:
    """Generic node updates should mutate stored entities and support removal."""
    task_id = knowledge_graph.add_task({
        "title": "Status report",
        "description": "Share weekly update",
        "tags": ["status"],
    })

    assert knowledge_graph.update_node(task_id, {"title": "Weekly status"}) is True
    assert knowledge_graph.get_task(task_id)["title"] == "Weekly status"

    assert knowledge_graph.delete_node(task_id) is True
    assert knowledge_graph.get_task(task_id) is None

    persisted = _load_persisted_data(data_file)
    assert persisted["tasks"] == []


def test_remove_all_relationships_clears_edges(knowledge_graph: KnowledgeGraph) -> None:
    """Removing relationships should isolate the node from the graph."""
    note_id = knowledge_graph.add_note({
        "title": "Tag note",
        "content": "",
        "tags": ["shared"],
    })
    knowledge_graph.add_task({
        "title": "Tag task",
        "description": "",
        "tags": ["shared"],
    })

    node_id = f"note_{note_id}"
    assert list(knowledge_graph.graph.neighbors(node_id))  # ensure an edge exists

    assert knowledge_graph.remove_all_relationships(note_id) is True
    assert list(knowledge_graph.graph.neighbors(node_id)) == []


def test_add_and_retrieve_document(knowledge_graph: KnowledgeGraph, data_file: Path) -> None:
    """Documents should be persisted and retrievable like other entities."""
    document_id = knowledge_graph.add_document({
        "id": "doc1",
        "title": "Spec",
        "content": "Functional spec",
        "tags": ["spec"],
        "topics": ["architecture"],
    })

    stored = knowledge_graph.get_document(document_id)
    assert stored["title"] == "Spec"

    persisted = _load_persisted_data(data_file)
    assert persisted["documents"][0]["id"] == "doc1"


def test_find_path_raises_for_missing_nodes(knowledge_graph: KnowledgeGraph) -> None:
    """Finding a path for unknown entities should raise an informative error."""
    with pytest.raises(EntityNotFoundError):
        knowledge_graph.find_path("missing", "note", "also-missing", "task")


def test_remove_relationship_missing_node_returns_false(knowledge_graph: KnowledgeGraph) -> None:
    """Removing relationships for a non-existent node should fail gracefully."""
    assert knowledge_graph.remove_all_relationships("nonexistent") is False
