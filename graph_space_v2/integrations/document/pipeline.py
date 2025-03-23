from typing import Dict, List, Any, Optional, Callable
import os
import asyncio
from datetime import datetime
import uuid

from graph_space_v2.integrations.document.document_processor import DocumentProcessor
from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph
from graph_space_v2.ai.llm.llm_service import LLMService


class DocumentPipeline:
    def __init__(
        self,
        document_processor: DocumentProcessor,
        knowledge_graph: Optional[KnowledgeGraph] = None,
        llm_service: Optional[LLMService] = None,
        doc_to_note_enabled: bool = True,
        doc_to_task_enabled: bool = True
    ):
        self.document_processor = document_processor
        self.knowledge_graph = knowledge_graph
        self.llm_service = llm_service
        self.doc_to_note_enabled = doc_to_note_enabled
        self.doc_to_task_enabled = doc_to_task_enabled

    def process_file(self, file_path: str) -> Dict[str, Any]:
        """
        Process a file through the complete pipeline.

        Args:
            file_path: Path to the file to process

        Returns:
            Dictionary with processing results and created entities
        """
        # Process the document
        doc_result = self.document_processor.process_single_file(file_path)

        # If processing failed, return early
        if doc_result.get("error"):
            return {
                "success": False,
                "error": doc_result["error"],
                "file_path": file_path
            }

        created_entities = {
            "notes": [],
            "tasks": []
        }

        # Create knowledge graph entities if needed
        if self.knowledge_graph:
            # Create notes from document if enabled
            if self.doc_to_note_enabled:
                note_id = self._create_note_from_document(doc_result)
                if note_id:
                    created_entities["notes"].append(note_id)

            # Create tasks from document if enabled and LLM is available
            if self.doc_to_task_enabled and self.llm_service:
                task_ids = self._extract_tasks_from_document(doc_result)
                if task_ids:
                    created_entities["tasks"].extend(task_ids)

        # Return complete results
        return {
            "success": True,
            "document": doc_result,
            "created_entities": created_entities,
            "file_path": file_path
        }

    def process_directory(self, directory_path: str) -> Dict[str, Any]:
        """
        Process all documents in a directory through the pipeline.

        Args:
            directory_path: Path to the directory

        Returns:
            Dictionary with processing results
        """
        # Process all documents in the directory
        dir_results = self.document_processor.process_directory(directory_path)

        # Process each document through the full pipeline if needed
        if self.knowledge_graph and (self.doc_to_note_enabled or self.doc_to_task_enabled):
            created_entities = {
                "notes": [],
                "tasks": []
            }

            for doc_result in dir_results["results"]:
                # Skip documents with errors
                if doc_result.get("error"):
                    continue

                # Create notes from document if enabled
                if self.doc_to_note_enabled:
                    note_id = self._create_note_from_document(doc_result)
                    if note_id:
                        created_entities["notes"].append(note_id)

                # Create tasks from document if enabled and LLM is available
                if self.doc_to_task_enabled and self.llm_service:
                    task_ids = self._extract_tasks_from_document(doc_result)
                    if task_ids:
                        created_entities["tasks"].extend(task_ids)

            # Add created entities to results
            dir_results["created_entities"] = created_entities

        return dir_results

    async def process_file_async(self, file_path: str) -> Dict[str, Any]:
        """
        Process a file asynchronously through the complete pipeline.

        Args:
            file_path: Path to the file to process

        Returns:
            Dictionary with processing results
        """
        # Run the processing in a thread pool to avoid blocking
        return await asyncio.to_thread(self.process_file, file_path)

    async def process_directory_async(self, directory_path: str) -> Dict[str, Any]:
        """
        Process a directory asynchronously through the complete pipeline.

        Args:
            directory_path: Path to the directory to process

        Returns:
            Dictionary with processing results
        """
        # Run the processing in a thread pool to avoid blocking
        return await asyncio.to_thread(self.process_directory, directory_path)

    def _create_note_from_document(self, doc_result: Dict[str, Any]) -> Optional[str]:
        """Create a note in the knowledge graph from a document"""
        if not self.knowledge_graph:
            return None

        # Prepare note data
        note_data = {
            "id": str(uuid.uuid4()),
            "title": f"Document: {doc_result['title']}",
            "content": self._prepare_note_content(doc_result),
            "tags": doc_result.get("topics", []) + ["document", "imported"],
            "source": {
                "type": "document",
                "file_path": doc_result["file_path"]
            },
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        # Add to knowledge graph
        try:
            note_id = self.knowledge_graph.add_note(note_data)
            return note_id
        except Exception as e:
            print(f"Error creating note from document: {e}")
            return None

    def _prepare_note_content(self, doc_result: Dict[str, Any]) -> str:
        """Prepare content for a note from document information"""
        summary = doc_result.get("summary", "")
        content = []

        # Add document information
        content.append(f"# {doc_result['title']}")
        content.append(f"File: {doc_result['file_name']}")
        content.append(f"Type: {doc_result['file_type']}")

        # Add summary if available
        if summary:
            content.append("\n## Summary")
            content.append(summary)

        # Add topics if available
        topics = doc_result.get("topics", [])
        if topics:
            content.append("\n## Topics")
            content.append(", ".join(topics))

        # Add entities if available
        entities = doc_result.get("entities", {})
        if entities:
            content.append("\n## Named Entities")
            for entity_type, items in entities.items():
                if items:
                    content.append(f"\n### {entity_type.title()}")
                    content.append(", ".join(items))

        return "\n\n".join(content)

    def _extract_tasks_from_document(self, doc_result: Dict[str, Any]) -> List[str]:
        """Extract tasks from document content using LLM"""
        if not self.llm_service or not self.knowledge_graph:
            return []

        try:
            # Use LLM to extract tasks from the document
            tasks = self.llm_service.extract_tasks(
                doc_result["summary"] or doc_result.get("content", ""))

            # Create tasks in the knowledge graph
            task_ids = []

            for task_desc in tasks:
                task_data = {
                    "id": str(uuid.uuid4()),
                    "title": task_desc,
                    "description": f"Task extracted from document: {doc_result['title']}",
                    "status": "pending",
                    "tags": ["extracted_from_document"],
                    "source": {
                        "type": "document",
                        "file_path": doc_result["file_path"]
                    },
                    "created_at": datetime.now().isoformat(),
                    "updated_at": datetime.now().isoformat()
                }

                task_id = self.knowledge_graph.add_task(task_data)
                task_ids.append(task_id)

            return task_ids

        except Exception as e:
            print(f"Error extracting tasks from document: {e}")
            return []
