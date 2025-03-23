from typing import Dict, List, Any, Optional, Set, Union
from datetime import datetime, timedelta
import uuid

from graph_space_v2.core.models.task import Task
from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph
from graph_space_v2.ai.embedding.embedding_service import EmbeddingService
from graph_space_v2.ai.llm.llm_service import LLMService
from graph_space_v2.utils.errors.exceptions import EntityNotFoundError


class TaskService:
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
            if self.llm_service and not task_data.get("title") and task_data.get("description"):
                title = self.llm_service.generate_title(
                    task_data["description"])
                task_data["title"] = title or "Untitled Task"

            # Generate tags using LLM if available and not provided
            if self.llm_service and not task_data.get("tags") and task_data.get("description"):
                tags = self.llm_service.extract_tags(task_data["description"])
                task_data["tags"] = tags

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
            except Exception as e:
                print(f"Error creating embedding: {e}")

        # Add to knowledge graph
        return self.knowledge_graph.add_task(task_data)

    def get_task(self, task_id: str) -> Optional[Task]:
        task_data = self.knowledge_graph.get_task(task_id)
        if task_data:
            return Task.from_dict(task_data)

        return None

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        Get all tasks as dictionaries instead of Task objects.

        Returns:
            List of task dictionaries
        """
        return [task.to_dict() for task in
                [Task.from_dict(task_data) for task_data in
                 self.knowledge_graph.data.get("tasks", [])]]

    def update_task(self, task_id: str, task_data: Dict[str, Any]) -> Optional[Task]:
        # Set the updated_at timestamp
        task_data["updated_at"] = datetime.now().isoformat()

        # Update the task in the knowledge graph
        success = self.knowledge_graph.update_task(task_id, task_data)

        if success:
            # Update embedding if description was updated
            if self.embedding_service and "description" in task_data:
                try:
                    embedding = self.embedding_service.embed_text(
                        task_data["description"])
                    self.embedding_service.update_embedding(task_id, embedding)
                except Exception as e:
                    print(f"Error updating embedding: {e}")

            # Return the updated task
            return self.get_task(task_id)

        return None

    def delete_task(self, task_id: str) -> bool:
        # Delete from embedding service if available
        if self.embedding_service:
            try:
                self.embedding_service.delete_embedding(task_id)
            except Exception as e:
                print(f"Error deleting embedding: {e}")

        # Delete from knowledge graph
        return self.knowledge_graph.delete_task(task_id)

    def get_tasks_by_status(self, status: str) -> List[Task]:
        return [task for task in self.get_all_tasks() if task.status == status]

    def get_tasks_by_project(self, project: str) -> List[Task]:
        return [task for task in self.get_all_tasks() if task.project == project]

    def get_tasks_by_tag(self, tag: str) -> List[Task]:
        return [task for task in self.get_all_tasks() if tag in task.tags]

    def get_overdue_tasks(self) -> List[Task]:
        tasks = self.get_all_tasks()
        now = datetime.now()
        return [
            task for task in tasks
            if task.due_date and task.status != Task.STATUS_COMPLETED and
            datetime.fromisoformat(task.due_date.replace("Z", "+00:00")) < now
        ]

    def get_tasks_due_soon(self, days: int = 3) -> List[Task]:
        tasks = self.get_all_tasks()
        now = datetime.now()
        soon = now + timedelta(days=days)
        return [
            task for task in tasks
            if task.due_date and task.status != Task.STATUS_COMPLETED and
            now <= datetime.fromisoformat(
                task.due_date.replace("Z", "+00:00")) <= soon
        ]

    def get_recurring_tasks(self) -> List[Task]:
        return [task for task in self.get_all_tasks() if task.is_recurring]

    def get_tasks_by_priority(self, priority: str) -> List[Task]:
        return [task for task in self.get_all_tasks() if task.priority == priority]

    def mark_task_completed(self, task_id: str) -> Optional[Task]:
        task = self.get_task(task_id)
        if not task:
            return None

        task.mark_completed()
        self.knowledge_graph.update_task(task_id, task.to_dict())
        return task

    def mark_task_in_progress(self, task_id: str) -> Optional[Task]:
        task = self.get_task(task_id)
        if not task:
            return None

        task.status = Task.STATUS_IN_PROGRESS
        task.updated_at = datetime.now().isoformat()
        self.knowledge_graph.update_task(task_id, task.to_dict())
        return task

    def search_tasks(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        if self.embedding_service:
            try:
                # Use semantic search if embedding service is available
                query_embedding = self.embedding_service.embed_text(query)
                results = self.embedding_service.search_embeddings(
                    query_embedding, filter_metadata={"type": "task"}, limit=max_results
                )

                # Fetch full task details and highlight matches
                enriched_results = []
                for result in results:
                    task_id = result["id"]
                    task = self.get_task(task_id)
                    if task:
                        enriched_results.append({
                            "task": task.to_dict(),
                            "score": result["score"],
                            "snippet": self._generate_snippet(task.description, query)
                        })
                return enriched_results
            except Exception as e:
                print(f"Error in semantic search: {e}")

        # Fall back to simple text search
        return self._simple_text_search(query, max_results)

    def _simple_text_search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        query = query.lower()
        results = []

        for task in self.get_all_tasks():
            score = 0
            if query in task.title.lower():
                score += 3
            if query in task.description.lower():
                score += 2
            if any(query in tag.lower() for tag in task.tags):
                score += 1

            if score > 0:
                results.append({
                    "task": task.to_dict(),
                    "score": score,
                    "snippet": self._generate_snippet(task.description, query)
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
        recurring_tasks = self.get_recurring_tasks()
        new_tasks = []

        for task in recurring_tasks:
            if task.is_recurring and task.recurrence_enabled:
                # Check if it's time to create a new instance
                if task.recurrence_next_run:
                    next_run = datetime.fromisoformat(
                        task.recurrence_next_run.replace("Z", "+00:00"))
                    if next_run <= datetime.now():
                        # Create a new task instance
                        new_task_data = {
                            "title": f"{task.title} ({datetime.now().strftime('%Y-%m-%d')})",
                            "description": task.description,
                            "status": Task.STATUS_PENDING,
                            "priority": task.priority,
                            "tags": task.tags + ["generated_from_recurring"],
                            "project": task.project,
                            "due_date": (datetime.now() + timedelta(days=1)).isoformat(),
                            "calendar_sync": task.calendar_sync,
                            "calendar_provider": task.calendar_provider
                        }

                        # Add the new task
                        new_task_id = self.add_task(new_task_data)
                        new_task = self.get_task(new_task_id)
                        if new_task:
                            new_tasks.append(new_task)

                        # Update the recurring task's next run date
                        task.recurrence_next_run = task.calculate_next_recurrence()
                        self.update_task(
                            task.id, {"recurrence_next_run": task.recurrence_next_run})

        return new_tasks
