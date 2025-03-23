from typing import Dict, List, Any, Optional, Set, Union
import networkx as nx
from datetime import datetime

from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph
from graph_space_v2.ai.embedding.embedding_service import EmbeddingService
from graph_space_v2.ai.llm.llm_service import LLMService
from graph_space_v2.utils.errors.exceptions import EntityNotFoundError


class QueryService:
    """Service for querying the knowledge graph."""

    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        embedding_service: Optional[EmbeddingService] = None,
        llm_service: Optional[LLMService] = None
    ):
        """
        Initialize the QueryService.

        Args:
            knowledge_graph: The knowledge graph instance
            embedding_service: Optional embedding service for semantic queries
            llm_service: Optional LLM service for natural language queries
        """
        self.knowledge_graph = knowledge_graph
        self.embedding_service = embedding_service
        self.llm_service = llm_service

    def semantic_search(self, query: str, entity_types: Optional[List[str]] = None, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Perform a semantic search across the knowledge graph.

        Args:
            query: Search query
            entity_types: Optional list of entity types to filter by ('note', 'task', 'contact')
            max_results: Maximum number of results to return

        Returns:
            List of entities matching the query with relevance scores
        """
        if not self.embedding_service:
            return self.text_search(query, entity_types, max_results)

        try:
            # Embed the query
            query_embedding = self.embedding_service.embed_text(query)

            # Prepare filter
            filter_by = {}
            if entity_types:
                filter_by["type"] = entity_types

            # Search for similar entities
            results = self.embedding_service.search(
                query_embedding, max_results, filter_by=filter_by)

            # Enrich results with entity data
            enriched_results = []
            for match in results.get("matches", []):
                entity_id = match["id"]
                entity_type = match["metadata"]["type"]
                entity = self._get_entity(entity_type, entity_id)

                if entity:
                    enriched_results.append({
                        "id": entity_id,
                        "type": entity_type,
                        "entity": entity,
                        "score": match["score"],
                        "snippet": self._generate_snippet(entity, query)
                    })

            return enriched_results

        except Exception as e:
            print(f"Error in semantic search: {e}")
            return self.text_search(query, entity_types, max_results)

    def text_search(self, query: str, entity_types: Optional[List[str]] = None, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Perform a text-based search across the knowledge graph.

        Args:
            query: Search query
            entity_types: Optional list of entity types to filter by ('note', 'task', 'contact')
            max_results: Maximum number of results to return

        Returns:
            List of entities matching the query with relevance scores
        """
        query = query.lower()
        results = []

        # Define what entity types to search
        types_to_search = entity_types if entity_types else [
            "note", "task", "contact"]

        # Search notes
        if "note" in types_to_search:
            for note in self.knowledge_graph.data.get("notes", []):
                score = self._calculate_text_match_score(note, query, "note")
                if score > 0:
                    results.append({
                        "id": note["id"],
                        "type": "note",
                        "entity": note,
                        "score": score,
                        "snippet": self._generate_snippet_for_note(note, query)
                    })

        # Search tasks
        if "task" in types_to_search:
            for task in self.knowledge_graph.data.get("tasks", []):
                score = self._calculate_text_match_score(task, query, "task")
                if score > 0:
                    results.append({
                        "id": task["id"],
                        "type": "task",
                        "entity": task,
                        "score": score,
                        "snippet": self._generate_snippet_for_task(task, query)
                    })

        # Search contacts
        if "contact" in types_to_search:
            for contact in self.knowledge_graph.data.get("contacts", []):
                score = self._calculate_text_match_score(
                    contact, query, "contact")
                if score > 0:
                    results.append({
                        "id": contact["id"],
                        "type": "contact",
                        "entity": contact,
                        "score": score,
                        "snippet": self._generate_snippet_for_contact(contact, query)
                    })

        # Sort by score and limit results
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]

    def _calculate_text_match_score(self, entity: Dict[str, Any], query: str, entity_type: str) -> float:
        """Calculate text match score for an entity."""
        score = 0.0

        if entity_type == "note":
            # Score for title match
            if "title" in entity and query in entity["title"].lower():
                score += 3.0

            # Score for content match
            if "content" in entity and query in entity["content"].lower():
                score += 2.0

        elif entity_type == "task":
            # Score for title match
            if "title" in entity and query in entity["title"].lower():
                score += 3.0

            # Score for description match
            if "description" in entity and query in entity["description"].lower():
                score += 2.0

        elif entity_type == "contact":
            # Score for name match
            if "name" in entity and query in entity["name"].lower():
                score += 3.0

            # Score for email match
            if "email" in entity and query in entity["email"].lower():
                score += 2.0

            # Score for organization match
            if "organization" in entity and query in entity["organization"].lower():
                score += 1.5

        # Score for tag match (common across all entity types)
        if "tags" in entity and any(query in tag.lower() for tag in entity["tags"]):
            score += 1.0

        return score

    def _get_entity(self, entity_type: str, entity_id: str) -> Optional[Dict[str, Any]]:
        """Get entity by type and ID."""
        if entity_type == "note":
            return self.knowledge_graph.get_note(entity_id)
        elif entity_type == "task":
            return self.knowledge_graph.get_task(entity_id)
        elif entity_type == "contact":
            for contact in self.knowledge_graph.data.get("contacts", []):
                if contact.get("id") == entity_id:
                    return contact
        return None

    def _generate_snippet(self, entity: Dict[str, Any], query: str, context_size: int = 50) -> str:
        """Generate a snippet from an entity for a query match."""
        entity_type = entity.get("type", "")

        if entity_type == "note":
            return self._generate_snippet_for_note(entity, query, context_size)
        elif entity_type == "task":
            return self._generate_snippet_for_task(entity, query, context_size)
        elif entity_type == "contact":
            return self._generate_snippet_for_contact(entity, query, context_size)

        return ""

    def _generate_snippet_for_note(self, note: Dict[str, Any], query: str, context_size: int = 50) -> str:
        """Generate a snippet from a note for a query match."""
        content = note.get("content", "")
        return self._extract_snippet(content, query, context_size)

    def _generate_snippet_for_task(self, task: Dict[str, Any], query: str, context_size: int = 50) -> str:
        """Generate a snippet from a task for a query match."""
        description = task.get("description", "")
        return self._extract_snippet(description, query, context_size)

    def _generate_snippet_for_contact(self, contact: Dict[str, Any], query: str, context_size: int = 50) -> str:
        """Generate a snippet from a contact for a query match."""
        # For contacts, we don't have long text fields, so we'll just return a formatted string
        name = contact.get("name", "")
        email = contact.get("email", "")
        org = contact.get("organization", "")

        fields = []
        if name:
            fields.append(f"Name: {name}")
        if email:
            fields.append(f"Email: {email}")
        if org:
            fields.append(f"Organization: {org}")

        return ", ".join(fields)

    def _extract_snippet(self, content: str, query: str, context_size: int = 50) -> str:
        """Extract a snippet from content around the query match."""
        if not content:
            return ""

        query = query.lower()
        content_lower = content.lower()

        # Find the position of the query
        position = content_lower.find(query)
        if position == -1:
            # If query not found, return the first part of the content
            return content[:100] + "..." if len(content) > 100 else content

        # Calculate snippet boundaries
        start = max(0, position - context_size)
        end = min(len(content), position + len(query) + context_size)

        # Add ellipses if needed
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(content) else ""

        return prefix + content[start:end] + suffix

    def query_by_natural_language(self, query: str) -> Dict[str, Any]:
        """
        Process a natural language query using LLM.

        Args:
            query: Natural language query

        Returns:
            Result of the query processing
        """
        if not self.llm_service:
            return {
                "error": "LLM service not available for natural language queries",
                "search_results": self.text_search(query)
            }

        try:
            # First perform a semantic search to get relevant context
            search_results = self.semantic_search(query)

            # Extract context from search results
            context = "\n\n".join([
                f"{result['type'].upper()}: {result['snippet']}"
                for result in search_results
            ])

            # Generate answer using LLM
            answer = self.llm_service.generate_answer(query, context)

            return {
                "query": query,
                "answer": answer,
                "sources": search_results
            }

        except Exception as e:
            return {
                "error": f"Error processing natural language query: {str(e)}",
                "search_results": self.text_search(query)
            }

    def find_path_between_entities(self, source_type: str, source_id: str, target_type: str, target_id: str) -> List[Dict[str, Any]]:
        """
        Find the shortest path between two entities in the knowledge graph.

        Args:
            source_type: Type of the source entity
            source_id: ID of the source entity
            target_type: Type of the target entity
            target_id: ID of the target entity

        Returns:
            List of entities in the path
        """
        return self.knowledge_graph.find_path(source_id, source_type, target_id, target_type)

    def get_entities_by_tag(self, tag: str) -> List[Dict[str, Any]]:
        """
        Get all entities with a specific tag.

        Args:
            tag: The tag to search for

        Returns:
            List of entities with the tag
        """
        return self.knowledge_graph.search_by_tag(tag)

    def get_graph_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the knowledge graph.

        Returns:
            Dictionary with statistics
        """
        graph = self.knowledge_graph.graph

        # Count entity types
        node_types = {}
        for _, attr in graph.nodes(data=True):
            node_type = attr.get("type", "unknown")
            node_types[node_type] = node_types.get(node_type, 0) + 1

        # Count relationship types
        edge_types = {}
        for _, _, attr in graph.edges(data=True):
            edge_type = attr.get("relationship", "unknown")
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1

        # Find most central nodes
        try:
            # Calculate betweenness centrality
            centrality = nx.betweenness_centrality(graph)
            # Get top 5 most central nodes
            most_central = sorted(centrality.items(),
                                  key=lambda x: x[1], reverse=True)[:5]
            most_central_nodes = []

            for node_id, score in most_central:
                node_data = graph.nodes[node_id]
                node_type = node_data.get("type", "unknown")
                entity_id = node_id.split(
                    "_")[1] if "_" in node_id else node_id

                most_central_nodes.append({
                    "id": entity_id,
                    "type": node_type,
                    "centrality": score
                })
        except:
            most_central_nodes = []

        return {
            "total_nodes": graph.number_of_nodes(),
            "total_edges": graph.number_of_edges(),
            "node_types": node_types,
            "edge_types": edge_types,
            "most_central_nodes": most_central_nodes,
            "notes_count": len(self.knowledge_graph.data.get("notes", [])),
            "tasks_count": len(self.knowledge_graph.data.get("tasks", [])),
            "contacts_count": len(self.knowledge_graph.data.get("contacts", []))
        }
