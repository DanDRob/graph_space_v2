import json
import os
import logging # Added
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

    logger = logging.getLogger(__name__) # Added logger instance

    def __init__(self, data_path: str):
        """
        Initialize the knowledge graph.

        Args:
            data_path: Path to the JSON file containing user data.
        """
        self.data_path = data_path
        self.graph = nx.Graph()
        self.node_embeddings = {}
        # self.data will be initialized by _load_graph_data
        self._load_graph_data() # Loads graph and initializes self.data

    def _load_graph_data(self):
        """
        Load graph data from the JSON file.
        If the file doesn't exist, is empty, or contains old list-based format,
        it initializes an empty graph and potentially converts old data.
        Also populates self.data for compatibility.
        """
        self.data = {"notes": [], "tasks": [], "contacts": [], "documents": []} # Initialize self.data

        if not os.path.exists(self.data_path):
            ensure_dir_exists(os.path.dirname(self.data_path))
            self.graph = nx.Graph() # Create an empty graph
            self._save_graph() # Save the empty graph structure immediately
            return

        try:
            with open(self.data_path, 'r') as f:
                json_data = json.load(f)

            # Try to load as new graph format (node-link format)
            if isinstance(json_data, dict) and 'nodes' in json_data and 'links' in json_data:
                self.graph = nx.node_link_graph(json_data, directed=False, multigraph=False)
                # Populate self.data from graph nodes for compatibility
                for node_id_str, attrs in self.graph.nodes(data=True):
                    entity_type = attrs.get("type")
                    entity_data_key = f"{entity_type}s" # e.g. "notes", "tasks"
                    if entity_type and entity_data_key in self.data:
                        # The 'data' attribute within the node should hold the original entity dict
                        stored_entity_dict = attrs.get('data')
                        if isinstance(stored_entity_dict, dict):
                            self.data[entity_data_key].append(stored_entity_dict)
                        else:
                            # Fallback: If 'data' attribute is missing/malformed, reconstruct from node attrs
                            # This might happen if graph was saved by a version not storing full dict in 'data'
                            reconstructed_data = {k: v for k, v in attrs.items() if k not in ['type', 'data']}
                            if 'id' not in reconstructed_data and '_' in node_id_str:
                                reconstructed_data['id'] = node_id_str.split('_',1)[1]
                            self.data[entity_data_key].append(reconstructed_data)
            # Else, assume old list-based format (json_data is a dict of lists)
            elif isinstance(json_data, dict) and any(key in json_data for key in ["notes", "tasks", "contacts", "documents"]):
                # Ensure all standard keys are present in self.data, even if missing in json_data
                for key in ["notes", "tasks", "contacts", "documents"]:
                    self.data[key] = json_data.get(key, [])

                self._build_graph_from_data_lists() # Build graph from these lists
                self.logger.info(f"Converted old format data from {self.data_path} to new graph format and saved.")
                self._save_graph() # Save in new graph format immediately
            else: # Unrecognized format or empty valid JSON
                self.logger.warning(f"Data in '{self.data_path}' is not in a recognized graph format. Initializing empty graph.")
                self.graph = nx.Graph()
                self._save_graph()

        except json.JSONDecodeError as je:
            self.logger.error(f"Invalid JSON in '{self.data_path}'. Initializing empty graph. Error: {je}", exc_info=True)
            self.graph = nx.Graph()
            self._save_graph() # Save empty graph
        except Exception as e:
            self.logger.error(f"Error loading or parsing graph data from '{self.data_path}': {e}. Initializing empty graph.", exc_info=True)
            self.graph = nx.Graph()
            self._save_graph()

    def _save_graph(self):
        """Save the current graph to the JSON file in node-link format."""
        ensure_dir_exists(os.path.dirname(self.data_path))
        graph_data = nx.node_link_data(self.graph)
        with open(self.data_path, 'w') as f:
            json.dump(graph_data, f, indent=2)

    # Renamed from save_data
    def save_data(self): # Effectively an alias for _save_graph now for external calls if any.
        """Save the current graph data back to the JSON file."""
        self._save_graph()

    # Renamed from build_graph
    def _build_graph_from_data_lists(self):
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
        """Add nodes to the graph for all entities in the data. (Used in migration from old format)"""
        self.logger.info("Populating graph nodes from self.data lists...")
        node_count = 0

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
            node_count += 1

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
                tags=task_data.get("tags", []),
                due_date=task_data.get("due_date", ""),
                created_at=task_data.get("created_at", ""),
                updated_at=task_data.get("updated_at", "")
            )
            node_count += 1

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
                tags=contact_data.get("tags", []),
                created_at=contact_data.get("created_at", "")
            )
            node_count += 1

        # Add documents
        for doc_data in self.data.get("documents", []):
            node_id = f"document_{doc_data.get('id')}"
            # Make sure document nodes have all necessary properties
            tags = doc_data.get("tags", []) or []
            topics = doc_data.get("topics", []) or []

            self.logger.debug(
                f"Adding document node from list: {node_id}, title: {doc_data.get('title', 'Untitled')}")

            self.graph.add_node(
                node_id,
                type="document",
                data=doc_data,
                title=doc_data.get("title", ""),
                content=doc_data.get("content", ""),
                tags=tags,
                topics=topics,
                summary=doc_data.get("summary", ""),
                created_at=doc_data.get("created_at", ""),
                processed_at=doc_data.get("processed_at", "")
            )
            node_count += 1

        self.logger.info(f"Added {node_count} nodes to the graph from self.data lists.")

        if self.logger.isEnabledFor(logging.DEBUG):
            node_types_counts = {}
            for _, node_attrs_dict in self.graph.nodes(data=True):
                node_type_val = node_attrs_dict.get('type', 'unknown')
                node_types_counts[node_type_val] = node_types_counts.get(node_type_val, 0) + 1
            self.logger.debug(f"Node type distribution in graph after list import: {node_types_counts}")

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
        """Add edges between different entity types based on relationships. (Used in migration from old format)"""
        self.logger.info("Building cross-entity edges from self.data lists...")
        edge_count = 0

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
                    edge_count += 1

                # Connect if task title is mentioned in note
                task_title = task_data.get("title", "").lower()
                if task_title and task_title in note_content:
                    self.graph.add_edge(
                        note_node, task_node,
                        relationship="mention",
                        weight=1.0
                    )
                    edge_count += 1

        # Connect documents to notes, tasks and contacts by tags
        doc_nodes = [n_id for n_id, attr in self.graph.nodes(data=True) if attr["type"] == "document"] # Get IDs
        self.logger.debug(f"Found {len(doc_nodes)} document nodes in graph to process for cross-entity edges.")

        for doc_node_id in doc_nodes: # Iterate by ID
            doc_data = self.graph.nodes[doc_node_id]
            doc_tags = set(doc_data.get("tags", []) or [])  # Ensure not None
            doc_topics = set(doc_data.get("topics", [])
                             or [])  # Ensure not None
            doc_content = doc_data.get("content", "").lower()
            doc_title = doc_data.get("title", "").lower()

            # Combine tags and topics for better matching
            doc_all_tags = doc_tags.union(doc_topics)

            self.logger.debug(
                f"Processing document {doc_node_id} for cross-entity edges. Tags: {doc_tags}, Topics: {doc_topics}")

            # If no tags/topics found, create basic connections
            if not doc_all_tags and (doc_title or doc_content):
                # Create at least one connection to each note
                for note_node in [n for n, attr in self.graph.nodes(data=True) if attr["type"] == "note"]:
                    self.graph.add_edge(
                        doc_node, note_node,
                        relationship="associated_document",
                        weight=0.5
                    )
                    edge_count += 1
                continue

            # Connect documents to notes
            for note_node in [n for n, attr in self.graph.nodes(data=True) if attr["type"] == "note"]:
                note_data = self.graph.nodes[note_node]
                note_tags = set(note_data.get("tags", [])
                                or [])  # Ensure not None
                note_content = note_data.get("content", "").lower()
                note_title = note_data.get("title", "").lower()

                # Connect by shared tags
                shared_tags = doc_all_tags.intersection(note_tags)
                if shared_tags:
                    self.logger.debug(
                        f"Creating edge between document {doc_node_id} and note {note_node} based on shared tags: {shared_tags}")
                    self.graph.add_edge(
                        doc_node_id, note_node,
                        relationship="shared_tags",
                        shared_tags=list(shared_tags),
                        weight=len(shared_tags)
                    )
                    edge_count += 1
                # Connect by content similarity
                elif doc_title and doc_title in note_content:
                    self.graph.add_edge(
                        doc_node, note_node,
                        relationship="content_mention",
                        weight=0.8
                    )
                    edge_count += 1
                # Fallback connection if no other connection found
                elif not shared_tags and not doc_content:
                    self.graph.add_edge(
                        doc_node, note_node,
                        relationship="associated_document",
                        weight=0.3
                    )
                    edge_count += 1

            # Connect documents to tasks
            for task_node in [n for n, attr in self.graph.nodes(data=True) if attr["type"] == "task"]:
                task_data = self.graph.nodes[task_node]
                task_tags = set(task_data.get("tags", [])
                                or [])  # Ensure not None
                task_title = task_data.get("title", "").lower()
                task_desc = task_data.get("description", "").lower()

                # Connect by shared tags
                shared_tags = doc_all_tags.intersection(task_tags)
                if shared_tags:
                    self.graph.add_edge(
                        doc_node, task_node,
                        relationship="shared_tags",
                        shared_tags=list(shared_tags),
                        weight=len(shared_tags)
                    )
                    edge_count += 1
                # Connect by content similarity
                elif doc_title and (doc_title in task_title or doc_title in task_desc):
                    self.graph.add_edge(
                        doc_node, task_node,
                        relationship="content_mention",
                        weight=0.8
                    )
                    edge_count += 1

            # Connect documents to contacts
            for contact_node in [n for n, attr in self.graph.nodes(data=True) if attr["type"] == "contact"]:
                contact_data = self.graph.nodes[contact_node]
                contact_tags = set(contact_data.get(
                    "tags", []) or [])  # Ensure not None
                contact_name = contact_data.get("name", "").lower()
                contact_org = contact_data.get("organization", "").lower()

                # Connect by shared tags
                shared_tags = doc_all_tags.intersection(contact_tags)
                if shared_tags:
                    self.graph.add_edge(
                        doc_node, contact_node,
                        relationship="shared_tags",
                        shared_tags=list(shared_tags),
                        weight=len(shared_tags)
                    )
                    edge_count += 1
                # Connect if contact is mentioned in document
                elif contact_name and contact_name in doc_content:
                    self.graph.add_edge(
                        doc_node, contact_node,
                        relationship="mention",
                        weight=1.0
                    )
                    edge_count += 1
                elif contact_org and contact_org in doc_content:
                    self.graph.add_edge(
                        doc_node, contact_node,
                        relationship="organization_mention",
                        weight=0.9
                    )
                    edge_count += 1

        self.logger.info(f"Finished building cross-entity edges from lists. Created {edge_count} edges.")

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

        # Add to self.data list (for compatibility)
        # Avoid duplicates if note_data somehow already got into self.data["notes"]
        if not any(n.get('id') == note_data['id'] for n in self.data.get("notes", [])):
            self.data["notes"].append(note_data)

        # Add node to graph directly
        node_id = f"note_{note_data['id']}"
        self.graph.add_node(
            node_id,
            type="note",
            data=note_data, # Store the full original dict here
            # Store some attributes at top level for easier access by networkx functions if needed
            title=note_data.get("title", ""),
            content=note_data.get("content", ""), # Consider if content is too large for direct attr
            tags=note_data.get("tags", []),
            created_at=note_data.get("created_at", ""),
            updated_at=note_data.get("updated_at", "")
        )

        # Update edges related to this new/updated node
        self._update_edges_for_node(node_id)

        # Save graph to persist changes
        self._save_graph()

        return note_data["id"]

    def _update_edges_for_node(self, node_id: str):
        """
        Update all edges for a specific node after it's added or updated.
        This involves removing all its existing edges, then re-calculating and adding
        new edges based on its current attributes and relationships with other nodes.
        """
        if node_id not in self.graph:
            self.logger.warning(f"Node {node_id} not found in graph for edge update. Cannot update edges.")
            return

        # Remove existing edges connected to this node
        # Iterating over a copy because edge removal modifies the graph's edge view
        edges_to_remove = list(self.graph.edges(node_id))
        for u, v in edges_to_remove:
            self.graph.remove_edge(u, v)

        node_attrs = self.graph.nodes[node_id]
        node_type = node_attrs.get("type")

        # Add intra-type edges (e.g., note-to-note by tags)
        if node_type == "note":
            self._add_specific_edges_for_note(node_id, node_attrs)
        elif node_type == "task":
            self._add_specific_edges_for_task(node_id, node_attrs)
        elif node_type == "contact":
            self._add_specific_edges_for_contact(node_id, node_attrs)
        elif node_type == "document":
            self._add_specific_edges_for_document(node_id, node_attrs) # Placeholder

        # Add inter-type edges (e.g., note-to-task, document-to-note)
        self._update_cross_entity_edges_for_node(node_id, node_attrs)


    def _add_specific_edges_for_note(self, note_id: str, note_attrs: Dict):
        """Adds intra-type edges for a given note (e.g., shared tags with other notes)."""
        note_tags = set(note_attrs.get("tags", []))
        for other_node_id, other_attrs in self.graph.nodes(data=True):
            if other_node_id == note_id or other_attrs.get("type") != "note":
                continue
            other_tags = set(other_attrs.get("tags", []))
            shared_tags = note_tags.intersection(other_tags)
            if shared_tags:
                self.graph.add_edge(
                    note_id, other_node_id,
                    relationship="shared_tags",
                    shared_tags=list(shared_tags),
                    weight=len(shared_tags)
                )

    def _add_specific_edges_for_task(self, task_id: str, task_attrs: Dict):
        """Adds intra-type edges for a given task."""
        task_tags = set(task_attrs.get("tags", []))
        task_project = task_attrs.get("project") # Assuming 'project' is in task_attrs from 'data'
        for other_node_id, other_attrs in self.graph.nodes(data=True):
            if other_node_id == task_id or other_attrs.get("type") != "task":
                continue

            # Connect by project
            if task_project and task_project == other_attrs.get("project"):
                self.graph.add_edge(
                    task_id, other_node_id,
                    relationship="same_project",
                    project=task_project,
                    weight=1.0
                )
            # Connect by shared tags
            other_tags = set(other_attrs.get("tags", []))
            shared_tags = task_tags.intersection(other_tags)
            if shared_tags:
                self.graph.add_edge(
                    task_id, other_node_id,
                    relationship="shared_tags",
                    shared_tags=list(shared_tags),
                    weight=len(shared_tags)
                )

    def _add_specific_edges_for_contact(self, contact_id: str, contact_attrs: Dict):
        """Adds intra-type edges for a given contact."""
        contact_tags = set(contact_attrs.get("tags", []))
        contact_org = contact_attrs.get("organization") # Assuming 'organization' is in contact_attrs
        for other_node_id, other_attrs in self.graph.nodes(data=True):
            if other_node_id == contact_id or other_attrs.get("type") != "contact":
                continue

            # Connect by organization
            if contact_org and contact_org == other_attrs.get("organization"):
                self.graph.add_edge(
                    contact_id, other_node_id,
                    relationship="same_organization",
                    organization=contact_org,
                    weight=1.0
                )
            # Connect by shared tags
            other_tags = set(other_attrs.get("tags", []))
            shared_tags = contact_tags.intersection(other_tags)
            if shared_tags:
                self.graph.add_edge(
                    contact_id, other_node_id,
                    relationship="shared_tags",
                    shared_tags=list(shared_tags),
                    weight=len(shared_tags)
                )

    def _add_specific_edges_for_document(self, doc_id: str, doc_attrs: Dict):
        """Placeholder for document-to-document specific edge logic if needed."""
        pass # Currently documents primarily connect via cross-entity edges.


    def _update_cross_entity_edges_for_node(self, current_node_id: str, current_node_attrs: Dict):
        """
        Updates cross-entity edges for the current_node_id by checking relationships
        with all other relevant nodes in the graph.
        This ensures that when a node is added or updated, its connections to
        nodes of different types are correctly established or re-established.
        """
        current_node_type = current_node_attrs.get("type")

        for other_node_id, other_node_attrs in self.graph.nodes(data=True):
            if current_node_id == other_node_id: # Don't connect node to itself
                continue

            other_node_type = other_node_attrs.get("type")

            # Determine source and target for edge creation based on type pairing
            # Note-Task
            if current_node_type == "note" and other_node_type == "task":
                self._create_note_task_edge(current_node_id, current_node_attrs, other_node_id, other_node_attrs)
            elif current_node_type == "task" and other_node_type == "note":
                self._create_note_task_edge(other_node_id, other_node_attrs, current_node_id, current_node_attrs) # Reversed order

            # Document with Note, Task, Contact
            # Document is usually the 'source' of information (tags, content)
            if current_node_type == "document":
                if other_node_type in ["note", "task", "contact"]:
                    self._create_doc_to_other_edge(current_node_id, current_node_attrs, other_node_id, other_node_attrs)
            elif other_node_type == "document": # current_node is note, task, or contact
                if current_node_type in ["note", "task", "contact"]:
                    self._create_doc_to_other_edge(other_node_id, other_node_attrs, current_node_id, current_node_attrs) # Reversed order

    def _create_note_task_edge(self, note_id: str, note_attrs: Dict, task_id: str, task_attrs: Dict):
        """Helper to create edges between a note and a task."""
        note_tags = set(note_attrs.get("tags", []))
        note_content = note_attrs.get("content", "").lower()
        task_tags = set(task_attrs.get("tags", []))
        task_title = task_attrs.get("title", "").lower()

        # Shared tags
        shared_tags = note_tags.intersection(task_tags)
        if shared_tags:
            self.graph.add_edge(note_id, task_id, relationship="shared_tags", shared_tags=list(shared_tags), weight=len(shared_tags))

        # Task title mentioned in note content
        if task_title and task_title in note_content:
            self.graph.add_edge(note_id, task_id, relationship="mention", context="task_in_note", weight=1.0)
        # Note title mentioned in task description (if applicable - less common)
        # task_desc = task_attrs.get("description","").lower()
        # note_title = note_attrs.get("title","").lower()
        # if note_title and note_title in task_desc:
        #    self.graph.add_edge(note_id, task_id, relationship="mention", context="note_in_task", weight=1.0)


    def _create_doc_to_other_edge(self, doc_id: str, doc_attrs: Dict, other_id: str, other_attrs: Dict):
        """
        Helper to create edges from a document to another entity (note, task, contact).
        """
        doc_all_tags = set(doc_attrs.get("tags", []) or []).union(set(doc_attrs.get("topics", []) or []))
        doc_content = doc_attrs.get("content", "").lower()
        doc_title = doc_attrs.get("title", "").lower()

        other_type = other_attrs.get("type")

        if other_type == "note":
            note_tags = set(other_attrs.get("tags", []) or [])
            note_content = other_attrs.get("content", "").lower() # Note's own content
            note_title = other_attrs.get("title","").lower()
            shared_tags = doc_all_tags.intersection(note_tags)
            if shared_tags:
                self.graph.add_edge(doc_id, other_id, relationship="shared_tags", shared_tags=list(shared_tags), weight=len(shared_tags))
            if doc_title and doc_title in note_content: # Doc title in note content
                self.graph.add_edge(doc_id, other_id, relationship="content_mention", mention_details="doc_title_in_note_content", weight=0.8)
            if note_title and note_title in doc_content: # Note title in doc content
                self.graph.add_edge(doc_id, other_id, relationship="content_mention", mention_details="note_title_in_doc_content", weight=0.8)

        elif other_type == "task":
            task_tags = set(other_attrs.get("tags", []) or [])
            task_title = other_attrs.get("title", "").lower()
            task_desc = other_attrs.get("description", "").lower()
            shared_tags = doc_all_tags.intersection(task_tags)
            if shared_tags:
                self.graph.add_edge(doc_id, other_id, relationship="shared_tags", shared_tags=list(shared_tags), weight=len(shared_tags))
            if doc_title and (doc_title in task_title or doc_title in task_desc): # Doc title in task
                self.graph.add_edge(doc_id, other_id, relationship="content_mention", mention_details="doc_title_in_task", weight=0.8)
            if task_title and task_title in doc_content: # Task title in doc content
                self.graph.add_edge(doc_id, other_id, relationship="content_mention", mention_details="task_title_in_doc_content", weight=0.8)


        elif other_type == "contact":
            contact_tags = set(other_attrs.get("tags", []) or [])
            contact_name = other_attrs.get("name", "").lower()
            contact_org = other_attrs.get("organization", "").lower()
            shared_tags = doc_all_tags.intersection(contact_tags)
            if shared_tags:
                self.graph.add_edge(doc_id, other_id, relationship="shared_tags", shared_tags=list(shared_tags), weight=len(shared_tags))
            if contact_name and contact_name in doc_content: # Contact name in doc content
                self.graph.add_edge(doc_id, other_id, relationship="mention", mention_details="contact_name_in_doc_content", weight=1.0)
            elif contact_org and contact_org in doc_content: # Org name in doc content
                self.graph.add_edge(doc_id, other_id, relationship="organization_mention", mention_details="contact_org_in_doc_content", weight=0.9)

    def update_note(self, note_id: str, note_data: Dict[str, Any]) -> bool:

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

                # Update the note in self.data list (for compatibility)
                # note_data should contain all fields, not just updated ones.
                # The calling function should ensure note_data is the full, updated representation.
                note["updated_at"] = datetime.now().isoformat()
                note.update(note_data) # Apply updates to the dict in self.data
                self.data["notes"][i] = note # Place it back in list

                # Update node in graph directly
                graph_node_id = f"note_{note_id}"
                if graph_node_id in self.graph:
                    # Update the 'data' attribute with the complete updated note object
                    self.graph.nodes[graph_node_id]["data"] = note
                    # Update top-level attributes from the 'note' dict
                    for key, value in note.items():
                        self.graph.nodes[graph_node_id][key] = value

                    # Edges might change based on new data (e.g. tags changed)
                    self._update_edges_for_node(graph_node_id)
                    self._save_graph()
                    return True
                else:
                    # Node not in graph, but was in self.data. This indicates inconsistency.
                    # Option: Add it now? Or log error?
                    # For now, if we fixed self.data, let's try to rebuild if graph is out of sync.
                    self.logger.warning(f"Note {graph_node_id} found in data list but not in graph during update. Rebuilding graph from data lists.")
                    self._build_graph_from_data_lists() # This will use the updated self.data
                    self._save_graph() # Persist the rebuilt graph
                    # Still, the original direct update failed on the potentially inconsistent graph state.
                    # Depending on desired behavior, one might return True because data is now consistent,
                    # or False because the initial state was problematic.
                    return True # Let's consider it a success if data is now consistent and saved.

        self.logger.warning(f"Note with ID {note_id} not found in self.data['notes'] list for update operation.")
        return False # Note not found in self.data["notes"]

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
                # Remove from self.data list (for compatibility)
                self.data["notes"].pop(i)

                # Remove node from graph directly
                graph_node_id = f"note_{note_id}"
                if self.graph.has_node(graph_node_id):
                    self.graph.remove_node(graph_node_id)
                    # Edges are automatically removed by NetworkX.
                    self._save_graph()
                    return True
                else:
                    # Node was in self.data list but not in graph. Inconsistency.
                    # self.data list is now fixed.
                    self.logger.warning(f"Note {graph_node_id} was removed from data list but was not found in the graph itself.")
                    self._save_graph() # Save graph to persist other changes if any (though this node wasn't in it)
                    return True # From the perspective of self.data list, it's deleted.

        self.logger.warning(f"Note with ID {note_id} not found in self.data['notes'] list for delete operation.")
        return False # Note not found in self.data["notes"]

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

        # Add to self.data list (for compatibility)
        if not any(t.get('id') == task_data['id'] for t in self.data.get("tasks", [])):
            self.data["tasks"].append(task_data)

        # Add node to graph directly
        node_id = f"task_{task_data['id']}"
        self.graph.add_node(
            node_id,
            type="task",
            data=task_data,
            title=task_data.get("title", ""),
            description=task_data.get("description", ""),
            status=task_data.get("status", ""),
            tags=task_data.get("tags", []),
            due_date=task_data.get("due_date", ""),
            created_at=task_data.get("created_at", ""),
            updated_at=task_data.get("updated_at", ""),
            project=task_data.get("project") # Make sure project is included
        )
        self._update_edges_for_node(node_id)
        self._save_graph()
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

                # Update task in self.data list
                task["updated_at"] = datetime.now().isoformat()
                task.update(task_data)
                self.data["tasks"][i] = task

                # Update node in graph directly
                graph_node_id = f"task_{task_id}"
                if graph_node_id in self.graph:
                    self.graph.nodes[graph_node_id]["data"] = task
                    for key, value in task.items(): # Update top-level attributes
                        self.graph.nodes[graph_node_id][key] = value

                    self._update_edges_for_node(graph_node_id)
                    self._save_graph()
                    return True
                else:
                    self.logger.warning(f"Task {graph_node_id} found in data list but not in graph during update. Rebuilding graph.")
                    self._build_graph_from_data_lists()
                    self._save_graph()
                    return True # Data is now consistent and saved.

        self.logger.warning(f"Task with ID {task_id} not found in self.data['tasks'] list for update.")
        return False # Task not found

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
                # Remove from self.data list
                self.data["tasks"].pop(i)

                graph_node_id = f"task_{task_id}"
                if self.graph.has_node(graph_node_id):
                    self.graph.remove_node(graph_node_id)
                    self._save_graph()
                    return True
                else:
                    self.logger.warning(f"Task {graph_node_id} was removed from data list but was not found in the graph itself.")
                    self._save_graph()
                    return True # From data list perspective, it's deleted.

        self.logger.warning(f"Task with ID {task_id} not found in self.data['tasks'] list for deletion.")
        return False # Task not found

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

        # Add to self.data list (for compatibility)
        if not any(c.get('id') == contact_data['id'] for c in self.data.get("contacts", [])):
            self.data["contacts"].append(contact_data)

        # Add node to graph directly
        node_id = f"contact_{contact_data['id']}"
        # Ensure created_at is set, as contacts might not have updated_at by default
        if "created_at" not in contact_data:
             contact_data["created_at"] = datetime.now().isoformat()

        self.graph.add_node(
            node_id,
            type="contact",
            data=contact_data,
            name=contact_data.get("name", ""),
            email=contact_data.get("email", ""),
            phone=contact_data.get("phone", ""),
            organization=contact_data.get("organization", ""),
            tags=contact_data.get("tags", []),
            created_at=contact_data.get("created_at")
        )
        self._update_edges_for_node(node_id)
        self._save_graph()
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

    def add_relationship(self, source_id: str, target_id: str, relationship_type: str,
                         properties: Optional[Dict[str, Any]] = None) -> bool:
        """
        Add a relationship between two entities.

        Args:
            source_id: ID of the source entity
            target_id: ID of the target entity
            relationship_type: Type of relationship
            properties: Additional properties for the relationship

        Returns:
            True if successful, False otherwise
        """
        # Determine entity types from IDs in the graph
        source_type = None
        target_type = None

        for node_id in self.graph.nodes:
            parts = node_id.split("_", 1)
            if len(parts) == 2:
                node_type, node_id_part = parts
                if node_id_part == source_id:
                    source_type = node_type
                elif node_id_part == target_id:
                    target_type = node_type

        if not source_type or not target_type:
            return False

        # Create edge with relationship properties
        source_node_id = f"{source_type}_{source_id}"
        target_node_id = f"{target_type}_{target_id}"

        props = {"relationship": relationship_type}
        if properties:
            props.update(properties)

        try:
            self.graph.add_edge(source_node_id, target_node_id, **props)
            return True
        except Exception:
            return False

    def update_node(self, entity_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update a generic node with new data.
        It finds the node in graph, updates its 'data' attribute and top-level attributes.
        Also updates the corresponding item in self.data lists for compatibility.

        Args:
            entity_id: ID of the entity to update.
            updates: Dictionary of updates to apply. This should be the fields to update.

        Returns:
            True if successful, False otherwise.
        """
        graph_node_id = None
        node_type_singular = None
        entity_list_key = None # e.g. "notes", "tasks"

        # Determine node type and graph_node_id
        for type_s, type_p_key in {"note": "notes", "task": "tasks", "contact": "contacts", "document": "documents"}.items():
            potential_id = f"{type_s}_{entity_id}"
            if self.graph.has_node(potential_id):
                graph_node_id = potential_id
                node_type_singular = type_s
                entity_list_key = type_p_key
                break

        if not graph_node_id:
            self.logger.error(f"Generic update_node: Node for entity_id '{entity_id}' not found in graph.")
            return False

        # Update the item in the self.data list
        item_updated_in_list = False
        if entity_list_key and entity_list_key in self.data:
            for i, item in enumerate(self.data[entity_list_key]):
                if item.get("id") == entity_id:
                    # Apply updates and set/update 'updated_at'
                    item.update(updates)
                    if "updated_at" in item or node_type_singular != "contact": # Contacts might not have updated_at
                        item["updated_at"] = datetime.now().isoformat()
                    self.data[entity_list_key][i] = item
                    item_updated_in_list = True

                    # Update graph node using this updated item from self.data
                    self.graph.nodes[graph_node_id]['data'] = item # Store full dict in 'data'
                    for key, value in item.items(): # Update top-level attrs
                        self.graph.nodes[graph_node_id][key] = value
                    break

        if not item_updated_in_list:
            # Item not found in self.data list, or list key is wrong.
            # Fallback: update graph node directly using 'updates' and try to reconstruct 'data' attr.
            self.logger.warning(f"Generic update_node: Entity '{entity_id}' (type: {node_type_singular}) not found in self.data['{entity_list_key}']. Updating graph node attributes directly.")
            current_graph_data = self.graph.nodes[graph_node_id].get('data', {})
            current_graph_data.update(updates) # Apply updates
            if "updated_at" in self.graph.nodes[graph_node_id] or node_type_singular != "contact": # Contacts might not have updated_at
                current_graph_data["updated_at"] = datetime.now().isoformat()
                self.graph.nodes[graph_node_id]["updated_at"] = current_graph_data["updated_at"]

            self.graph.nodes[graph_node_id]['data'] = current_graph_data
            for key, value in updates.items(): # Update top-level attributes that were explicitly passed
                 self.graph.nodes[graph_node_id][key] = value


        # Common attributes like 'tags', 'title', 'name', 'status', 'organization' should be at top-level of node
        # Ensure these are updated from the 'updates' dict if present
        for common_key in ['tags', 'title', 'name', 'status', 'organization', 'project', 'content', 'description', 'summary', 'topics']:
            if common_key in updates:
                self.graph.nodes[graph_node_id][common_key] = updates[common_key]

        self._update_edges_for_node(graph_node_id)
        self._save_graph()
        return True


    def delete_node(self, entity_id: str) -> bool:
        """
        Delete a node from the graph.

        Args:
            entity_id: ID of the entity to delete

        Returns:
            True if successful, False otherwise
        """
        """
        Delete a generic node by its entity_id.
        It finds the node in the graph, removes it, and also removes it from self.data lists.
        """
        graph_node_id_to_delete = None
        entity_list_key = None # e.g. "notes"

        # Find the node in the graph to determine its type and full ID
        for type_s, type_p_key in {"note": "notes", "task": "tasks", "contact": "contacts", "document": "documents"}.items():
            potential_id = f"{type_s}_{entity_id}"
            if self.graph.has_node(potential_id):
                graph_node_id_to_delete = potential_id
                entity_list_key = type_p_key
                break

        deleted_from_data_list = False
        # Remove from self.data list (for compatibility)
        if entity_list_key and entity_list_key in self.data:
            original_len = len(self.data[entity_list_key])
            self.data[entity_list_key] = [item for item in self.data[entity_list_key]
                                          if item.get("id") != entity_id]
            if len(self.data[entity_list_key]) < original_len:
                deleted_from_data_list = True

        if not graph_node_id_to_delete:
            if deleted_from_data_list:
                # Removed from list, but wasn't in graph.
                self.logger.warning(f"Generic delete_node: Entity '{entity_id}' removed from data list but was not found in the graph.")
                self._save_graph()
                return True # Successful from data list perspective
            self.logger.error(f"Generic delete_node: Node for entity_id '{entity_id}' not found in graph for deletion and was not in data lists either.")
            return False # Not found in graph or lists

        # Remove node from graph
        self.graph.remove_node(graph_node_id_to_delete)
        # Edges are automatically removed by NetworkX.

        self._save_graph()
        return True


    def remove_all_relationships(self, entity_id: str) -> bool:
        """
        Remove all relationships for an entity.

        Args:
            entity_id: ID of the entity

        Returns:
            True if successful, False otherwise
        """
        # Find the node in the graph
        node_id = None
        for n in self.graph.nodes:
            if n.endswith(f"_{entity_id}"):
                node_id = n
                break

        if not node_id:
            return False

        # Find the node in the graph first to get its full prefixed ID
        node_id_to_clear = None
        for type_prefix in ["note", "task", "contact", "document"]:
            potential_id = f"{type_prefix}_{entity_id}"
            if self.graph.has_node(potential_id):
                node_id_to_clear = potential_id
                break

        if not node_id_to_clear:
            self.logger.warning(f"Node for entity_id '{entity_id}' not found in graph. Cannot remove relationships.")
            return False

        # Get all neighbors (edges will be (node_id_to_clear, neighbor))
        # Make a copy of neighbors list as graph will be modified
        neighbors = list(self.graph.neighbors(node_id_to_clear))

        # Remove all edges connected to this node
        for neighbor in neighbors:
            if self.graph.has_edge(node_id_to_clear, neighbor):
                self.graph.remove_edge(node_id_to_clear, neighbor)

        self._save_graph() # Persist the changes (edge removals)
        return True

    def add_document(self, document_data: Dict[str, Any]) -> str:
        """
        Add a document to the knowledge graph.

        Args:
            document_data: Document data dictionary

        Returns:
            ID of the document
        """
        # Ensure document has an ID
        if "id" not in document_data:
            document_data["id"] = os.path.basename(
                document_data.get("file_path", ""))

        # Ensure documents array exists
        if "documents" not in self.data:
            self.data["documents"] = []

        # Ensure documents array exists in self.data (for compatibility)
        if "documents" not in self.data:
            self.data["documents"] = []

        # Add or update in self.data list
        doc_idx = -1
        for i, existing_doc in enumerate(self.data["documents"]):
            if existing_doc.get("id") == document_data["id"]:
                doc_idx = i
                break

        if doc_idx != -1: # Update existing document in list
            self.data["documents"][doc_idx] = document_data
        else: # Add new document to list
            self.data["documents"].append(document_data)

        # Add or Update node in graph directly
        node_id = f"document_{document_data['id']}"

        # Prepare node attributes. 'data' holds the original dict.
        node_attrs = {
            "type": "document",
            "data": document_data,
            "title": document_data.get("title", ""),
            "content": document_data.get("content", ""),
            "tags": document_data.get("tags", []),
            "topics": document_data.get("topics", []),
            "summary": document_data.get("summary", ""),
            "created_at": document_data.get("created_at", datetime.now().isoformat()), # Ensure created_at
            "processed_at": document_data.get("processed_at", "")
        }
        # Handle updated_at if document can be updated
        if "updated_at" in document_data:
             node_attrs["updated_at"] = document_data["updated_at"]
        elif self.graph.has_node(node_id): # If updating and no updated_at, set it now
             node_attrs["updated_at"] = datetime.now().isoformat()


        if self.graph.has_node(node_id): # If node exists, update its attributes
            for key, value in node_attrs.items():
                self.graph.nodes[node_id][key] = value
        else: # If node doesn't exist, add it
            self.graph.add_node(node_id, **node_attrs)

        self._update_edges_for_node(node_id)
        self._save_graph()
        return document_data["id"]

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a document by ID.

        Args:
            document_id: ID of the document

        Returns:
            Document data or None if not found
        """
        if "documents" not in self.data:
            return None

        for document in self.data["documents"]:
            if document.get("id") == document_id:
                return document

        return None
