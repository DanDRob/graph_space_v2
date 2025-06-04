import pytest
from unittest.mock import MagicMock, patch
from graph_space_v2.core.services.note_service import NoteService
from graph_space_v2.core.models.note import Note # For creating test data
from datetime import datetime, timedelta # Import timedelta

@pytest.fixture
def mock_kg():
    return MagicMock()

@pytest.fixture
def mock_embedding_service():
    return MagicMock()

@pytest.fixture
def mock_llm_service():
    return MagicMock()

@pytest.fixture
def note_service(mock_kg, mock_embedding_service, mock_llm_service):
    return NoteService(
        knowledge_graph=mock_kg,
        embedding_service=mock_embedding_service,
        llm_service=mock_llm_service
    )

def test_add_note(note_service, mock_kg): # Renamed from test_create_note
    note_data_input = {"title": "Test Note", "content": "This is a test note."}

    # NoteService.add_note creates a Note instance internally, assigns an ID,
    # then calls kg.add_note with the dict version of this instance.
    # kg.add_note is expected to return the ID of the created note.
    expected_note_id = "some_uuid_generated_by_note_constructor_or_service"
    mock_kg.add_note.return_value = expected_note_id

    # The NoteService.add_note method returns an ID string.
    created_note_id = note_service.add_note(note_data_input)

    assert created_note_id == expected_note_id

    mock_kg.add_note.assert_called_once()
    call_args = mock_kg.add_note.call_args[0][0]
    assert call_args['title'] == "Test Note"
    assert call_args['content'] == "This is a test note."
    assert 'id' in call_args # Note model constructor or service should generate an ID
    assert 'created_at' in call_args # Service adds these if not present
    assert 'updated_at' in call_args

def test_get_note(note_service, mock_kg):
    note_id = "test_note_id"
    note_data_from_kg = {
        "id": note_id, "title": "Fetched Note", "content": "Content from KG",
        "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat(),
        "tags": [], "source": {}
    }
    mock_kg.get_note.return_value = note_data_from_kg

    note_obj = note_service.get_note(note_id) # Service converts dict from KG to Note object

    assert note_obj is not None
    assert isinstance(note_obj, Note)
    assert note_obj.id == note_id
    assert note_obj.title == "Fetched Note"
    mock_kg.get_note.assert_called_with(note_id)

def test_get_all_notes(note_service, mock_kg):
    notes_data_from_kg = [
        {"id": "note1", "title": "Note 1", "content": "Content 1", "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat(), "tags": [], "source": {}},
        {"id": "note2", "title": "Note 2", "content": "Content 2", "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat(), "tags": [], "source": {}}
    ]
    # NoteService.get_all_notes directly accesses kg.data['notes'] which is a list of dicts
    mock_kg.data = {"notes": notes_data_from_kg}

    notes_list_of_dicts = note_service.get_all_notes() # Returns list of dicts

    assert len(notes_list_of_dicts) == 2
    assert isinstance(notes_list_of_dicts[0], dict) # Check it's a dict
    assert notes_list_of_dicts[0]['title'] == "Note 1"
    assert notes_list_of_dicts[1]['id'] == "note2"

def test_update_note(note_service, mock_kg):
    note_id = "note_to_update"
    update_data_payload = {"title": "Updated Title", "content": "Updated Content"} # This is what test passes to service

    # This is what kg.get_note returns initially when service calls it
    original_note_data_from_kg = {
        "id": note_id, "title": "Original Title", "content": "Original Content",
        "created_at": datetime.now().isoformat(),
        "updated_at": (datetime.now() - timedelta(seconds=10)).isoformat(), # ensure updated_at is older
        "tags": [], "source": {}
    }

    # This is what kg.get_note returns the *second* time (after update)
    # It should reflect the changes applied by kg.update_note.
    # The service's update_note method adds 'updated_at' to the dict it passes to kg.update_note.
    # So, the data in KG (and thus returned by the second get_note) should have this new 'updated_at'.
    final_note_data_in_kg = {
        "id": note_id, "title": "Updated Title", "content": "Updated Content", # from update_data_payload
        "created_at": original_note_data_from_kg['created_at'], # created_at should persist
        "updated_at": datetime.now().isoformat(), # This will be new
        "tags": [], "source": {}
    }

    # Configure mocks:
    # 1. First call to kg.get_note (inside service.update_note before calling kg.update_note - though NoteService doesn't do this, it calls kg.update_note directly)
    #    Actually, NoteService.update_note *only* calls kg.update_note, then kg.get_note for the return.
    #    So, the first kg.get_note is not called by update_note.
    # 2. kg.update_note is called by service.
    mock_kg.update_note.return_value = True
    # 3. Second call to kg.get_note (by service.update_note to get the object to return).
    #    This should return the data as it would be *after* the update.
    mock_kg.get_note.return_value = final_note_data_in_kg

    updated_note_obj = note_service.update_note(note_id, update_data_payload)

    assert updated_note_obj is not None
    assert isinstance(updated_note_obj, Note)
    assert updated_note_obj.title == "Updated Title"
    assert updated_note_obj.content == "Updated Content"
    assert updated_note_obj.updated_at == final_note_data_in_kg['updated_at'] # Check new updated_at

    mock_kg.update_note.assert_called_once()

    # Check arguments passed to kg.update_note
    # NoteService.update_note passes `note_data` which is `update_data_payload` plus a new `updated_at`
    args_to_kg_update_note = mock_kg.update_note.call_args[0]
    assert args_to_kg_update_note[0] == note_id # note_id
    payload_to_kg = args_to_kg_update_note[1] # note_data dict
    assert payload_to_kg['title'] == "Updated Title"
    assert payload_to_kg['content'] == "Updated Content"
    assert 'updated_at' in payload_to_kg # Service adds this
    assert 'id' not in payload_to_kg # ID is passed separately to kg.update_note

    # get_note is called by the service at the end to return the Note object
    mock_kg.get_note.assert_called_with(note_id)


def test_delete_note(note_service, mock_kg):
    note_id = "note_to_delete"
    mock_kg.delete_note.return_value = True

    result = note_service.delete_note(note_id)

    assert result is True
    mock_kg.delete_note.assert_called_with(note_id)
