from typing import Dict, List, Any, Optional, Set, Union
from datetime import datetime, timedelta
import uuid
import logging # Added

from graph_space_v2.core.models.task import Task
from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph
from graph_space_v2.ai.embedding.embedding_service import EmbeddingService
from graph_space_v2.ai.llm.llm_service import LLMService
from graph_space_v2.utils.errors.exceptions import EntityNotFoundError, TaskServiceError, EmbeddingServiceError, LLMServiceError


class TaskService:
    logger = logging.getLogger(__name__) # Added logger instance

    def __init__(
        self,
        knowledge_graph: KnowledgeGraph,
        embedding_service: Optional[EmbeddingService] = None,
        llm_service: Optional[LLMService] = None
    ):
        self.knowledge_graph = knowledge_graph
        self.embedding_service = embedding_service
        self.llm_service = llm_service

    def add_task(self, task_data: Dict[str, Any]) -> str:
        if not isinstance(task_data, Task):
            # Generate title using LLM if available and not provided
            if self.llm_service and self.llm_service.enabled and not task_data.get("title") and task_data.get("description"):
                try:
                    title = self.llm_service.generate_title(
                        task_data["description"])
                    task_data["title"] = title or "Untitled Task"
                except Exception as e:
                    self.logger.error(f"Error generating title via LLM for new task: {e}", exc_info=True)

            # Generate tags using LLM if available and not provided
            if self.llm_service and self.llm_service.enabled and not task_data.get("tags") and task_data.get("description"):
                try:
                    tags = self.llm_service.extract_tags(task_data["description"])
                    task_data["tags"] = tags
                except Exception as e:
                    self.logger.error(f"Error extracting tags via LLM for new task: {e}", exc_info=True)

            # Set timestamps if not provided
            now = datetime.now().isoformat()
            if not task_data.get("created_at"):
                task_data["created_at"] = now
            if not task_data.get("updated_at"):
                task_data["updated_at"] = now

            task = Task.from_dict(task_data)
            task_data = task.to_dict()

        # Create embeddings if available and description is provided
        if self.embedding_service and task_data.get("description"):
            try:
                embedding = self.embedding_service.embed_text(
                    task_data["description"])
                self.embedding_service.store_embedding(
                    task_data["id"], embedding, {"type": "task"})
            except EmbeddingServiceError as e:
                self.logger.error(f"Embedding creation failed for task '{task_data.get('title', 'Untitled')}': {e}", exc_info=True)
                # Optionally re-raise as TaskServiceError or let it proceed without embedding
            except Exception as e: # Catch any other unexpected error from embedding service
                self.logger.error(f"Unexpected error during embedding creation for task '{task_data.get('title', 'Untitled')}': {e}", exc_info=True)

        try:
            new_task_id = self.knowledge_graph.add_task(task_data)
            if not new_task_id:
                self.logger.error(f"KnowledgeGraph.add_task failed for task '{task_data.get('title', 'Untitled')}'")
                raise TaskServiceError(f"Failed to add task '{task_data.get('title', 'Untitled')}' to knowledge graph.")
            self.logger.info(f"Task '{new_task_id}' added successfully.")
            return new_task_id
        except Exception as e:
            self.logger.error(f"Error adding task '{task_data.get('title', 'Untitled')}' to knowledge graph: {e}", exc_info=True)
            raise TaskServiceError(f"Error adding task '{task_data.get('title', 'Untitled')}' to knowledge graph: {e}")


    def get_task(self, task_id: str) -> Task:
        task_data = self.knowledge_graph.get_task(task_id)
        if not task_data:
            raise TaskServiceError(f"Task with ID {task_id} not found.")
        try:
            return Task.from_dict(task_data)
        except Exception as e:
            raise TaskServiceError(f"Error converting data to Task object for ID {task_id}: {e}")

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        Get all tasks as dictionaries instead of Task objects.

        Returns:
            List of task dictionaries
        """
        try:
            tasks_data = self.knowledge_graph.data.get("tasks", [])
            # Returning list of dicts as per original method's docstring after correction
            return [Task.from_dict(task_d).to_dict() for task_d in tasks_data]
        except Exception as e:
            raise TaskServiceError(f"Failed to retrieve all tasks: {e}")

    def update_task(self, task_id: str, task_data: Dict[str, Any]) -> Task:
        # Set the updated_at timestamp
        task_data["updated_at"] = datetime.now().isoformat()

        # Conditionally generate title and tags if description is being updated and they are missing
        if self.llm_service and self.llm_service.enabled and task_data.get("description"): # Check if LLM is enabled and description is present
            current_title = task_data.get("title", "").strip()
            if not current_title: # If title is empty or not provided
                try:
                    self.logger.info(f"Attempting to generate title for task {task_id} as it's missing/empty during update.")
                    generated_title = self.llm_service.generate_title(task_data["description"])
                    if generated_title:
                        task_data["title"] = generated_title
                        self.logger.info(f"Generated title for task {task_id}: '{generated_title}'")
                except LLMServiceError as e:
                    self.logger.error(f"LLMServiceError generating title for task {task_id} during update: {e}", exc_info=True)
                except Exception as e:
                    self.logger.error(f"Unexpected error generating title for task {task_id} during update: {e}", exc_info=True)

            current_tags = task_data.get("tags", [])
            if not current_tags: # If tags are empty or not provided
                try:
                    self.logger.info(f"Attempting to generate tags for task {task_id} as they are missing/empty during update.")
                    generated_tags = self.llm_service.extract_tags(task_data["description"])
                    if generated_tags:
                        task_data["tags"] = generated_tags
                        self.logger.info(f"Generated tags for task {task_id}: {generated_tags}")
                except LLMServiceError as e:
                    self.logger.error(f"LLMServiceError extracting tags for task {task_id} during update: {e}", exc_info=True)
                except Exception as e:
                    self.logger.error(f"Unexpected error extracting tags for task {task_id} during update: {e}", exc_info=True)

        # Update the task in the knowledge graph
        success = self.knowledge_graph.update_task(task_id, task_data)

        if not success:
            # Check if task exists to give a more specific error
            if not self.knowledge_graph.get_task(task_id):
                 raise TaskServiceError(f"Task with ID {task_id} not found, cannot update.")
            raise TaskServiceError(f"Failed to update task with ID {task_id} in knowledge graph.")

        # Update embedding if description was updated
        if self.embedding_service and "description" in task_data and task_data["description"]:
            try:
                embedding = self.embedding_service.embed_text(
                    task_data["description"])
                updated_embedding = self.embedding_service.update_embedding(task_id, embedding)
                if not updated_embedding: # if update_embedding returns boolean (some services might do this)
                    self.logger.warning(f"Failed to update embedding for task {task_id} via embedding service, but task data was updated.")
            except EmbeddingServiceError as e:
                self.logger.error(f"EmbeddingServiceError while updating embedding for task {task_id}: {e}", exc_info=True)
            except Exception as e:
                self.logger.error(f"Unexpected error updating embedding for task {task_id}: {e}", exc_info=True)

        updated_task = self.get_task(task_id) # get_task will raise if not found
        return updated_task


    def delete_task(self, task_id: str) -> bool:
        # Delete from embedding service if available
        if self.embedding_service:
            try:
                deleted_embedding = self.embedding_service.delete_embedding(task_id)
                if not deleted_embedding: # if it returns boolean (some services might do this)
                     self.logger.warning(f"Embedding for task {task_id} not found or not deleted by embedding service (returned False).")
            except EmbeddingServiceError as e:
                self.logger.error(f"EmbeddingServiceError while deleting embedding for task {task_id}: {e}", exc_info=True)
            except Exception as e:
                self.logger.error(f"Unexpected error deleting embedding for task {task_id}: {e}", exc_info=True)

        deleted_from_kg = self.knowledge_graph.delete_task(task_id)
        if not deleted_from_kg:
            if not self.knowledge_graph.get_task(task_id): # Check if it existed
                raise TaskServiceError(f"Task with ID {task_id} not found for deletion.")
            raise TaskServiceError(f"Failed to delete task with ID {task_id} from knowledge graph.")
        return True

    def get_tasks_by_status(self, status: str) -> List[Task]: # Assumes get_all_tasks returns list of Task objects
        all_task_dicts = self.get_all_tasks() # This now returns list of dicts
        return [Task.from_dict(task_dict) for task_dict in all_task_dicts if task_dict.get("status") == status]

    def get_tasks_by_project(self, project: str) -> List[Task]:
        all_task_dicts = self.get_all_tasks()
        return [Task.from_dict(task_dict) for task_dict in all_task_dicts if task_dict.get("project") == project]

    def get_tasks_by_tag(self, tag: str) -> List[Task]:
        all_task_dicts = self.get_all_tasks()
        return [Task.from_dict(task_dict) for task_dict in all_task_dicts if tag in task_dict.get("tags", [])]

    def get_overdue_tasks(self) -> List[Task]:
        all_task_dicts = self.get_all_tasks()
        now = datetime.now()
        overdue_tasks = []
        for task_dict in all_task_dicts:
            task = Task.from_dict(task_dict)
            if task.due_date and task.status != Task.STATUS_COMPLETED and \
               datetime.fromisoformat(task.due_date.replace("Z", "+00:00")) < now:
                overdue_tasks.append(task)
        return overdue_tasks

    def get_tasks_due_soon(self, days: int = 3) -> List[Task]:
        all_task_dicts = self.get_all_tasks()
        now = datetime.now()
        soon = now + timedelta(days=days)
        due_soon_tasks = []
        for task_dict in all_task_dicts:
            task = Task.from_dict(task_dict)
            if task.due_date and task.status != Task.STATUS_COMPLETED and \
               now <= datetime.fromisoformat(task.due_date.replace("Z", "+00:00")) <= soon:
                due_soon_tasks.append(task)
        return due_soon_tasks

    def get_recurring_tasks(self) -> List[Task]:
        all_task_dicts = self.get_all_tasks()
        return [Task.from_dict(task_dict) for task_dict in all_task_dicts if task_dict.get("is_recurring")]

    def get_tasks_by_priority(self, priority: str) -> List[Task]:
        all_task_dicts = self.get_all_tasks()
        return [Task.from_dict(task_dict) for task_dict in all_task_dicts if task_dict.get("priority") == priority]

    def mark_task_completed(self, task_id: str) -> Task:
        task = self.get_task(task_id) # Raises TaskServiceError if not found
        task.mark_completed()
        # update_task will raise error if update fails
        return self.update_task(task_id, task.to_dict())


    def mark_task_in_progress(self, task_id: str) -> Task:
        task = self.get_task(task_id) # Raises TaskServiceError if not found
        task.status = Task.STATUS_IN_PROGRESS
        task.updated_at = datetime.now().isoformat()
        # update_task will raise error if update fails
        return self.update_task(task_id, task.to_dict())


    def search_tasks(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        if self.embedding_service:
            try:
                query_embedding = self.embedding_service.embed_text(query)
                # Assuming search_embeddings is the correct method name, and it exists.
                # If not, this would be self.embedding_service.search(...)
                search_results = self.embedding_service.search(
                    query_embedding, filter_by={"type": "task"}, limit=max_results
                ) # Corrected to use .search and filter_by

                enriched_results = []
                for result in search_results.get("matches", []): # search returns a dict with "matches"
                    task_id_match = result["id"]
                    try:
                        task = self.get_task(task_id_match) # get_task raises if not found
                        enriched_results.append({
                            "task": task.to_dict(),
                            "score": result["score"],
                            "snippet": self._generate_snippet(task.description, query)
                        })
                    except TaskServiceError as e: # Catch if a task from search results is problematic
                        self.logger.warning(f"Could not retrieve task {task_id_match} from search results during semantic search: {e}")
                return enriched_results
            except EmbeddingServiceError as e:
                self.logger.error(f"Semantic search for tasks failed due to embedding error: {e}. Falling back to simple search.", exc_info=True)
            except Exception as e: # Catch other unexpected errors
                self.logger.error(f"Unexpected error in semantic search for tasks: {e}. Falling back to simple search.", exc_info=True)

        # Fall back to simple text search if embedding search fails or service not available
        return self._simple_text_search(query, max_results)

    def _simple_text_search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        results = []
        all_task_dicts = []
        try:
            all_task_dicts = self.get_all_tasks() # This now returns list of dicts
        except TaskServiceError as e:
            self.logger.error(f"Error getting all tasks for simple text search: {e}", exc_info=True)
            return [] # Return empty if cannot get tasks

        for task_dict in all_task_dicts:
            task = Task.from_dict(task_dict) # Convert to Task object for easier field access
            score = 0
            if query_lower in task.title.lower():
                score += 3
            if task.description and query_lower in task.description.lower():
                score += 2
            if any(query_lower in tag.lower() for tag in task.tags):
                score += 1

            if score > 0:
                results.append({
                    "task": task.to_dict(), # Convert back to dict for consistent output
                    "score": score,
                    "snippet": self._generate_snippet(task.description, query_lower)
                })

        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:max_results]

    def _generate_snippet(self, content: str, query: str, context_size: int = 50) -> str:
        if not content:
            return ""

        query = query.lower()
        content_lower = content.lower()

        # Find the position of the query in the content
        pos = content_lower.find(query)
        if pos == -1:
            # If the exact query isn't found, return the first part of the content
            return content[:100] + "..." if len(content) > 100 else content

        # Calculate snippet bounds
        start = max(0, pos - context_size)
        end = min(len(content), pos + len(query) + context_size)

        # Add ellipsis if we're not at the beginning/end
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(content) else ""

        return prefix + content[start:end] + suffix

    def process_recurring_tasks(self) -> List[Task]:
        new_tasks_created = []
        try:
            recurring_tasks_list = self.get_recurring_tasks() # Uses refactored get_all_tasks
        except TaskServiceError as e:
            raise TaskServiceError(f"Failed to process recurring tasks due to error fetching tasks: {e}")

        for task_obj in recurring_tasks_list:
            try:
                if task_obj.is_recurring and task_obj.recurrence_enabled:
                    if task_obj.recurrence_next_run:
                        next_run_dt = datetime.fromisoformat(task_obj.recurrence_next_run.replace("Z", "+00:00"))
                        if next_run_dt <= datetime.now():
                            new_task_data = {
                                "title": f"{task_obj.title} ({datetime.now().strftime('%Y-%m-%d')})",
                                "description": task_obj.description,
                                "status": Task.STATUS_PENDING,
                                "priority": task_obj.priority,
                                "tags": task_obj.tags + ["generated_from_recurring"],
                                "project": task_obj.project,
                                "due_date": (datetime.now() + timedelta(days=1)).isoformat(), # Example: due next day
                                # Copy other relevant fields from task_obj as needed
                            }

                            new_task_id = self.add_task(new_task_data) # add_task is refactored
                            created_task = self.get_task(new_task_id) # get_task is refactored
                            new_tasks_created.append(created_task)

                            # Update the original recurring task's next run date
                            next_recurrence_date_iso = task_obj.calculate_next_recurrence()
                            if next_recurrence_date_iso:
                                self.update_task(task_obj.id, {"recurrence_next_run": next_recurrence_date_iso})
                            else: # Handle case where recurrence might end
                                self.update_task(task_obj.id, {"recurrence_enabled": False})
            except Exception as e: # Catch errors related to a single recurring task processing
                self.logger.error(f"Error processing individual recurring task {task_obj.id if task_obj else 'Unknown'}: {e}", exc_info=True)
                # Optionally, collect these errors if a partial success/failure report is needed.
        return new_tasks_created
