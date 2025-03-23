import json
import os
import networkx as nx
import numpy as np
from typing import Dict, List, Any, Optional, Set, Tuple, Union
from datetime import datetime

from graph_space_v2.utils.errors.exceptions import KnowledgeGraphError, EntityNotFoundError
from graph_space_v2.core.models.note import Note
from graph_space_v2.core.models.task import Task
from graph_space_v2.core.models.contact import Contact
from graph_space_v2.utils.helpers.path_utils import get_user_data_path, ensure_dir_exists


class KnowledgeGraph:
    """Core knowledge graph for storing and connecting entities."""

    def __init__(self, data_path: str):
        """
        Initialize the knowledge graph.

        Args:
            data_path: Path to the JSON file containing user data.
        """
        self.data_path = data_path
        self.graph = nx.Graph()
        self.node_embeddings = {}
        self.data = self._load_data()
        self.build_graph()

    def _load_data(self) -> Dict:
        """
        Load data from the JSON file. If the file doesn't exist or is empty,
        return an empty data structure.

        Returns:
            Dict containing the loaded data.
        """
        if not os.path.exists(self.data_path):
            # Create directory if it doesn't exist
            ensure_dir_exists(os.path.dirname(self.data_path))
            # Create empty data structure
            empty_data = {
                "notes": [],
                "tasks": [],
                "contacts": []
            }
            # Save the empty structure
            with open(self.data_path, 'w') as f:
                json.dump(empty_data, f)
            return empty_data

        try:
            with open(self.data_path, 'r') as f:
                data = json.load(f)
                # Ensure all required keys exist
                for key in ["notes", "tasks", "contacts"]:
                    if key not in data:
                        data[key] = []
                return data
        except json.JSONDecodeError:
            # Handle case where file exists but is empty or invalid
            return {"notes": [], "tasks": [], "contacts": []}

    def save_data(self):
        """Save the current data back to the JSON file."""
        with open(self.data_path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def build_graph(self):
        """
        Build the knowledge graph from the loaded data.
        Create nodes for all entities and edges based on relationships.
        """
        # Clear existing graph
        self.graph.clear()

        # Add nodes for each entity type
        self._add_nodes_from_data()

        # Add edges based on relationships
        self._add_edges_for_notes()
        self._add_edges_for_tasks()
        self._add_edges_for_contacts()
        self._add_cross_entity_edges()

    def _add_nodes_from_data(self):
        """Add nodes to the graph for all entities in the data."""
        # Add notes
        for note_data in self.data.get("notes", []):
            node_id = f"note_{note_data.get('id')}"
            self.graph.add_node(
                node_id,
                type="note",
                data=note_data,
                title=note_data.get("title", ""),
                content=note_data.get("content", ""),
                tags=note_data.get("tags", []),
                created_at=note_data.get("created_at", ""),
                updated_at=note_data.get("updated_at", "")
            )

        # Add tasks
        for task_data in self.data.get("tasks", []):
            node_id = f"task_{task_data.get('id')}"
            self.graph.add_node(
                node_id,
                type="task",
                data=task_data,
                title=task_data.get("title", ""),
                description=task_data.get("description", ""),
                status=task_data.get("status", ""),
                due_date=task_data.get("due_date", ""),
                tags=task_data.get("tags", []),
                project=task_data.get("project", "")
            )

        # Add contacts
        for contact_data in self.data.get("contacts", []):
            node_id = f"contact_{contact_data.get('id')}"
            self.graph.add_node(
                node_id,
                type="contact",
                data=contact_data,
                name=contact_data.get("name", ""),
                email=contact_data.get("email", ""),
                phone=contact_data.get("phone", ""),
                organization=contact_data.get("organization", ""),
                tags=contact_data.get("tags", [])
            )

    def _add_edges_for_notes(self):
        """Add edges between notes based on shared tags and other relationships."""
        notes_nodes = [n for n, attr in self.graph.nodes(
            data=True) if attr["type"] == "note"]

        # Connect notes that share tags
        for i, node1 in enumerate(notes_nodes):
            for node2 in notes_nodes[i+1:]:
                node1_tags = set(self.graph.nodes[node1].get("tags", []))
                node2_tags = set(self.graph.nodes[node2].get("tags", []))

                # If they share tags, add an edge
                shared_tags = node1_tags.intersection(node2_tags)
                if shared_tags:
                    self.graph.add_edge(
                        node1, node2,
                        relationship="shared_tags",
                        shared_tags=list(shared_tags),
                        weight=len(shared_tags)
                    )

    def _add_edges_for_tasks(self):
        """Add edges between tasks based on shared projects, tags, etc."""
        tasks_nodes = [n for n, attr in self.graph.nodes(
            data=True) if attr["type"] == "task"]

        # Connect tasks that share projects or tags
        for i, node1 in enumerate(tasks_nodes):
            for node2 in tasks_nodes[i+1:]:
                node1_data = self.graph.nodes[node1]
                node2_data = self.graph.nodes[node2]

                # Connect by project
                if (node1_data.get("project") and
                        node1_data.get("project") == node2_data.get("project")):
                    self.graph.add_edge(
                        node1, node2,
                        relationship="same_project",
                        project=node1_data.get("project"),
                        weight=1.0
                    )

                # Connect by shared tags
                node1_tags = set(node1_data.get("tags", []))
                node2_tags = set(node2_data.get("tags", []))
                shared_tags = node1_tags.intersection(node2_tags)

                if shared_tags:
                    self.graph.add_edge(
                        node1, node2,
                        relationship="shared_tags",
                        shared_tags=list(shared_tags),
                        weight=len(shared_tags)
                    )

    def _add_edges_for_contacts(self):
        """Add edges between contacts based on shared organizations, tags, etc."""
        contacts_nodes = [n for n, attr in self.graph.nodes(
            data=True) if attr["type"] == "contact"]

        # Connect contacts in the same organization
        for i, node1 in enumerate(contacts_nodes):
            for node2 in contacts_nodes[i+1:]:
                node1_data = self.graph.nodes[node1]
                node2_data = self.graph.nodes[node2]

                # Connect by organization
                if (node1_data.get("organization") and
                        node1_data.get("organization") == node2_data.get("organization")):
                    self.graph.add_edge(
                        node1, node2,
                        relationship="same_organization",
                        organization=node1_data.get("organization"),
                        weight=1.0
                    )

                # Connect by shared tags
                node1_tags = set(node1_data.get("tags", []))
                node2_tags = set(node2_data.get("tags", []))
                shared_tags = node1_tags.intersection(node2_tags)

                if shared_tags:
                    self.graph.add_edge(
                        node1, node2,
                        relationship="shared_tags",
                        shared_tags=list(shared_tags),
                        weight=len(shared_tags)
                    )

    def _add_cross_entity_edges(self):
        """Add edges between different entity types based on relationships."""
        # Connect notes to tasks by tags or mentions
        for note_node in [n for n, attr in self.graph.nodes(data=True) if attr["type"] == "note"]:
            note_data = self.graph.nodes[note_node]
            note_tags = set(note_data.get("tags", []))
            note_content = note_data.get("content", "").lower()

            # Connect notes to tasks
            for task_node in [n for n, attr in self.graph.nodes(data=True) if attr["type"] == "task"]:
                task_data = self.graph.nodes[task_node]
                task_tags = set(task_data.get("tags", []))

                # Connect by shared tags
                shared_tags = note_tags.intersection(task_tags)
                if shared_tags:
                    self.graph.add_edge(
                        note_node, task_node,
                        relationship="shared_tags",
                        shared_tags=list(shared_tags),
                        weight=len(shared_tags)
                    )

                # Connect if task title is mentioned in note
                task_title = task_data.get("title", "").lower()
                if task_title and task_title in note_content:
                    self.graph.add_edge(
                        note_node, task_node,
                        relationship="mention",
                        weight=1.0
                    )

            # Connect notes to contacts
            for contact_node in [n for n, attr in self.graph.nodes(data=True) if attr["type"] == "contact"]:
                contact_data = self.graph.nodes[contact_node]
                contact_name = contact_data.get("name", "").lower()

                # Connect if contact name is mentioned in note
                if contact_name and contact_name in note_content:
                    self.graph.add_edge(
                        note_node, contact_node,
                        relationship="mention",
                        weight=1.0
                    )

        # Connect tasks to contacts (e.g., assignee)
        for task_node in [n for n, attr in self.graph.nodes(data=True) if attr["type"] == "task"]:
            task_data = self.graph.nodes[task_node]
            task_description = task_data.get("description", "").lower()

            for contact_node in [n for n, attr in self.graph.nodes(data=True) if attr["type"] == "contact"]:
                contact_data = self.graph.nodes[contact_node]
                contact_name = contact_data.get("name", "").lower()

                # Connect if contact name is mentioned in task description
                if contact_name and contact_name in task_description:
                    self.graph.add_edge(
                        task_node, contact_node,
                        relationship="mention",
                        weight=1.0
                    )

    def update_embeddings(self, embeddings: Dict[str, np.ndarray]):
        """
        Update node embeddings from an external source.

        Args:
            embeddings: Dictionary mapping node IDs to embedding vectors
        """
        self.node_embeddings = embeddings

    def add_note(self, note_data: Dict[str, Any]) -> str:
        """
        Add a new note to the knowledge graph.

        Args:
            note_data: Dictionary with note data

        Returns:
            ID of the new note
        """
        # Ensure note has an ID
        if "id" not in note_data:
            if isinstance(note_data, Note):
                note_data = note_data.to_dict()
            else:
                note = Note.from_dict(note_data)
                note_data = note.to_dict()

        # Add to data structure
        self.data["notes"].append(note_data)

        # Rebuild the graph to include the new note
        self.build_graph()

        # Save data
        self.save_data()

        return note_data["id"]

    def update_note(self, note_id: str, note_data: Dict[str, Any]) -> bool:
        """
        Update an existing note.

        Args:
            note_id: ID of the note to update
            note_data: Updated note data

        Returns:
            True if the note was updated, False otherwise
        """
        for i, note in enumerate(self.data["notes"]):
            if note.get("id") == note_id:
                # Update the note
                for key, value in note_data.items():
                    note[key] = value

                # Update timestamp
                note["updated_at"] = datetime.now().isoformat()

                # Update data structure
                self.data["notes"][i] = note

                # Rebuild graph
                self.build_graph()

                # Save data
                self.save_data()

                return True

        return False

    def delete_note(self, note_id: str) -> bool:
        """
        Delete a note from the knowledge graph.

        Args:
            note_id: ID of the note to delete

        Returns:
            True if the note was deleted, False otherwise
        """
        for i, note in enumerate(self.data["notes"]):
            if note.get("id") == note_id:
                # Remove from data structure
                self.data["notes"].pop(i)

                # Rebuild graph
                self.build_graph()

                # Save data
                self.save_data()

                return True

        return False

    def get_note(self, note_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a note by ID.

        Args:
            note_id: ID of the note to retrieve

        Returns:
            Note data or None if not found
        """
        for note in self.data["notes"]:
            if note.get("id") == note_id:
                return note

        return None

    def add_task(self, task_data: Dict[str, Any]) -> str:
        """
        Add a new task to the knowledge graph.

        Args:
            task_data: Dictionary with task data

        Returns:
            ID of the new task
        """
        # Ensure task has an ID
        if "id" not in task_data:
            if isinstance(task_data, Task):
                task_data = task_data.to_dict()
            else:
                task = Task.from_dict(task_data)
                task_data = task.to_dict()

        # Add to data structure
        self.data["tasks"].append(task_data)

        # Rebuild the graph to include the new task
        self.build_graph()

        # Save data
        self.save_data()

        return task_data["id"]

    def update_task(self, task_id: str, task_data: Dict[str, Any]) -> bool:
        """
        Update an existing task.

        Args:
            task_id: ID of the task to update
            task_data: Updated task data

        Returns:
            True if the task was updated, False otherwise
        """
        for i, task in enumerate(self.data["tasks"]):
            if task.get("id") == task_id:
                # Update the task
                for key, value in task_data.items():
                    task[key] = value

                # Update timestamp
                task["updated_at"] = datetime.now().isoformat()

                # Update data structure
                self.data["tasks"][i] = task

                # Rebuild graph
                self.build_graph()

                # Save data
                self.save_data()

                return True

        return False

    def delete_task(self, task_id: str) -> bool:
        """
        Delete a task from the knowledge graph.

        Args:
            task_id: ID of the task to delete

        Returns:
            True if the task was deleted, False otherwise
        """
        for i, task in enumerate(self.data["tasks"]):
            if task.get("id") == task_id:
                # Remove from data structure
                self.data["tasks"].pop(i)

                # Rebuild graph
                self.build_graph()

                # Save data
                self.save_data()

                return True

        return False

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a task by ID.

        Args:
            task_id: ID of the task to retrieve

        Returns:
            Task data or None if not found
        """
        for task in self.data["tasks"]:
            if task.get("id") == task_id:
                return task

        return None

    def add_contact(self, contact_data: Dict[str, Any]) -> str:
        """
        Add a new contact to the knowledge graph.

        Args:
            contact_data: Dictionary with contact data

        Returns:
            ID of the new contact
        """
        # Ensure contact has an ID
        if "id" not in contact_data:
            if isinstance(contact_data, Contact):
                contact_data = contact_data.to_dict()
            else:
                contact = Contact.from_dict(contact_data)
                contact_data = contact.to_dict()

        # Add to data structure
        self.data["contacts"].append(contact_data)

        # Rebuild the graph to include the new contact
        self.build_graph()

        # Save data
        self.save_data()

        return contact_data["id"]

    def get_related_entities(self, entity_id: str, entity_type: str, relationship_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get entities related to a specific entity.

        Args:
            entity_id: ID of the entity
            entity_type: Type of the entity ('note', 'task', 'contact')
            relationship_type: Type of relationship to filter by (optional)

        Returns:
            List of related entities with relationship information
        """
        node_id = f"{entity_type}_{entity_id}"

        if node_id not in self.graph:
            raise EntityNotFoundError(
                f"Entity {entity_type} with ID {entity_id} not found")

        related_entities = []

        for neighbor in self.graph.neighbors(node_id):
            edge_data = self.graph.get_edge_data(node_id, neighbor)
            neighbor_data = self.graph.nodes[neighbor]

            # Skip if filtering by relationship type and not a match
            if relationship_type and edge_data.get("relationship") != relationship_type:
                continue

            related_entities.append({
                "id": neighbor.split("_")[1],
                "type": neighbor_data["type"],
                "data": neighbor_data["data"],
                "relationship": edge_data.get("relationship"),
                "relationship_data": {
                    k: v for k, v in edge_data.items() if k != "relationship"
                }
            })

        return related_entities

    def search_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """
        Search for entities with a specific tag.

        Args:
            tag: Tag to search for

        Returns:
            List of entities that have the tag
        """
        results = []

        for node_id, data in self.graph.nodes(data=True):
            if tag in data.get("tags", []):
                entity_id = node_id.split("_")[1]
                results.append({
                    "id": entity_id,
                    "type": data["type"],
                    "data": data["data"]
                })

        return results

    def find_path(self, start_id: str, start_type: str, end_id: str, end_type: str) -> List[Dict[str, Any]]:
        """
        Find the shortest path between two entities.

        Args:
            start_id: ID of the starting entity
            start_type: Type of the starting entity
            end_id: ID of the ending entity
            end_type: Type of the ending entity

        Returns:
            List of entities in the path
        """
        start_node = f"{start_type}_{start_id}"
        end_node = f"{end_type}_{end_id}"

        if start_node not in self.graph:
            raise EntityNotFoundError(
                f"Entity {start_type} with ID {start_id} not found")

        if end_node not in self.graph:
            raise EntityNotFoundError(
                f"Entity {end_type} with ID {end_id} not found")

        try:
            path = nx.shortest_path(self.graph, start_node, end_node)
        except nx.NetworkXNoPath:
            return []

        result = []
        for node in path:
            node_data = self.graph.nodes[node]
            entity_id = node.split("_")[1]
            result.append({
                "id": entity_id,
                "type": node_data["type"],
                "data": node_data["data"]
            })

            # Add relationship data if not the last node
            if node != path[-1]:
                next_node = path[path.index(node) + 1]
                edge_data = self.graph.get_edge_data(node, next_node)
                result[-1]["next_relationship"] = edge_data

        return result
