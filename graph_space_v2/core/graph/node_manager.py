from typing import Dict, List, Any, Optional, Set, Union
from datetime import datetime
import uuid

from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph
from graph_space_v2.core.models.note import Note
from graph_space_v2.core.models.task import Task
from graph_space_v2.core.models.contact import Contact
from graph_space_v2.utils.errors.exceptions import EntityNotFoundError


class NodeManager:
    """Manager class for creating and manipulating nodes in the knowledge graph."""

    def __init__(self, knowledge_graph: KnowledgeGraph):
        """
        Initialize the NodeManager.

        Args:
            knowledge_graph: The knowledge graph instance to manage
        """
        self.knowledge_graph = knowledge_graph

    def create_node(self, entity_type: str, data: Dict[str, Any]) -> str:
        """
        Create a new node in the knowledge graph.

        Args:
            entity_type: Type of entity ('note', 'task', 'contact')
            data: Entity data

        Returns:
            ID of the new entity
        """
        if entity_type == 'note':
            return self.knowledge_graph.add_note(data)
        elif entity_type == 'task':
            return self.knowledge_graph.add_task(data)
        elif entity_type == 'contact':
            return self.knowledge_graph.add_contact(data)
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")

    def update_node(self, entity_type: str, entity_id: str, data: Dict[str, Any]) -> bool:
        """
        Update an existing node in the knowledge graph.

        Args:
            entity_type: Type of entity ('note', 'task', 'contact')
            entity_id: ID of the entity to update
            data: Updated entity data

        Returns:
            True if the entity was updated, False otherwise
        """
        if entity_type == 'note':
            return self.knowledge_graph.update_note(entity_id, data)
        elif entity_type == 'task':
            return self.knowledge_graph.update_task(entity_id, data)
        elif entity_type == 'contact':
            return self.update_contact(entity_id, data)
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")

    def delete_node(self, entity_type: str, entity_id: str) -> bool:
        """
        Delete a node from the knowledge graph.

        Args:
            entity_type: Type of entity ('note', 'task', 'contact')
            entity_id: ID of the entity to delete

        Returns:
            True if the entity was deleted, False otherwise
        """
        if entity_type == 'note':
            return self.knowledge_graph.delete_note(entity_id)
        elif entity_type == 'task':
            return self.knowledge_graph.delete_task(entity_id)
        elif entity_type == 'contact':
            return self.delete_contact(entity_id)
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")

    def get_node(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a node from the knowledge graph.

        Args:
            entity_type: Type of entity ('note', 'task', 'contact')
            entity_id: ID of the entity to retrieve

        Returns:
            Entity data or None if not found
        """
        if entity_type == 'note':
            return self.knowledge_graph.get_note(entity_id)
        elif entity_type == 'task':
            return self.knowledge_graph.get_task(entity_id)
        elif entity_type == 'contact':
            return self.get_contact(entity_id)
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")

    def get_nodes_by_type(self, entity_type: str) -> List[Dict[str, Any]]:
        """
        Get all nodes of a specific type.

        Args:
            entity_type: Type of entity ('note', 'task', 'contact')

        Returns:
            List of entities of the specified type
        """
        if entity_type == 'note':
            return self.knowledge_graph.data.get("notes", [])
        elif entity_type == 'task':
            return self.knowledge_graph.data.get("tasks", [])
        elif entity_type == 'contact':
            return self.knowledge_graph.data.get("contacts", [])
        else:
            raise ValueError(f"Unknown entity type: {entity_type}")

    def add_tag_to_node(self, entity_type: str, entity_id: str, tag: str) -> bool:
        """
        Add a tag to an entity.

        Args:
            entity_type: Type of entity ('note', 'task', 'contact')
            entity_id: ID of the entity
            tag: Tag to add

        Returns:
            True if the tag was added, False otherwise
        """
        entity = self.get_node(entity_type, entity_id)
        if not entity:
            return False

        # Add tag if not already present
        tags = entity.get('tags', [])
        if tag not in tags:
            tags.append(tag)
            entity['tags'] = tags

            # Update the entity
            return self.update_node(entity_type, entity_id, {'tags': tags})

        return True  # Tag was already present

    def remove_tag_from_node(self, entity_type: str, entity_id: str, tag: str) -> bool:
        """
        Remove a tag from an entity.

        Args:
            entity_type: Type of entity ('note', 'task', 'contact')
            entity_id: ID of the entity
            tag: Tag to remove

        Returns:
            True if the tag was removed, False otherwise
        """
        entity = self.get_node(entity_type, entity_id)
        if not entity:
            return False

        # Remove tag if present
        tags = entity.get('tags', [])
        if tag in tags:
            tags.remove(tag)
            entity['tags'] = tags

            # Update the entity
            return self.update_node(entity_type, entity_id, {'tags': tags})

        return True  # Tag was not present

    def create_relationship(self, source_type: str, source_id: str, target_type: str, target_id: str, relationship_type: str, attributes: Optional[Dict[str, Any]] = None) -> bool:
        """
        Create a relationship between two entities.

        Args:
            source_type: Type of source entity
            source_id: ID of source entity
            target_type: Type of target entity
            target_id: ID of target entity
            relationship_type: Type of relationship
            attributes: Additional relationship attributes

        Returns:
            True if the relationship was created, False otherwise
        """
        # Check if both entities exist
        source = self.get_node(source_type, source_id)
        target = self.get_node(target_type, target_id)

        if not source or not target:
            return False

        # Create the relationship by adding metadata that will be processed
        # when the graph is rebuilt
        source_node_id = f"{source_type}_{source_id}"
        target_node_id = f"{target_type}_{target_id}"

        # Add the relationship to the graph
        attributes = attributes or {}
        attributes['relationship'] = relationship_type

        try:
            self.knowledge_graph.graph.add_edge(
                source_node_id, target_node_id, **attributes)
            return True
        except Exception:
            return False

    def delete_relationship(self, source_type: str, source_id: str, target_type: str, target_id: str) -> bool:
        """
        Delete a relationship between two entities.

        Args:
            source_type: Type of source entity
            source_id: ID of source entity
            target_type: Type of target entity
            target_id: ID of target entity

        Returns:
            True if the relationship was deleted, False otherwise
        """
        source_node_id = f"{source_type}_{source_id}"
        target_node_id = f"{target_type}_{target_id}"

        try:
            self.knowledge_graph.graph.remove_edge(
                source_node_id, target_node_id)
            return True
        except Exception:
            return False

    def get_related_nodes(self, entity_type: str, entity_id: str, relationship_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get nodes related to a specific entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of entity
            relationship_type: Type of relationship to filter by (optional)

        Returns:
            List of related entities with relationship information
        """
        return self.knowledge_graph.get_related_entities(entity_id, entity_type, relationship_type)

    # Contact-specific methods (example of specialized methods for an entity type)
    def update_contact(self, contact_id: str, data: Dict[str, Any]) -> bool:
        """
        Update a contact in the knowledge graph.

        Args:
            contact_id: ID of the contact to update
            data: Updated contact data

        Returns:
            True if the contact was updated, False otherwise
        """
        for i, contact in enumerate(self.knowledge_graph.data["contacts"]):
            if contact.get("id") == contact_id:
                # Update the contact
                for key, value in data.items():
                    contact[key] = value

                # Update timestamp
                contact["updated_at"] = datetime.now().isoformat()

                # Update data structure
                self.knowledge_graph.data["contacts"][i] = contact

                # Rebuild graph
                self.knowledge_graph.build_graph()

                # Save data
                self.knowledge_graph.save_data()

                return True

        return False

    def delete_contact(self, contact_id: str) -> bool:
        """
        Delete a contact from the knowledge graph.

        Args:
            contact_id: ID of the contact to delete

        Returns:
            True if the contact was deleted, False otherwise
        """
        for i, contact in enumerate(self.knowledge_graph.data["contacts"]):
            if contact.get("id") == contact_id:
                # Remove from data structure
                self.knowledge_graph.data["contacts"].pop(i)

                # Rebuild graph
                self.knowledge_graph.build_graph()

                # Save data
                self.knowledge_graph.save_data()

                return True

        return False

    def get_contact(self, contact_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a contact by ID.

        Args:
            contact_id: ID of the contact to retrieve

        Returns:
            Contact data or None if not found
        """
        for contact in self.knowledge_graph.data["contacts"]:
            if contact.get("id") == contact_id:
                return contact

        return None
