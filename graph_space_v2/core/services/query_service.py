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
            print(f"Processing natural language query: {query}")
            # First perform a semantic search to get relevant context
            search_results = self.semantic_search(query)
            print(f"Found {len(search_results)} semantic search results")

            # Get graph context by exploring relationships from top results
            graph_context = []

            # Track seen entities to avoid duplicates
            seen_entities = set()

            # For each result, explore its neighbors in the graph
            # Use top 3 results as starting points
            for result in search_results[:3]:
                entity_type = result.get('type')
                entity_id = result.get('id')

                if not entity_type or not entity_id:
                    continue

                # Skip if we've already processed this entity
                entity_key = f"{entity_type}_{entity_id}"
                if entity_key in seen_entities:
                    continue

                seen_entities.add(entity_key)

                # Add the current entity to context
                graph_context.append({
                    'type': entity_type,
                    'id': entity_id,
                    'content': self._get_entity_content(entity_type, entity_id),
                    'relationship': 'direct_match'
                })

                # Get connected entities
                try:
                    related_entities = self.knowledge_graph.get_related_entities(
                        entity_id, entity_type)
                    print(
                        f"Found {len(related_entities)} related entities for {entity_type} {entity_id}")

                    for related in related_entities:
                        related_key = f"{related.get('type')}_{related.get('id')}"

                        # Skip if we've already seen this entity
                        if related_key in seen_entities:
                            continue

                        seen_entities.add(related_key)

                        # Add to context with relationship information
                        graph_context.append({
                            'type': related.get('type'),
                            'id': related.get('id'),
                            'content': self._get_entity_content(related.get('type'), related.get('id')),
                            'relationship': related.get('relationship', 'related')
                        })
                except Exception as e:
                    print(f"Error getting related entities: {e}")

            # Combine semantic search results with graph context
            combined_context = search_results + [item for item in graph_context
                                                 if f"{item['type']}_{item['id']}" not in
                                                 {f"{r['type']}_{r['id']}" for r in search_results}]

            # Build rich context string for LLM including relationship information
            context_items = []

            for item in combined_context:
                entity_type = item.get('type', '').upper()
                entity_content = item.get('content') or item.get('snippet', '')
                relationship = item.get('relationship', 'direct_match')

                if entity_content:
                    # Add relationship information to help LLM understand connections
                    relationship_info = f" (Relationship: {relationship})" if relationship != 'direct_match' else ""
                    context_items.append(
                        f"{entity_type}{relationship_info}: {entity_content}")

            # Join all context items
            context = "\n\n".join(context_items)

            print(f"Built context with {len(context_items)} items")

            # Generate answer using LLM
            answer = self.llm_service.generate_answer(query, context)

            return {
                "query": query,
                "answer": answer,
                "sources": combined_context
            }

        except Exception as e:
            print(f"Error processing natural language query: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "error": f"Error processing natural language query: {str(e)}",
                "search_results": self.text_search(query)
            }

    def _get_entity_content(self, entity_type: str, entity_id: str) -> str:
        """Get the main content text for an entity by type and ID."""
        entity = self._get_entity(entity_type, entity_id)
        if not entity:
            return ""

        if entity_type == "note":
            # For notes, include title and content
            title = entity.get('title', '')
            content = entity.get('content', '')
            return f"{title}\n{content}" if title else content

        elif entity_type == "task":
            # For tasks, include title and description
            title = entity.get('title', '')
            description = entity.get('description', '')
            status = entity.get('status', '')
            return f"{title} ({status})\n{description}" if description else title

        elif entity_type == "contact":
            # For contacts, return formatted contact info
            name = entity.get('name', '')
            email = entity.get('email', '')
            organization = entity.get('organization', '')
            return f"{name}, {organization}, {email}" if organization else f"{name}, {email}"

        elif entity_type == "document":
            # For documents, use summary if available, else use title
            title = entity.get('title', '')
            summary = entity.get('summary', '')
            return f"{title}\n{summary}" if summary else title

        return ""

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

    def get_entities_by_tag(self, entity_type: str) -> List[Dict[str, Any]]:
        """
        Get all entities of a specific type.

        Args:
            entity_type: Type of entity to get ('note', 'task', 'contact')

        Returns:
            List of entities
        """
        if entity_type == "note":
            return self.knowledge_graph.data.get("notes", [])
        elif entity_type == "task":
            return self.knowledge_graph.data.get("tasks", [])
        elif entity_type == "contact":
            return self.knowledge_graph.data.get("contacts", [])
        elif entity_type == "document":
            return self.knowledge_graph.data.get("documents", [])
        else:
            return []

    def get_contacts(self) -> List[Dict[str, Any]]:
        """
        Get all contacts from the knowledge graph.

        Returns:
            List of contact dictionaries
        """
        return self.knowledge_graph.data.get("contacts", [])

    def search_all_entities(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search across all entity types (notes, tasks, contacts, documents).

        Args:
            query: Search query string
            max_results: Maximum number of results to return

        Returns:
            List of matching entities with relevance scores
        """
        results = []

        # Try semantic search first if embedding service is available
        if self.embedding_service:
            try:
                query_embedding = self.embedding_service.embed_text(query)
                search_results = self.embedding_service.search(
                    query_embedding, max_results * 2)

                for match in search_results.get("matches", []):
                    entity_id = match["id"]
                    entity_type = match["metadata"].get("type", "")

                    # Get full entity data
                    entity_data = None
                    if entity_type == "note":
                        entity_data = self.knowledge_graph.get_note(entity_id)
                    elif entity_type == "task":
                        entity_data = self.knowledge_graph.get_task(entity_id)
                    elif entity_type == "contact":
                        entity_data = self._get_entity("contact", entity_id)
                    elif entity_type == "document" or entity_type == "document_chunk":
                        entity_data = self.knowledge_graph.get_document(
                            entity_id.split("_chunk_")[0])

                    if entity_data:
                        results.append({
                            "id": entity_id,
                            "type": entity_type,
                            "entity": entity_data,
                            "score": match["score"],
                            "matched_by": "semantic"
                        })
            except Exception as e:
                print(f"Error in semantic search: {e}")
                # Fall back to text search

        # Add text search results if semantic search didn't find enough
        if len(results) < max_results:
            text_results_needed = max_results - len(results)

            # Search notes
            for note in self.knowledge_graph.data.get("notes", []):
                if query.lower() in note.get("title", "").lower() or query.lower() in note.get("content", "").lower():
                    results.append({
                        "id": note["id"],
                        "type": "note",
                        "entity": note,
                        "score": 0.7,  # Arbitrary score for text match
                        "matched_by": "text"
                    })

            # Search tasks
            for task in self.knowledge_graph.data.get("tasks", []):
                if query.lower() in task.get("title", "").lower() or query.lower() in task.get("description", "").lower():
                    results.append({
                        "id": task["id"],
                        "type": "task",
                        "entity": task,
                        "score": 0.7,
                        "matched_by": "text"
                    })

            # Search contacts
            for contact in self.knowledge_graph.data.get("contacts", []):
                if query.lower() in contact.get("name", "").lower() or query.lower() in contact.get("email", "").lower():
                    results.append({
                        "id": contact["id"],
                        "type": "contact",
                        "entity": contact,
                        "score": 0.7,
                        "matched_by": "text"
                    })

            # Search documents
            for document in self.knowledge_graph.data.get("documents", []):
                if (query.lower() in document.get("title", "").lower() or
                        query.lower() in document.get("summary", "").lower()):
                    results.append({
                        "id": document["id"],
                        "type": "document",
                        "entity": document,
                        "score": 0.7,
                        "matched_by": "text"
                    })

        # Deduplicate results by entity ID and type
        seen_entities = set()
        unique_results = []

        for result in results:
            entity_key = f"{result['type']}_{result['id']}"
            if entity_key not in seen_entities:
                seen_entities.add(entity_key)
                unique_results.append(result)

                if len(unique_results) >= max_results:
                    break

        # Sort by score
        unique_results.sort(key=lambda x: x["score"], reverse=True)

        return unique_results

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
