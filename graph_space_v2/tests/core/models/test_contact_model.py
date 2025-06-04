import pytest
from datetime import datetime
from graph_space_v2.core.models.contact import Contact

def test_contact_creation_minimal():
    # Assuming name is the minimal requirement
    contact = Contact(name="Minimal Contact")
    assert contact.name == "Minimal Contact"
    assert contact.email == ""  # Defaults to empty string
    assert contact.phone == ""  # Defaults to empty string
    assert contact.organization == ""  # Defaults to empty string
    assert contact.id is not None
    assert isinstance(contact.created_at, str) # Dates are strings
    assert isinstance(contact.updated_at, str) # Dates are strings

def test_contact_creation_full():
    now_iso = datetime.now().isoformat()
    sample_addresses = [{"type": "home", "address": "123 Main St"}]
    contact = Contact(
        id="contact_custom_id",
        name="Full Name Contact",
        email="test@example.com",
        phone="123-456-7890",
        organization="Test Inc.",
        addresses=sample_addresses, # Correct attribute name and type
        # notes attribute does not exist
        tags=["friend", "work"],
        created_at=now_iso,
        updated_at=now_iso
    )
    assert contact.id == "contact_custom_id"
    assert contact.name == "Full Name Contact"
    assert contact.email == "test@example.com"
    assert contact.phone == "123-456-7890"
    assert contact.organization == "Test Inc."
    assert contact.addresses == sample_addresses
    assert contact.tags == ["friend", "work"]

def test_contact_to_dict():
    contact = Contact(name="To Dict Contact", email="dict@example.com")
    contact_dict = contact.to_dict()
    assert contact_dict['id'] == contact.id
    assert contact_dict['name'] == "To Dict Contact"
    assert contact_dict['email'] == "dict@example.com"
    assert 'created_at' in contact_dict

def test_contact_from_dict():
    data = {
        "id": "contact_dict_id",
        "name": "From Dict Contact",
        "email": "fromdict@example.com",
        "organization": "Dict Corp",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    contact = Contact.from_dict(data)
    assert contact.id == "contact_dict_id"
    assert contact.name == "From Dict Contact"
    assert contact.email == "fromdict@example.com"
    assert contact.organization == "Dict Corp"
    assert isinstance(contact.created_at, str) # Dates are strings
    assert isinstance(contact.updated_at, str) # Dates are strings

# Test for default values when no name is provided
def test_contact_creation_empty():
    # Contact() is allowed, name defaults to ""
    contact = Contact()
    assert contact.name == ""
