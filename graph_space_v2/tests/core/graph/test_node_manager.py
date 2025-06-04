import pytest
from graph_space_v2.core.graph.node_manager import NodeManager
from graph_space_v2.core.models.note import Note # Assuming Note is a valid node type
import os # For path operations
from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph # Import KG

@pytest.fixture
def node_manager():
    # NodeManager requires a KnowledgeGraph instance
    temp_kg_path = "./test_nodemanager_kg_data.json" # Explicitly make it relative to CWD
    if os.path.exists(temp_kg_path):
        os.remove(temp_kg_path)
    kg_instance = KnowledgeGraph(data_path=temp_kg_path)
    manager = NodeManager(knowledge_graph=kg_instance)
    yield manager
    if os.path.exists(temp_kg_path):
        os.remove(temp_kg_path)

def test_node_manager_create_node(node_manager): # Renamed from add_node
    note_data = {"content": "Test Note for NodeManager", "title": "NM Test"}
    # NodeManager.create_node expects data dict and type, returns ID
    note_id = node_manager.create_node(entity_type="note", data=note_data)
    assert note_id is not None

    # Verify through NodeManager.get_node (which calls KG.get_note)
    retrieved_note_data = node_manager.get_node(entity_type="note", entity_id=note_id)
    assert retrieved_note_data is not None
    assert retrieved_note_data['id'] == note_id
    assert retrieved_note_data['content'] == "Test Note for NodeManager"

def test_node_manager_get_node_not_found(node_manager):
    assert node_manager.get_node(entity_type="note", entity_id="non_existent_id") is None

def test_node_manager_delete_node(node_manager): # Renamed from remove_node
    note_data = {"content": "Test Note to Remove", "title":"NM Delete Test"}
    note_id = node_manager.create_node(entity_type="note", data=note_data)
    assert node_manager.get_node(entity_type="note", entity_id=note_id) is not None

    success = node_manager.delete_node(entity_type="note", entity_id=note_id)
    assert success is True
    assert node_manager.get_node(entity_type="note", entity_id=note_id) is None

def test_node_manager_update_node(node_manager):
    initial_note_data = {"title": "Initial Title", "content": "Initial Content"}
    # Use Note model to generate ID consistent with how KG might do it if data doesn't have ID
    note_for_id = Note(**initial_note_data)
    initial_note_data_with_id = note_for_id.to_dict()

    note_id = node_manager.create_node(entity_type="note", data=initial_note_data_with_id)
    assert note_id == initial_note_data_with_id['id'] # Ensure ID is used if provided

    updated_data_payload = {"title": "Updated Title", "content": "Updated Content"}

    success = node_manager.update_node(entity_type="note", entity_id=note_id, data=updated_data_payload)
    assert success is True

    retrieved_note_data = node_manager.get_node(entity_type="note", entity_id=note_id)
    assert retrieved_note_data['title'] == "Updated Title"
    assert retrieved_note_data['content'] == "Updated Content"


def test_node_manager_get_nodes_by_type(node_manager): # Renamed from get_all_nodes
    note_data1 = Note(content="Note 1", title="NM Note 1").to_dict()
    note_data2 = Note(content="Note 2", title="NM Note 2").to_dict()

    id1 = node_manager.create_node(entity_type="note", data=note_data1)
    id2 = node_manager.create_node(entity_type="note", data=note_data2)

    all_notes_data = node_manager.get_nodes_by_type(entity_type="note")
    # Check current items in self.data['notes'] which can be affected by other tests if KG instance is shared
    # For a fresh KG per test, this would be 2.
    # If KG is reused by fixture, this count could be higher.
    # The current fixture creates a new KG for each test.
    assert len(all_notes_data) == 2

    retrieved_ids = [n['id'] for n in all_notes_data]
    assert id1 in retrieved_ids
    assert id2 in retrieved_ids

# NodeManager does not have a clear_nodes method.
# This functionality belongs to KnowledgeGraph.
# def test_node_manager_clear_nodes(node_manager):
#     pass
