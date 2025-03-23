from typing import Dict, List, Any, Optional, Set, Union, Tuple
from datetime import datetime

from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph
from graph_space_v2.utils.errors.exceptions import EntityNotFoundError


class Relationship:
    """Class representing a relationship between two entities in the knowledge graph."""

    def __init__(
        self,
        source_type: str,
        source_id: str,
        target_type: str,
        target_id: str,
        relationship_type: str,
        weight: float = 1.0,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a relationship.

        Args:
            source_type: Type of source entity ('note', 'task', 'contact')
            source_id: ID of source entity
            target_type: Type of target entity ('note', 'task', 'contact')
            target_id: ID of target entity
            relationship_type: Type of relationship (e.g., 'shared_tags', 'mention')
            weight: Relationship weight/strength
            attributes: Additional relationship attributes
        """
        self.source_type = source_type
        self.source_id = source_id
        self.target_type = target_type
        self.target_id = target_id
        self.relationship_type = relationship_type
        self.weight = weight
        self.attributes = attributes or {}

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the relationship to a dictionary.

        Returns:
            Dictionary representation of the relationship
        """
        return {
            'source_type': self.source_type,
            'source_id': self.source_id,
            'target_type': self.target_type,
            'target_id': self.target_id,
            'relationship_type': self.relationship_type,
            'weight': self.weight,
            'attributes': self.attributes
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Relationship':
        """
        Create a relationship from a dictionary.

        Args:
            data: Dictionary containing relationship data

        Returns:
            Relationship instance
        """
        return cls(
            source_type=data['source_type'],
            source_id=data['source_id'],
            target_type=data['target_type'],
            target_id=data['target_id'],
            relationship_type=data['relationship_type'],
            weight=data.get('weight', 1.0),
            attributes=data.get('attributes', {})
        )

    def __eq__(self, other: Any) -> bool:
        """
        Check if two relationships are equal.

        Args:
            other: Other object to compare with

        Returns:
            True if the relationships are equal, False otherwise
        """
        if not isinstance(other, Relationship):
            return False

        return (
            self.source_type == other.source_type and
            self.source_id == other.source_id and
            self.target_type == other.target_type and
            self.target_id == other.target_id and
            self.relationship_type == other.relationship_type
        )

    def __repr__(self) -> str:
        """
        Get string representation of the relationship.

        Returns:
            String representation
        """
        return (
            f"Relationship({self.source_type}:{self.source_id} --[{self.relationship_type}]--> "
            f"{self.target_type}:{self.target_id})"
        )


class RelationshipManager:
    """Manager class for creating and manipulating relationships in the knowledge graph."""

    RELATIONSHIP_TYPES = {
        'shared_tags',      # Entities share one or more tags
        'mention',          # Entity mentions another entity
        'reference',        # Entity references another entity
        'parent_child',     # Hierarchical relationship
        'dependency',       # Entity depends on another entity
        'same_project',     # Entities belong to the same project
        'same_organization',  # Entities belong to the same organization
        'collaboration',    # Entities collaborate with each other
        'temporal',         # Temporal relationship (before, after, during)
        'semantic',         # Semantic similarity relationship
        'custom'            # Custom relationship type
    }

    def __init__(self, knowledge_graph: KnowledgeGraph):
        """
        Initialize the RelationshipManager.

        Args:
            knowledge_graph: The knowledge graph instance to manage
        """
        self.knowledge_graph = knowledge_graph

    def create_relationship(self, relationship: Relationship) -> bool:
        """
        Create a relationship between two entities.

        Args:
            relationship: Relationship to create

        Returns:
            True if the relationship was created, False otherwise
        """
        source_node_id = f"{relationship.source_type}_{relationship.source_id}"
        target_node_id = f"{relationship.target_type}_{relationship.target_id}"

        # Check if both entities exist
        if (source_node_id not in self.knowledge_graph.graph or
                target_node_id not in self.knowledge_graph.graph):
            return False

        # Create attributes dictionary for the edge
        edge_attrs = {
            'relationship': relationship.relationship_type,
            'weight': relationship.weight
        }

        # Add additional attributes
        for key, value in relationship.attributes.items():
            edge_attrs[key] = value

        # Add the edge to the graph
        self.knowledge_graph.graph.add_edge(
            source_node_id, target_node_id, **edge_attrs)

        return True

    def delete_relationship(self, relationship: Relationship) -> bool:
        """
        Delete a relationship between two entities.

        Args:
            relationship: Relationship to delete

        Returns:
            True if the relationship was deleted, False otherwise
        """
        source_node_id = f"{relationship.source_type}_{relationship.source_id}"
        target_node_id = f"{relationship.target_type}_{relationship.target_id}"

        try:
            self.knowledge_graph.graph.remove_edge(
                source_node_id, target_node_id)
            return True
        except Exception:
            return False

    def get_relationship(self, source_type: str, source_id: str, target_type: str, target_id: str) -> Optional[Relationship]:
        """
        Get a relationship between two entities.

        Args:
            source_type: Type of source entity
            source_id: ID of source entity
            target_type: Type of target entity
            target_id: ID of target entity

        Returns:
            Relationship or None if not found
        """
        source_node_id = f"{source_type}_{source_id}"
        target_node_id = f"{target_type}_{target_id}"

        if not self.knowledge_graph.graph.has_edge(source_node_id, target_node_id):
            return None

        edge_data = self.knowledge_graph.graph.get_edge_data(
            source_node_id, target_node_id)
        relationship_type = edge_data.get('relationship', 'custom')
        weight = edge_data.get('weight', 1.0)

        # Extract other attributes
        attributes = {k: v for k, v in edge_data.items() if k not in [
            'relationship', 'weight']}

        return Relationship(
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relationship_type=relationship_type,
            weight=weight,
            attributes=attributes
        )

    def update_relationship(self, relationship: Relationship) -> bool:
        """
        Update a relationship between two entities.

        Args:
            relationship: Updated relationship

        Returns:
            True if the relationship was updated, False otherwise
        """
        # Delete the existing relationship
        if not self.delete_relationship(relationship):
            return False

        # Create a new relationship with updated attributes
        return self.create_relationship(relationship)

    def get_relationships_by_entity(self, entity_type: str, entity_id: str) -> List[Relationship]:
        """
        Get all relationships involving a specific entity.

        Args:
            entity_type: Type of entity
            entity_id: ID of entity

        Returns:
            List of relationships
        """
        node_id = f"{entity_type}_{entity_id}"

        if node_id not in self.knowledge_graph.graph:
            raise EntityNotFoundError(
                f"Entity {entity_type} with ID {entity_id} not found")

        relationships = []

        # Get outgoing relationships (where entity is the source)
        for neighbor in self.knowledge_graph.graph.neighbors(node_id):
            edge_data = self.knowledge_graph.graph.get_edge_data(
                node_id, neighbor)
            neighbor_type, neighbor_id = neighbor.split('_', 1)

            relationship_type = edge_data.get('relationship', 'custom')
            weight = edge_data.get('weight', 1.0)

            # Extract other attributes
            attributes = {k: v for k, v in edge_data.items() if k not in [
                'relationship', 'weight']}

            relationships.append(Relationship(
                source_type=entity_type,
                source_id=entity_id,
                target_type=neighbor_type,
                target_id=neighbor_id,
                relationship_type=relationship_type,
                weight=weight,
                attributes=attributes
            ))

        return relationships

    def get_relationships_by_type(self, relationship_type: str) -> List[Relationship]:
        """
        Get all relationships of a specific type.

        Args:
            relationship_type: Type of relationship

        Returns:
            List of relationships
        """
        relationships = []

        for source, target, edge_data in self.knowledge_graph.graph.edges(data=True):
            if edge_data.get('relationship') == relationship_type:
                source_type, source_id = source.split('_', 1)
                target_type, target_id = target.split('_', 1)
                weight = edge_data.get('weight', 1.0)

                # Extract other attributes
                attributes = {k: v for k, v in edge_data.items() if k not in [
                    'relationship', 'weight']}

                relationships.append(Relationship(
                    source_type=source_type,
                    source_id=source_id,
                    target_type=target_type,
                    target_id=target_id,
                    relationship_type=relationship_type,
                    weight=weight,
                    attributes=attributes
                ))

        return relationships

    def create_bidirectional_relationship(self, source_type: str, source_id: str, target_type: str, target_id: str, relationship_type: str, weight: float = 1.0, attributes: Optional[Dict[str, Any]] = None) -> Tuple[bool, bool]:
        """
        Create bidirectional relationships between two entities.

        Args:
            source_type: Type of source entity
            source_id: ID of source entity
            target_type: Type of target entity
            target_id: ID of target entity
            relationship_type: Type of relationship
            weight: Relationship weight/strength
            attributes: Additional relationship attributes

        Returns:
            Tuple of (source_to_target_success, target_to_source_success)
        """
        attributes = attributes or {}

        # Create source to target relationship
        source_to_target = Relationship(
            source_type=source_type,
            source_id=source_id,
            target_type=target_type,
            target_id=target_id,
            relationship_type=relationship_type,
            weight=weight,
            attributes=attributes
        )
        source_to_target_success = self.create_relationship(source_to_target)

        # Create target to source relationship
        target_to_source = Relationship(
            source_type=target_type,
            source_id=target_id,
            target_type=source_type,
            target_id=source_id,
            relationship_type=relationship_type,
            weight=weight,
            attributes=attributes
        )
        target_to_source_success = self.create_relationship(target_to_source)

        return (source_to_target_success, target_to_source_success)
