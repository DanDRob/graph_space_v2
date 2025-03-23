from typing import Dict, List, Any, Optional, Set, Union
from datetime import datetime
import uuid
import traceback

from graph_space_v2.core.models.note import Note
from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph
from graph_space_v2.ai.embedding.embedding_service import EmbeddingService
from graph_space_v2.ai.llm.llm_service import LLMService
from graph_space_v2.utils.errors.exceptions import EntityNotFoundError


class NoteService:
    """Service class for note-related operations."""

    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        embedding_service: Optional[EmbeddingService] = None,
        llm_service: Optional[LLMService] = None
    ):
        """
        Initialize the NoteService.

        Args:
            knowledge_graph: The knowledge graph instance
            embedding_service: Optional embedding service for semantic features
            llm_service: Optional LLM service for advanced features
        """
        self.knowledge_graph = knowledge_graph
        self.embedding_service = embedding_service
        self.llm_service = llm_service

    def add_note(self, note_data: Dict[str, Any]) -> str:
        """
        Add a new note.

        Args:
            note_data: Dictionary with note data

        Returns:
            ID of the new note
        """
        # Convert to Note instance if it's a dictionary
        if not isinstance(note_data, Note):
            # Generate title and tags using LLM if available and not provided
            if self.llm_service and not note_data.get("title") and note_data.get("content"):
                title = self.llm_service.generate_title(note_data["content"])
                note_data["title"] = title or "Untitled Note"

            if self.llm_service and not note_data.get("tags") and note_data.get("content"):
                tags = self.llm_service.extract_tags(note_data["content"])
                note_data["tags"] = tags

            # Set timestamps if not provided
            now = datetime.now().isoformat()
            if not note_data.get("created_at"):
                note_data["created_at"] = now
            if not note_data.get("updated_at"):
                note_data["updated_at"] = now

            note = Note.from_dict(note_data)
            note_data = note.to_dict()

        # Create embeddings if available
        if self.embedding_service and note_data.get("content"):
            try:
                embedding = self.embedding_service.embed_text(
                    note_data["content"])
                # Store the embedding (implementation depends on EmbeddingService)
                self.embedding_service.store_embedding(
                    note_data["id"], embedding, {"type": "note"})
            except Exception as e:
                print(f"Error creating embedding: {e}")

        # Add to knowledge graph
        return self.knowledge_graph.add_note(note_data)

    def get_note(self, note_id: str) -> Optional[Note]:
        """
        Get a note by ID.

        Args:
            note_id: ID of the note to retrieve

        Returns:
            Note instance or None if not found
        """
        note_data = self.knowledge_graph.get_note(note_id)
        if note_data:
            return Note.from_dict(note_data)

        return None

    def get_all_notes(self) -> List[Dict[str, Any]]:
        """
        Get all notes.

        Returns:
            List of note dictionaries
        """
        try:
            # For troubleshooting, let's first check the knowledge graph data structure
            print(f"Knowledge graph data: {self.knowledge_graph.data}")

            # Check if notes array exists in data
            if "notes" not in self.knowledge_graph.data:
                print(
                    "Notes array not found in knowledge graph data, initializing empty list")
                self.knowledge_graph.data["notes"] = []

            # Get raw notes from knowledge graph
            raw_notes = self.knowledge_graph.data.get("notes", [])
            print(f"Found {len(raw_notes)} raw notes in knowledge graph")

            # Return raw note data as dictionaries instead of converting to Note objects
            # This avoids potential serialization issues with Note objects
            return raw_notes
        except Exception as e:
            print(f"Error in get_all_notes: {e}")
            traceback.print_exc()
            # Return empty list instead of raising exception
            return []

    def update_note(self, note_id: str, note_data: Dict[str, Any]) -> Optional[Note]:
        """
        Update a note.

        Args:
            note_id: ID of the note to update
            note_data: Updated note data

        Returns:
            Updated Note instance or None if not found
        """
        # Set the updated_at timestamp
        note_data["updated_at"] = datetime.now().isoformat()

        # Update the note in the knowledge graph
        success = self.knowledge_graph.update_note(note_id, note_data)

        if success:
            # Update embedding if content was updated
            if self.embedding_service and "content" in note_data:
                try:
                    embedding = self.embedding_service.embed_text(
                        note_data["content"])
                    self.embedding_service.update_embedding(note_id, embedding)
                except Exception as e:
                    print(f"Error updating embedding: {e}")

            # Return the updated note
            return self.get_note(note_id)

        return None

    def delete_note(self, note_id: str) -> bool:
        """
        Delete a note.

        Args:
            note_id: ID of the note to delete

        Returns:
            True if the note was deleted, False otherwise
        """
        # Delete from embedding service if available
        if self.embedding_service:
            try:
                self.embedding_service.delete_embedding(note_id)
            except Exception as e:
                print(f"Error deleting embedding: {e}")

        # Delete from knowledge graph
        return self.knowledge_graph.delete_note(note_id)

    def search_notes_by_content(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search notes by content using semantic search if available.

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of notes matching the query with relevance scores
        """
        if not self.embedding_service:
            # Fall back to simple text search if embedding service not available
            return self._simple_text_search(query, max_results)

        try:
            # Embed the query
            query_embedding = self.embedding_service.embed_text(query)

            # Search for similar notes
            results = self.embedding_service.search(
                query_embedding, max_results, filter_by={"type": "note"})

            # Convert IDs to Note objects
            note_results = []
            for match in results.get("matches", []):
                note_id = match["id"]
                note = self.get_note(note_id)
                if note:
                    note_results.append({
                        "note": note,
                        "score": match["score"],
                        "snippet": self._generate_snippet(note.content, query)
                    })

            return note_results

        except Exception as e:
            print(f"Error in semantic search: {e}")
            # Fall back to simple text search
            return self._simple_text_search(query, max_results)

    def _simple_text_search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Perform a simple text-based search on notes.

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of notes matching the query
        """
        query = query.lower()
        results = []

        for note_data in self.knowledge_graph.data.get("notes", []):
            content = note_data.get("content", "").lower()
            title = note_data.get("title", "").lower()

            # Check if query appears in title or content
            if query in title or query in content:
                # Calculate a simple relevance score
                # Title matches weighted more
                title_score = title.count(query) * 2
                content_score = content.count(query)
                score = (title_score + content_score) / \
                    (len(content) + len(title))

                note = Note.from_dict(note_data)
                results.append({
                    "note": note,
                    "score": score,
                    "snippet": self._generate_snippet(note.content, query)
                })

        # Sort by score and limit results
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]

    def _generate_snippet(self, content: str, query: str, context_size: int = 50) -> str:
        """
        Generate a snippet of text around the query match.

        Args:
            content: The full content to extract snippet from
            query: The search query
            context_size: Number of characters to include before and after match

        Returns:
            Snippet of text
        """
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

    def generate_tags(self, note_id: str) -> List[str]:
        """
        Generate tags for a note using LLM.

        Args:
            note_id: ID of the note

        Returns:
            List of generated tags
        """
        if not self.llm_service:
            return []

        note = self.get_note(note_id)
        if not note:
            raise EntityNotFoundError(f"Note with ID {note_id} not found")

        tags = self.llm_service.extract_tags(note.content)

        # Update the note with the generated tags
        if tags:
            note.tags = tags
            self.update_note(note_id, {"tags": tags})

        return tags

    def summarize_note(self, note_id: str) -> Optional[str]:
        """
        Generate a summary for a note using LLM.

        Args:
            note_id: ID of the note

        Returns:
            Summary text or None if not available
        """
        if not self.llm_service:
            return None

        note = self.get_note(note_id)
        if not note:
            raise EntityNotFoundError(f"Note with ID {note_id} not found")

        return self.llm_service.summarize_text(note.content)

    def get_related_notes(self, note_id: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Get notes related to a specific note.

        Args:
            note_id: ID of the note
            max_results: Maximum number of results to return

        Returns:
            List of related notes with relevance scores
        """
        note = self.get_note(note_id)
        if not note:
            raise EntityNotFoundError(f"Note with ID {note_id} not found")

        # First, check for explicitly connected notes in the knowledge graph
        graph_related = self.knowledge_graph.get_related_entities(
            note_id, "note")
        related_notes = []

        for related in graph_related:
            if related["type"] == "note":
                related_note = self.get_note(related["id"])
                if related_note:
                    related_notes.append({
                        "note": related_note,
                        "score": related["relationship_data"].get("weight", 1.0),
                        "relationship": related["relationship"]
                    })

        # If we have embedding service, also find semantically similar notes
        if self.embedding_service and len(related_notes) < max_results:
            remaining_slots = max_results - len(related_notes)

            try:
                # Get the embedding for this note
                note_embedding = self.embedding_service.get_embedding(note_id)
                if note_embedding is not None:
                    # Search for similar notes
                    results = self.embedding_service.search(
                        note_embedding,
                        remaining_slots + 1,  # +1 to account for the current note
                        filter_by={"type": "note"}
                    )

                    # Add semantically similar notes
                    for match in results.get("matches", []):
                        # Skip the current note
                        if match["id"] == note_id:
                            continue

                        similar_note = self.get_note(match["id"])
                        if similar_note:
                            # Check if this note is already in the results
                            if not any(r["note"].id == similar_note.id for r in related_notes):
                                related_notes.append({
                                    "note": similar_note,
                                    "score": match["score"],
                                    "relationship": "semantic_similarity"
                                })
            except Exception as e:
                print(f"Error finding similar notes: {e}")

        # Sort by score and limit results
        related_notes.sort(key=lambda x: x["score"], reverse=True)
        return related_notes[:max_results]
