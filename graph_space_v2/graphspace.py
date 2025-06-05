from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph
from graph_space_v2.ai.embedding.embedding_service import EmbeddingService
from graph_space_v2.ai.llm.llm_service import LLMService
from graph_space_v2.integrations.document.document_processor import DocumentProcessor
from graph_space_v2.integrations.google.drive_service import GoogleDriveService
from graph_space_v2.core.models.note import Note
from graph_space_v2.core.models.task import Task
from graph_space_v2.core.services.note_service import NoteService
from graph_space_v2.core.services.task_service import TaskService
from graph_space_v2.core.services.query_service import QueryService
from graph_space_v2.utils.config.config_loader import ConfigLoader
from graph_space_v2.utils.helpers.path_utils import get_user_data_path, get_config_path

import os
import json
import logging # Added
from typing import Dict, Any, Optional
from datetime import datetime


class GraphSpace:
    """
    GraphSpace is the main application class that integrates all components:
    - Knowledge graph for data storage and relationships
    - Embedding services for text and semantic analysis
    - LLM services for natural language processing
    - Document processing for importing external content
    - Integration with external services like Google Drive
    """
    logger = logging.getLogger(__name__) # Added logger instance

    def __init__(
        self,
        data_path: str,
        config_path: str,
        use_api: bool = True,
        api_key: Optional[str] = None,
        use_google_drive: bool = False,
        google_credentials_file: Optional[str] = None
    ):
        """
        Initialize GraphSpace.

        Args:
            data_path: Path to user data file
            config_path: Path to configuration file
            use_api: Whether to use API for LLM
            api_key: API key for LLM service
            use_google_drive: Whether to enable Google Drive integration
            google_credentials_file: Path to Google credentials file
        """
        # Load configuration
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load_config()

        # Store parameters
        self.use_google_drive = use_google_drive
        self.google_credentials_file = google_credentials_file

        # Extract API key from environment if not provided
        if api_key is None and "DEEPSEEK_API_KEY" in os.environ:
            api_key = os.environ["DEEPSEEK_API_KEY"]

        # Initialize core components
        self.knowledge_graph = KnowledgeGraph(data_path=data_path)
        self.embedding_service = EmbeddingService(
            model_name=self.config["embedding"]["model"],
            dimension=self.config["embedding"]["dimension"]
        )
        self.llm_service = LLMService(
            api_key=api_key,
            model_name=self.config["llm"]["model"],
            fallback_model_name=self.config["llm"]["fallback_model"],
            use_api=use_api
        )

        # Check config to globally disable LLMService if needed
        # Default to True if the 'llm' section or 'llm_enabled' key is missing
        llm_enabled_config = self.config.get("llm", {}).get("llm_enabled", True)
        if not llm_enabled_config:
            if self.llm_service: # Should always exist, but good practice to check
                self.llm_service.enabled = False
                self.logger.info("LLMService has been disabled based on 'llm_enabled: false' in configuration.")
        elif not self.llm_service.enabled: # If it was already disabled (e.g. no API key)
             self.logger.warning("LLMService is not enabled (e.g., API key missing or provider issue), overriding 'llm_enabled: true' from config.")
        else:
            self.logger.info("LLMService is enabled.")


        # Initialize services directly as top-level attributes
        self.note_service = NoteService(
            self.knowledge_graph, self.embedding_service, self.llm_service)
        self.task_service = TaskService(
            self.knowledge_graph, self.embedding_service, self.llm_service)
        self.query_service = QueryService(
            self.knowledge_graph, self.embedding_service, self.llm_service)

        # For backward compatibility with existing code
        self.core = type('CoreNamespace', (), {})()
        self.core.services = type('ServicesNamespace', (), {})()
        self.core.services.note_service = self.note_service
        self.core.services.task_service = self.task_service
        self.core.services.query_service = self.query_service

        # Set up namespace for core.graph for backward compatibility
        self.core.graph = type('GraphNamespace', (), {})()
        self.core.graph.knowledge_graph = self.knowledge_graph
        self.core.graph.node_manager = self.knowledge_graph
        self.core.graph.relationship = self.knowledge_graph

        # Initialize document processor for importing external content
        self.document_processor = DocumentProcessor(
            llm_service=self.llm_service,
            embedding_service=self.embedding_service,
            knowledge_graph=self.knowledge_graph
        )

        # Initialize AI components namespace
        self.ai = type('AINamespace', (), {})()
        self.ai.embedding = type('EmbeddingNamespace', (), {})()
        self.ai.embedding.embedding_service = self.embedding_service
        self.ai.embedding.vector_store = self.embedding_service
        self.ai.llm = type('LLMNamespace', (), {})()
        self.ai.llm.llm_service = self.llm_service
        self.ai.rag = type('RAGNamespace', (), {})()
        self.ai.rag.query = self.query

        # Initialize integrations namespace
        self.integrations = type('IntegrationsNamespace', (), {})()
        self.integrations.document = type('DocumentNamespace', (), {})()
        self.integrations.document.document_processor = self.document_processor

        # Initialize placeholder for Google services
        self._google_drive_service = None
        self._calendar_service = None

        # Synchronize components
        self._sync_components()

    @property
    def google_drive_service(self):
        """
        Lazy-loaded GoogleDriveService property.

        Returns:
            GoogleDriveService instance or None if not enabled
        """
        if not self.use_google_drive:
            return None

        # Return cached instance if available
        if self._google_drive_service is not None:
            return self._google_drive_service

        try:
            # Create GoogleDriveService instance
            self._google_drive_service = GoogleDriveService(
                credentials_file=self.google_credentials_file,
                document_processor=self.document_processor
            )
            self.logger.info("GoogleDriveService instance created.")

            # If web authentication, don't authenticate immediately
            # The API endpoints will handle authentication for each request
            self._google_drive_service.auth_required = True
            self._google_drive_service.authenticated = False

            return self._google_drive_service
        except Exception as e:
            self.logger.warning(f"Failed to initialize Google Drive service: {e}", exc_info=True)
            return None

    def _sync_components(self):
        """Synchronize components after initialization."""
        # Initialize embeddings for the knowledge graph
        if len(self.knowledge_graph.graph.nodes()) > 1:
            self.logger.info("Training embedding service on existing graph data...")
            try:
                self.embedding_service.train_on_graph(self.knowledge_graph.graph)
                self.logger.info("Embedding service training on graph completed.")
            except Exception as e: # Catch specific errors if EmbeddingService raises them
                self.logger.error(f"Error during embedding service training on graph: {e}", exc_info=True)
        else:
            self.logger.info("Skipping embedding service training on graph: Not enough nodes.")


    def add_note(self, note_data: Dict[str, Any]) -> str:
        """
        Add a new note to the system.

        Args:
            note_data: Dictionary with note data

        Returns:
            ID of the new note
        """
        return self.note_service.add_note(note_data)

    def get_notes(self):
        """Get all notes."""
        return self.note_service.get_all_notes()

    def get_note(self, note_id: str):
        """Get a note by ID."""
        return self.note_service.get_note(note_id)

    def update_note(self, note_id: str, note_data: Dict[str, Any]):
        """Update a note."""
        return self.note_service.update_note(note_id, note_data)

    def delete_note(self, note_id: str):
        """Delete a note."""
        return self.note_service.delete_note(note_id)

    def add_task(self, task_data: Dict[str, Any]) -> str:
        """Add a new task."""
        return self.task_service.add_task(task_data)

    def get_tasks(self):
        """Get all tasks."""
        return self.task_service.get_all_tasks()

    def get_task(self, task_id: str):
        """Get a task by ID."""
        return self.task_service.get_task(task_id)

    def update_task(self, task_id: str, task_data: Dict[str, Any]):
        """Update a task."""
        return self.task_service.update_task(task_id, task_data)

    def delete_task(self, task_id: str):
        """Delete a task."""
        return self.task_service.delete_task(task_id)

    def get_tasks_by_status(self, status: str):
        """Get tasks by status."""
        return self.task_service.get_tasks_by_status(status)

    def get_tasks_by_project(self, project: str):
        """Get tasks by project."""
        return self.task_service.get_tasks_by_project(project)

    def get_tasks_by_tag(self, tag: str):
        """Get tasks by tag."""
        return self.task_service.get_tasks_by_tag(tag)

    def get_overdue_tasks(self):
        """Get overdue tasks."""
        return self.task_service.get_overdue_tasks()

    def get_tasks_due_soon(self, days: int = 3):
        """Get tasks due soon."""
        return self.task_service.get_tasks_due_soon(days)

    def mark_task_completed(self, task_id: str):
        """Mark a task as completed."""
        return self.task_service.mark_task_completed(task_id)

    def mark_task_in_progress(self, task_id: str):
        """Mark a task as in progress."""
        return self.task_service.mark_task_in_progress(task_id)

    def search_tasks(self, query: str, max_results: int = 5):
        """Search tasks by query."""
        return self.task_service.search_tasks(query, max_results)

    def process_recurring_tasks(self):
        """Process recurring tasks and create new task instances as needed."""
        return self.task_service.process_recurring_tasks()

    def process_document(self, file_path: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process a single document file.

        Args:
            file_path: Path to the document file
            metadata: Optional metadata to associate with the document

        Returns:
            Dictionary with processing results
        """
        return self.document_processor.process_single_file(file_path, metadata=metadata)

    def process_documents(self, directory: str) -> Dict[str, Any]:
        """
        Process multiple documents from a directory.

        Args:
            directory: Path to directory containing documents

        Returns:
            Dictionary with processing results
        """
        return self.document_processor.process_directory(directory)

    def query(self, query_text: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Query the knowledge graph.

        Args:
            query_text: Query text
            max_results: Maximum number of results to return

        Returns:
            Dictionary with query results
        """
        try:
            self.logger.info(f"Processing query: '{query_text}'")

            # Ensure the graph is fully built with all connections
            # Note: build_graph was refactored to _build_graph_from_data_lists
            # For incremental updates, the graph should ideally always be up-to-date.
            # If a full rebuild is desired here, it should be intentional.
            # self.logger.info("Ensuring knowledge graph is up-to-date for query.")
            # self.knowledge_graph._build_graph_from_data_lists() # Example if full rebuild needed. Usually not.

            # Use the query service for natural language queries
            result = self.query_service.query_by_natural_language(query_text)

            # If there's an error in the query service, fall back to basic search
            # QueryService should ideally raise exceptions rather than return dict with "error"
            if isinstance(result, dict) and "error" in result:
                self.logger.warning(f"Error in query service for query '{query_text}': {result['error']}. Falling back to basic search.")

                # Embed the query
                query_embedding = self.embedding_service.embed_text(query_text)

                # Search for similar content
                search_results_dict = self.embedding_service.search(
                    query_embedding, max_results)

                matches = search_results_dict.get("matches", [])
                context_texts = [r.get("text", "") for r in matches]
                context = "\n".join(filter(None, context_texts))


                self.logger.info(
                    f"Generating answer with {len(matches)} context items for query '{query_text}'.")

                answer = "Could not generate an answer."
                if self.llm_service and self.llm_service.enabled:
                    if context:
                        answer = self.llm_service.generate_answer(query_text, context)
                    else:
                        self.logger.info("No context found from embedding search; attempting to answer query without context.")
                        answer = self.llm_service.generate_text(query_text) # Or a specific method for no-context QA
                else:
                    self.logger.warning("LLMService is not available or disabled. Cannot generate answer for query.")


                return {
                    "query": query_text,
                    "answer": answer,
                    "sources": matches
                }

            return result
        except Exception as e:
            self.logger.error(f"Error processing query '{query_text}': {e}", exc_info=True)
            return {
                "query": query_text,
                "error": str(e),
                "sources": []
            }
