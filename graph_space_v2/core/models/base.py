from typing import Dict, Any, List, Optional, Set, ClassVar
import uuid
from datetime import datetime
import json


class BaseModel:
    """Base class for all models in the system."""

    # Fields that should be included in serialization
    fields: ClassVar[Set[str]] = {'id', 'created_at', 'updated_at'}

    def __init__(
        self,
        id: Optional[str] = None,
        created_at: Optional[str] = None,
        updated_at: Optional[str] = None,
        **kwargs
    ):
        """
        Initialize the base model.

        Args:
            id: Unique identifier
            created_at: Creation timestamp
            updated_at: Last update timestamp
            **kwargs: Additional attributes
        """
        self.id = id or str(uuid.uuid4())
        self.created_at = created_at or datetime.now().isoformat()
        self.updated_at = updated_at or self.created_at

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the model to a dictionary.

        Returns:
            Dictionary representation of the model
        """
        return {
            field: getattr(self, field)
            for field in self.fields
            if hasattr(self, field)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaseModel':
        """
        Create a model instance from a dictionary.

        Args:
            data: Dictionary containing model attributes

        Returns:
            Model instance
        """
        # Create a shallow copy to avoid modifying the original
        data_copy = data.copy()
        return cls(**data_copy)

    def to_json(self) -> str:
        """
        Convert the model to a JSON string.

        Returns:
            JSON string representation of the model
        """
        return json.dumps(self.to_dict())

    @classmethod
    def from_json(cls, json_str: str) -> 'BaseModel':
        """
        Create a model instance from a JSON string.

        Args:
            json_str: JSON string containing model attributes

        Returns:
            Model instance
        """
        data = json.loads(json_str)
        return cls.from_dict(data)

    def __eq__(self, other: Any) -> bool:
        """
        Check if two models are equal.

        Args:
            other: Other object to compare with

        Returns:
            True if the models are equal, False otherwise
        """
        if not isinstance(other, BaseModel):
            return False
        return self.id == other.id

    def __repr__(self) -> str:
        """
        Get string representation of the model.

        Returns:
            String representation
        """
        attrs = []
        for field in self.fields:
            if hasattr(self, field):
                value = getattr(self, field)
                if isinstance(value, str):
                    # Truncate long strings
                    if len(value) > 50:
                        value = value[:47] + "..."
                attrs.append(f"{field}={value!r}")

        return f"{self.__class__.__name__}({', '.join(attrs)})"
