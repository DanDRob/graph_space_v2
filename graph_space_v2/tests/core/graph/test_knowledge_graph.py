import pytest
import os
import json
from unittest.mock import patch, mock_open
from datetime import datetime # Added this import
from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph
from graph_space_v2.core.models.note import Note
from graph_space_v2.core.models.task import Task
from graph_space_v2.core.models.contact import Contact

@pytest.fixture
def kg():
    db_path = "./test_kg_data.json" # Explicitly make it relative to CWD
    if os.path.exists(db_path):
        os.remove(db_path)
    graph = KnowledgeGraph(data_path=db_path)
    yield graph
    if os.path.exists(db_path):
        os.remove(db_path)

def test_kg_add_and_get_node(kg):
    note_obj = Note(title="KG Test Note", content="Content for KG")
    note_data_dict = note_obj.to_dict()
    kg.add_note(note_data_dict)
    retrieved_node_data = kg.get_note(note_obj.id)
    assert retrieved_node_data is not None
    assert retrieved_node_data['id'] == note_obj.id
    assert retrieved_node_data['title'] == "KG Test Note"

def test_kg_get_node_not_found(kg):
    assert kg.get_note("non_existent_id_kg") is None

def test_kg_add_relationship(kg):
    note1_obj = Note(content="Note 1 for KG relationship")
    task1_obj = Task(title="Task 1 for KG relationship")
    kg.add_note(note1_obj.to_dict())
    kg.add_task(task1_obj.to_dict())
    kg.add_relationship(note1_obj.id, task1_obj.id, "relates_to", properties={"reason": "testing"})
    graph_note1_id = f"note_{note1_obj.id}"
    graph_task1_id = f"task_{task1_obj.id}"
    assert kg.graph.has_edge(graph_note1_id, graph_task1_id)
    edge_data = kg.graph.get_edge_data(graph_note1_id, graph_task1_id)
    assert edge_data['relationship'] == "relates_to" # For nx.Graph, edge_data is the dict itself
    assert edge_data['reason'] == "testing" # Properties are added at the top level of edge attributes

def test_kg_get_graph_neighbors_directly(kg):
    note1_obj = Note(content="Note 1 neighbors")
    note2_obj = Note(content="Note 2 neighbors")
    task1_obj = Task(title="Task 1 neighbors")
    kg.add_note(note1_obj.to_dict())
    kg.add_task(task1_obj.to_dict())
    kg.add_note(note2_obj.to_dict())
    kg.add_relationship(note1_obj.id, note2_obj.id, "connects_to")
    kg.add_relationship(note1_obj.id, task1_obj.id, "assigned_to")
    graph_note1_id = f"note_{note1_obj.id}"
    graph_note2_id = f"note_{note2_obj.id}"
    graph_task1_id = f"task_{task1_obj.id}"
    graph_neighbors_prefixed_ids = list(kg.graph.neighbors(graph_note1_id))
    assert len(graph_neighbors_prefixed_ids) == 2
    assert graph_note2_id in graph_neighbors_prefixed_ids
    assert graph_task1_id in graph_neighbors_prefixed_ids

@patch("builtins.open", new_callable=mock_open)
@patch("json.dump")
def test_kg_save_data(mock_json_dump, mock_file_open, kg):
    note_obj = Note(content="Note for saving", id="save_note_id")
    kg.add_note(note_obj.to_dict())
    kg.save_data()
    mock_file_open.assert_called_with(kg.data_path, "w")
    assert mock_json_dump.called
    args, _ = mock_json_dump.call_args
    saved_data_root = args[0]
    assert saved_data_root == kg.data
    assert 'notes' in saved_data_root
    assert len(saved_data_root['notes']) == 1
    found_node = False
    for node_data_dict in saved_data_root['notes']:
        if node_data_dict.get('id') == note_obj.id:
            found_node = True
            break
    assert found_node, f"Note with id {note_obj.id} not found in saved data"

@patch("os.path.exists", return_value=True)
def test_kg_load_data_and_build_graph(mock_path_exists, kg):
    note_dict = {"id": "loaded_note_id", "title": "Loaded Note", "content": "Loaded Content",
                 "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat()}
    test_db_content = {"notes": [note_dict], "tasks": [], "contacts": [], "documents": []}
    m = mock_open(read_data=json.dumps(test_db_content))
    with patch("builtins.open", m):
        kg.data = kg._load_data()
        kg.build_graph()
    m.assert_called_with(kg.data_path, "r")
    retrieved_node_data_from_kg_data = kg.get_note("loaded_note_id")
    assert retrieved_node_data_from_kg_data is not None
    assert retrieved_node_data_from_kg_data['id'] == "loaded_note_id"
    assert retrieved_node_data_from_kg_data['title'] == "Loaded Note"
    graph_node_id = f"note_loaded_note_id"
    assert graph_node_id in kg.graph
    assert kg.graph.nodes[graph_node_id]['data']['title'] == "Loaded Note"

def test_kg_delete_node_cascades_relationships(kg):
    note1_obj = Note(content="Note 1 to remove")
    note2_obj = Note(content="Note 2 connected")
    task1_obj = Task(title="Task 1 connected")
    kg.add_note(note1_obj.to_dict())
    kg.add_note(note2_obj.to_dict())
    kg.add_task(task1_obj.to_dict())
    graph_note1_id = f"note_{note1_obj.id}"
    graph_note2_id = f"note_{note2_obj.id}"
    graph_task1_id = f"task_{task1_obj.id}"
    kg.add_relationship(note1_obj.id, note2_obj.id, "rel_1")
    kg.add_relationship(task1_obj.id, note1_obj.id, "rel_2")
    assert kg.graph.has_edge(graph_note1_id, graph_note2_id)
    assert kg.graph.has_edge(graph_task1_id, graph_note1_id)
    kg.delete_note(note1_obj.id)
    assert kg.get_note(note1_obj.id) is None
    assert not kg.graph.has_node(graph_note1_id)
    assert kg.get_note(note2_obj.id) is not None
    assert kg.get_task(task1_obj.id) is not None
