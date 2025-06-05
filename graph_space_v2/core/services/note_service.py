from typing import Dict, List, Any, Optional, Set, Union
from datetime import datetime
import uuid
import traceback
import logging # Added

from graph_space_v2.core.models.note import Note
from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph
from graph_space_v2.ai.embedding.embedding_service import EmbeddingService
from graph_space_v2.ai.llm.llm_service import LLMService
from graph_space_v2.utils.errors.exceptions import EntityNotFoundError, NoteServiceError, EmbeddingServiceError, LLMServiceError


class NoteService:
    """Service class for note-related operations."""

    logger = logging.getLogger(__name__) # Added logger instance

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
            if self.llm_service and self.llm_service.enabled and not note_data.get("title") and note_data.get("content"):
                try:
                    title = self.llm_service.generate_title(note_data["content"])
                    note_data["title"] = title or "Untitled Note"
                except Exception as e: # Catch errors from LLM call
                    self.logger.error(f"Error generating title via LLM for new note: {e}", exc_info=True)


            if self.llm_service and self.llm_service.enabled and not note_data.get("tags") and note_data.get("content"):
                try:
                    tags = self.llm_service.extract_tags(note_data["content"])
                    note_data["tags"] = tags
                except Exception as e: # Catch errors from LLM call
                    self.logger.error(f"Error extracting tags via LLM for new note: {e}", exc_info=True)

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
            except EmbeddingServiceError as e: # More specific catch
                # Re-raise as NoteServiceError or let EmbeddingServiceError propagate if desired
                # For this task, let's wrap it as NoteServiceError indicating the context
                self.logger.error(f"Embedding failed during note creation for '{note_data.get('title', 'Untitled')}'. Error: {e}", exc_info=True)
                raise NoteServiceError(f"Embedding failed during note creation for '{note_data.get('title', 'Untitled')}': {e}")
            except Exception as e: # Catch other unexpected errors from embedding service
                self.logger.error(f"Unhandled error creating embedding for note '{note_data.get('title', 'Untitled')}': {e}", exc_info=True)
                raise NoteServiceError(f"Unexpected error during embedding for note '{note_data.get('title', 'Untitled')}': {e}")

        try:
            # Add to knowledge graph
            new_note_id = self.knowledge_graph.add_note(note_data)
            # Assuming add_note in KnowledgeGraph now raises its own specific error or returns a clear failure indicator.
            # If add_note could return None/False on failure without raising:
            if not new_note_id:
                self.logger.error(f"KnowledgeGraph.add_note failed for note '{note_data.get('title', 'Untitled')}'")
                raise NoteServiceError(f"Failed to add note '{note_data.get('title', 'Untitled')}' to knowledge graph.")
            self.logger.info(f"Note '{new_note_id}' added successfully.")
            return new_note_id
        except Exception as e: # Catch potential errors from knowledge_graph.add_note
            self.logger.error(f"Error adding note '{note_data.get('title', 'Untitled')}' to knowledge graph: {e}", exc_info=True)
            raise NoteServiceError(f"Error adding note '{note_data.get('title', 'Untitled')}' to knowledge graph: {e}")


    def get_note(self, note_id: str) -> Optional[Note]:
        """
        Get a note by ID.

        Args:
            note_id: ID of the note to retrieve

        Returns:
            Note instance or None if not found
        """
        note_data = self.knowledge_graph.get_note(note_id)
        if not note_data:
            raise NoteServiceError(f"Note with ID {note_id} not found.")
        try:
            return Note.from_dict(note_data)
        except Exception as e:
            raise NoteServiceError(f"Error converting data to Note object for ID {note_id}: {e}")

    def get_all_notes(self) -> List[Dict[str, Any]]:
        """
        Get all notes.

        Returns:
            List of note dictionaries
        """
        try:
            self.logger.debug(f"Knowledge graph data structure for get_all_notes: {self.knowledge_graph.data.keys()}")

            if "notes" not in self.knowledge_graph.data:
                self.logger.warning("Notes array not found in knowledge graph data during get_all_notes. Initializing empty list.")
                self.knowledge_graph.data["notes"] = [] # Should this modify KG state or just return []?

            raw_notes = self.knowledge_graph.data.get("notes", [])
            self.logger.info(f"Retrieved {len(raw_notes)} raw notes from knowledge graph.")
            return raw_notes
        except Exception as e:
            self.logger.error(f"Error in get_all_notes: {e}", exc_info=True)
            raise NoteServiceError(f"Failed to retrieve all notes: {e}")

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

        # Conditionally generate title and tags if content is being updated and they are missing
        if self.llm_service and self.llm_service.enabled and note_data.get("content"): # Check if LLM is enabled and content is present
            current_title = note_data.get("title", "").strip()
            if not current_title: # If title is empty or not provided
                try:
                    self.logger.info(f"Attempting to generate title for note {note_id} as it's missing/empty during update.")
                    generated_title = self.llm_service.generate_title(note_data["content"])
                    if generated_title:
                        note_data["title"] = generated_title
                        self.logger.info(f"Generated title for note {note_id}: '{generated_title}'")
                except LLMServiceError as e:
                    self.logger.error(f"LLMServiceError generating title for note {note_id} during update: {e}", exc_info=True)
                except Exception as e:
                    self.logger.error(f"Unexpected error generating title for note {note_id} during update: {e}", exc_info=True)

            current_tags = note_data.get("tags", [])
            if not current_tags: # If tags are empty or not provided
                try:
                    self.logger.info(f"Attempting to generate tags for note {note_id} as they are missing/empty during update.")
                    generated_tags = self.llm_service.extract_tags(note_data["content"])
                    if generated_tags:
                        note_data["tags"] = generated_tags
                        self.logger.info(f"Generated tags for note {note_id}: {generated_tags}")
                except LLMServiceError as e:
                    self.logger.error(f"LLMServiceError extracting tags for note {note_id} during update: {e}", exc_info=True)
                except Exception as e:
                    self.logger.error(f"Unexpected error extracting tags for note {note_id} during update: {e}", exc_info=True)

        # Update the note in the knowledge graph
        success = self.knowledge_graph.update_note(note_id, note_data)

        if not success:
            # Attempt to get the note to see if it exists, to provide a more specific error
            existing_note = self.knowledge_graph.get_note(note_id)
            if not existing_note:
                raise NoteServiceError(f"Note with ID {note_id} not found, cannot update.")
            raise NoteServiceError(f"Failed to update note with ID {note_id} in knowledge graph.")

        # Update embedding if content was updated
        if self.embedding_service and "content" in note_data:
            try:
                embedding = self.embedding_service.embed_text(
                    note_data["content"])
                # Assuming update_embedding might return bool or raise its own error
                updated_embedding = self.embedding_service.update_embedding(note_id, embedding)
                if not updated_embedding: # If it returns boolean false (some services might do this)
                     self.logger.warning(f"Failed to update embedding for note {note_id} via embedding service, but note data was updated.")
            except EmbeddingServiceError as e:
                self.logger.error(f"EmbeddingServiceError while updating embedding for note {note_id}: {e}", exc_info=True)
                # Depending on policy, we might re-raise or just log. Logged for now.
                # raise NoteServiceError(f"Note data updated, but failed to update embedding for note {note_id}: {e}")
            except Exception as e:
                self.logger.error(f"Unexpected error updating embedding for note {note_id}: {e}", exc_info=True)

        updated_note_obj = self.get_note(note_id) # get_note will raise if not found after supposed update
        if not updated_note_obj: # Should be caught by get_note's internal error handling
            raise NoteServiceError(f"Failed to retrieve note {note_id} after update, data inconsistency likely.")
        return updated_note_obj


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
                deleted_embedding = self.embedding_service.delete_embedding(note_id)
                if not deleted_embedding: # if delete_embedding returns boolean (some services might do this)
                    self.logger.warning(f"Embedding for note {note_id} not found or not deleted by embedding service (returned False).")
            except EmbeddingServiceError as e: # Catch specific service error
                 self.logger.error(f"EmbeddingServiceError while deleting embedding for note {note_id}: {e}", exc_info=True)
                 # Logged, proceeding with KG deletion as per original logic.
            except Exception as e: # Catch other unexpected errors
                self.logger.error(f"Unexpected error deleting embedding for note {note_id}: {e}", exc_info=True)

        # Delete from knowledge graph
        deleted_from_kg = self.knowledge_graph.delete_note(note_id)
        if not deleted_from_kg:
            # Check if it didn't exist in the first place
            if not self.knowledge_graph.get_note(note_id): # Assuming get_note is cheap or cached
                 raise NoteServiceError(f"Note with ID {note_id} not found for deletion.")
            raise NoteServiceError(f"Failed to delete note with ID {note_id} from knowledge graph.")
        return True # If it reaches here, KG deletion was successful

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
                    note_id_match = match["id"]
                    # get_note will raise NoteServiceError if a note found by search doesn't exist,
                    # which would be a data inconsistency.
                    try:
                        note = self.get_note(note_id_match) # Uses the updated get_note
                        if note: # Should always be true if get_note doesn't raise
                            note_results.append({
                                "note": note,
                                "score": match["score"],
                                "snippet": self._generate_snippet(note.content, query)
                            })
                    except NoteServiceError as e: # Catch if a specific note ID from search results is problematic
                        self.logger.warning(f"Could not retrieve note {note_id_match} from search results during semantic search: {e}")
                        # Continue to next match
            return note_results

        except EmbeddingServiceError as e:
            self.logger.error(f"Semantic search failed due to embedding error: {e}. Falling back to simple search.", exc_info=True)
            return self._simple_text_search(query, max_results) # Fallback
        except Exception as e: # Catch other unexpected errors
            self.logger.error(f"Unexpected error in semantic search: {e}. Falling back to simple search.", exc_info=True)
            return self._simple_text_search(query, max_results) # Fallback

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
        if not self.llm_service or not self.llm_service.enabled:
            self.logger.warning("LLM Service is not available or disabled. Skipping tag generation.")
            return []

        note = self.get_note(note_id) # This will raise NoteServiceError if not found

        try:
            tags = self.llm_service.extract_tags(note.content)
        except LLMServiceError as e: # Catch specific LLM errors
            self.logger.error(f"LLMServiceError while generating tags for note {note_id}: {e}", exc_info=True)
            raise NoteServiceError(f"Failed to generate tags for note {note_id} due to LLM error: {e}")
        except Exception as e: # Catch other unexpected errors from LLM service
            self.logger.error(f"Unexpected error generating tags for note {note_id}: {e}", exc_info=True)
            raise NoteServiceError(f"Unexpected error generating tags for note {note_id}: {e}")


        # Update the note with the generated tags
        if tags:
            try:
                # Use a subset of note data for update, just the tags
                self.update_note(note_id, {"tags": list(set(note.tags + tags))}) # Merge and deduplicate
            except NoteServiceError as e:
                self.logger.error(f"Failed to update note {note_id} with newly generated tags: {e}", exc_info=True)
                # Depending on desired behavior, could re-raise or just return tags without saving.
                # For now, returning tags even if saving them back to note failed.
        return tags

    def summarize_note(self, note_id: str) -> Optional[str]:
        """
        Generate a summary for a note using LLM.

        Args:
            note_id: ID of the note

        Returns:
            Summary text or None if not available
        """
        if not self.llm_service or not self.llm_service.enabled:
            self.logger.warning("LLM Service is not available or disabled. Cannot generate summary.")
            return None

        note = self.get_note(note_id) # Raises NoteServiceError if not found

        try:
            summary = self.llm_service.summarize_text(note.content)
            return summary
        except LLMServiceError as e:
            self.logger.error(f"LLMServiceError while summarizing note {note_id}: {e}", exc_info=True)
            raise NoteServiceError(f"Failed to summarize note {note_id} due to LLM error: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error summarizing note {note_id}: {e}", exc_info=True)
            raise NoteServiceError(f"Unexpected error summarizing note {note_id}: {e}")


    def get_related_notes(self, note_id: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Get notes related to a specific note.

        Args:
            note_id: ID of the note
            max_results: Maximum number of results to return

        Returns:
            List of related notes with relevance scores
        """
        note = self.get_note(note_id) # Raises NoteServiceError if not found

        # First, check for explicitly connected notes in the knowledge graph
        related_notes: List[Dict[str, Any]] = []
        try:
            graph_related = self.knowledge_graph.get_related_entities(note_id, "note")
            for related in graph_related:
                if related["type"] == "note":
                    # get_note internally handles NoteServiceError if related["id"] is somehow invalid
                    related_note_obj = self.get_note(related["id"])
                    if related_note_obj: # Should be true if no error
                        related_notes.append({
                            "note": related_note_obj,
                            "score": related.get("relationship_data", {}).get("weight", 1.0),
                            "relationship": related.get("relationship", "graph_related")
                        })
        except Exception as e: # Catch errors from knowledge_graph.get_related_entities
            self.logger.error(f"Error fetching graph-related notes for {note_id} from KnowledgeGraph: {e}", exc_info=True)
            # Potentially raise NoteServiceError or just log and proceed to semantic search.
            # For now, logging and proceeding.

        # If we have embedding service, also find semantically similar notes
        if self.embedding_service and len(related_notes) < max_results:
            remaining_slots = max_results - len(related_notes)
            if remaining_slots > 0: # Only search if we need more notes
                try:
                    note_embedding = self.embedding_service.get_embedding(note_id)
                    if note_embedding is not None:
                        search_results = self.embedding_service.search(
                            note_embedding,
                            remaining_slots + 1,  # +1 to exclude self if present
                            filter_by={"type": "note"}
                        )
                        for match in search_results.get("matches", []):
                            if match["id"] == note_id:
                                continue
                            # Check if we already have this note from graph relationships
                            if any(r["note"].id == match["id"] for r in related_notes):
                                continue

                            similar_note_obj = self.get_note(match["id"]) # get_note handles errors
                            if similar_note_obj:
                                related_notes.append({
                                    "note": similar_note_obj,
                                    "score": match["score"],
                                    "relationship": "semantic_similarity"
                                })
                                if len(related_notes) >= max_results:
                                    break
                except EmbeddingServiceError as e:
                    self.logger.error(f"EmbeddingServiceError while finding semantically related notes for {note_id}: {e}", exc_info=True)
                    # Optionally: raise NoteServiceError(...)
                except Exception as e: # Catch other unexpected errors
                    self.logger.error(f"Unexpected error finding semantically similar notes for {note_id}: {e}", exc_info=True)

        # Sort by score and limit results
        related_notes.sort(key=lambda x: x.get("score", 0.0), reverse=True)
        return related_notes[:max_results]
