from typing import Dict, Any, List, Optional, Set, ClassVar
from datetime import datetime
from graph_space_v2.core.models.base import BaseModel


class Contact(BaseModel):
    """Model representing a contact in the system."""

    # Add contact-specific fields to the serializable fields
    fields: ClassVar[Set[str]] = BaseModel.fields.union({
        'name', 'email', 'phone', 'organization', 'tags', 'addresses',
        'social_profiles', 'metadata'
    })

    def __init__(
        self,
        id: Optional[str] = None,
        name: str = "",
        email: str = "",
        phone: str = "",
        organization: str = "",
        tags: Optional[List[str]] = None,
        addresses: Optional[List[Dict[str, str]]] = None,
        social_profiles: Optional[Dict[str, str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize a Contact.

        Args:
            id: Unique identifier
            name: Contact name
            email: Contact email
            phone: Contact phone number
            organization: Organization name
            tags: List of tags
            addresses: List of address dictionaries
            social_profiles: Dictionary of social profile links
            metadata: Additional metadata
            created_at: Creation timestamp
            updated_at: Last update timestamp
            **kwargs: Additional attributes
        """
        super().__init__(
            id=id,
            created_at=created_at,
            updated_at=updated_at,
            **kwargs
        )
        self.name = name
        self.email = email
        self.phone = phone
        self.organization = organization
        self.tags = tags or []
        self.addresses = addresses or []
        self.social_profiles = social_profiles or {}
        self.metadata = metadata or {}

    def update(self, data: Dict[str, Any]) -> None:
        """
        Update contact with new data.

        Args:
            data: Dictionary containing fields to update
        """
        # Update fields from data
        if 'name' in data:
            self.name = data['name']
        if 'email' in data:
            self.email = data['email']
        if 'phone' in data:
            self.phone = data['phone']
        if 'organization' in data:
            self.organization = data['organization']
        if 'tags' in data:
            self.tags = data['tags']
        if 'addresses' in data:
            self.addresses = data['addresses']
        if 'social_profiles' in data:
            self.social_profiles = data['social_profiles']
        if 'metadata' in data:
            self.metadata = data['metadata']

        # Always update the updated_at timestamp
        self.updated_at = datetime.now().isoformat()

    def add_tag(self, tag: str) -> None:
        """
        Add a tag to the contact.

        Args:
            tag: Tag to add
        """
        if tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.now().isoformat()

    def remove_tag(self, tag: str) -> None:
        """
        Remove a tag from the contact.

        Args:
            tag: Tag to remove
        """
        if tag in self.tags:
            self.tags.remove(tag)
            self.updated_at = datetime.now().isoformat()

    def add_address(self, address_type: str, address: str) -> None:
        """
        Add an address to the contact.

        Args:
            address_type: Type of address (e.g., home, work)
            address: Address text
        """
        self.addresses.append({
            'type': address_type,
            'address': address
        })
        self.updated_at = datetime.now().isoformat()

    def add_social_profile(self, platform: str, url: str) -> None:
        """
        Add a social profile to the contact.

        Args:
            platform: Social platform name (e.g., linkedin, twitter)
            url: Profile URL
        """
        self.social_profiles[platform] = url
        self.updated_at = datetime.now().isoformat()

    def get_full_name(self) -> str:
        """
        Get the contact's full name.

        Returns:
            Full name
        """
        return self.name.strip()

    @staticmethod
    def from_email(email: str, name: Optional[str] = None) -> 'Contact':
        """
        Create a contact from an email address.

        Args:
            email: Email address
            name: Optional name (derived from email if not provided)

        Returns:
            Contact instance
        """
        if not name and '@' in email:
            # Try to derive a name from the email address
            name = email.split('@')[0].replace('.', ' ').title()

        return Contact(
            name=name or "",
            email=email,
            created_at=datetime.now().isoformat()
        )
