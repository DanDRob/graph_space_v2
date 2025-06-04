import pytest
from datetime import datetime
from graph_space_v2.core.models.note import Note

def test_note_creation_minimal():
    note = Note(content="Test content")
    assert note.content == "Test content"
    assert note.title == "Untitled Note"  # Default title
    assert note.tags == []
    # attachments, category, related_notes do not exist on the model
    assert note.id is not None
    assert isinstance(note.created_at, str) # Dates are strings
    assert isinstance(note.updated_at, str) # Dates are strings

def test_note_creation_full():
    now_iso = datetime.now().isoformat()
    note = Note(
        id="custom_id",
        title="Test Title",
        content="Detailed test content.",
        tags=["tag1", "tag2"],
        # attachments, category, related_notes do not exist
        created_at=now_iso,
        updated_at=now_iso
    )
    assert note.id == "custom_id"
    assert note.title == "Test Title"
    assert note.content == "Detailed test content."
    assert note.tags == ["tag1", "tag2"]
    assert note.created_at == now_iso
    assert note.updated_at == now_iso

def test_note_to_dict():
    note = Note(title="Dict Test", content="Content for dict")
    note_dict = note.to_dict()
    assert note_dict['id'] == note.id
    assert note_dict['title'] == "Dict Test"
    assert note_dict['content'] == "Content for dict"
    assert 'created_at' in note_dict
    assert 'updated_at' in note_dict

def test_note_from_dict():
    data = {
        "id": "dict_id_123",
        "title": "From Dict",
        "content": "Loaded from a dictionary.",
        "tags": ["dict_tag"],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    note = Note.from_dict(data)
    assert note.id == "dict_id_123"
    assert note.title == "From Dict"
    assert note.content == "Loaded from a dictionary."
    assert note.tags == ["dict_tag"]
    assert isinstance(note.created_at, str) # Dates are strings
    assert isinstance(note.updated_at, str) # Dates are strings

def test_note_update_content():
    note = Note(content="Initial content")
    original_updated_at = datetime.fromisoformat(note.updated_at)
    # Ensure some time passes for updated_at to change
    import time; time.sleep(0.001)
    note.update({'content': "Updated content"}) # Use the update method
    assert note.content == "Updated content"
    assert datetime.fromisoformat(note.updated_at) > original_updated_at

# Test for default values when no content/title is provided
def test_note_creation_empty():
    # Note() is allowed, content defaults to "", title to "Untitled Note"
    note = Note()
    assert note.content == ""
    assert note.title == "Untitled Note"
