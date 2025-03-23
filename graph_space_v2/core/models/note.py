from typing import Dict, Any, List, Optional, Set, ClassVar
from datetime import datetime
from graph_space_v2.core.models.base import BaseModel


class Note(BaseModel):
    """Model representing a note in the system."""

    # Add note-specific fields to the serializable fields
    fields: ClassVar[Set[str]] = BaseModel.fields.union({
        'title', 'content', 'tags', 'source', 'metadata'
    })

    def __init__(
        self,
        id: Optional[str] = None,
        title: str = "Untitled Note",
        content: str = "",
        tags: Optional[List[str]] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        source: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Initialize a Note.

        Args:
            id: Unique identifier
            title: Note title
            content: Note content
            tags: List of tags
            created_at: Creation timestamp
            updated_at: Last update timestamp
            source: Source information (e.g., document, web page)
            metadata: Additional metadata
            **kwargs: Additional attributes
        """
        super().__init__(
            id=id,
            created_at=created_at,
            updated_at=updated_at,
            **kwargs
        )
        self.title = title
        self.content = content
        self.tags = tags or []
        self.source = source or {}
        self.metadata = metadata or {}

    def update(self, data: Dict[str, Any]) -> None:
        """
        Update note with new data.

        Args:
            data: Dictionary containing fields to update
        """
        # Update fields from data
        if 'title' in data:
            self.title = data['title']
        if 'content' in data:
            self.content = data['content']
        if 'tags' in data:
            self.tags = data['tags']
        if 'source' in data:
            self.source = data['source']
        if 'metadata' in data:
            self.metadata = data['metadata']

        # Always update the updated_at timestamp
        self.updated_at = datetime.now().isoformat()

    def add_tag(self, tag: str) -> None:
        """
        Add a tag to the note.

        Args:
            tag: Tag to add
        """
        if tag not in self.tags:
            self.tags.append(tag)
            self.updated_at = datetime.now().isoformat()

    def remove_tag(self, tag: str) -> None:
        """
        Remove a tag from the note.

        Args:
            tag: Tag to remove
        """
        if tag in self.tags:
            self.tags.remove(tag)
            self.updated_at = datetime.now().isoformat()

    def is_empty(self) -> bool:
        """
        Check if the note is empty.

        Returns:
            True if the note is empty, False otherwise
        """
        return not bool(self.content.strip())

    @staticmethod
    def from_text(text: str, title: Optional[str] = None) -> 'Note':
        """
        Create a note from plain text.

        Args:
            text: Text content
            title: Optional title (generated from text if not provided)

        Returns:
            Note instance
        """
        # Generate title from first line if not provided
        if title is None:
            first_line = text.split('\n', 1)[0].strip()
            title = first_line[:50] + ('...' if len(first_line) > 50 else '')

        return Note(
            title=title,
            content=text,
            created_at=datetime.now().isoformat()
        )
