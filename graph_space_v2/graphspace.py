from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph
from graph_space_v2.ai.embedding.embedding_service import EmbeddingService
from graph_space_v2.ai.llm.llm_service import LLMService
from graph_space_v2.integrations.document.document_processor import DocumentProcessor
from graph_space_v2.integrations.google.drive_service import GoogleDriveService
from graph_space_v2.core.models.note import Note
from graph_space_v2.core.models.task import Task
from graph_space_v2.core.services.note_service import NoteService
from graph_space_v2.core.services.task_service import TaskService
from graph_space_v2.utils.config.config_loader import ConfigLoader
from graph_space_v2.utils.helpers.path_utils import get_user_data_path, get_config_path

import os
import json
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

        # Initialize services
        self.note_service = NoteService(
            self.knowledge_graph, self.embedding_service, self.llm_service)
        self.task_service = TaskService(
            self.knowledge_graph, self.embedding_service, self.llm_service)

        # Initialize document processor
        self.document_processor = DocumentProcessor(
            llm_service=self.llm_service,
            embedding_service=self.embedding_service,
            max_workers=self.config["document_processing"]["max_workers"],
            chunk_size=self.config["document_processing"]["chunk_size"]
        )

        # Initialize Google Drive service if enabled
        self.google_drive_service = None
        if use_google_drive:
            self.google_drive_service = GoogleDriveService(
                credentials_file=google_credentials_file,
                document_processor=self.document_processor
            )

        # Synchronize components
        self._sync_components()

    def _sync_components(self):
        """Synchronize components after initialization."""
        # Initialize embeddings for the knowledge graph
        if len(self.knowledge_graph.graph.nodes()) > 1:
            print("Training embedding service on graph...")
            self.embedding_service.train_on_graph(self.knowledge_graph.graph)

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

    def process_document(self, file_path: str) -> Dict[str, Any]:
        """
        Process a single document file.

        Args:
            file_path: Path to the document file

        Returns:
            Dictionary with processing results
        """
        return self.document_processor.process_single_file(file_path)

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
        # Embed the query
        query_embedding = self.embedding_service.embed_text(query_text)

        # Search for similar content
        results = self.embedding_service.search(query_embedding, max_results)

        # Generate an answer using LLM
        context = "\n".join([r["text"] for r in results["matches"]])
        answer = self.llm_service.generate_answer(query_text, context)

        # Return results
        return {
            "query": query_text,
            "answer": answer,
            "sources": results["matches"]
        }
