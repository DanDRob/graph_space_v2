"""Task service behaviour under various workflows."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

import pytest

from graph_space_v2.core.models.task import Task
from graph_space_v2.core.services.task_service import TaskService

from tests.conftest import DummyEmbeddingService, DummyLLMService


@pytest.fixture()
def task_service(knowledge_graph, dummy_embedding_service, dummy_llm_service):
    """Create a TaskService wired to the in-memory stubs."""
    return TaskService(knowledge_graph, dummy_embedding_service, dummy_llm_service)


def test_add_task_uses_llm_and_embeddings(task_service: TaskService, knowledge_graph, dummy_embedding_service: DummyEmbeddingService, dummy_llm_service: DummyLLMService) -> None:
    """Tasks added via dictionaries should be enriched by the LLM and embedded."""
    task_id = task_service.add_task({
        "description": "Prepare onboarding email",
        "tags": [],
    })

    stored = knowledge_graph.get_task(task_id)
    assert stored["title"].startswith("Title for")
    assert dummy_embedding_service.stored_embeddings
    assert dummy_llm_service.generated_titles == ["Prepare onboarding email"]


def test_get_all_tasks_returns_models(task_service: TaskService) -> None:
    """Fetching all tasks should yield Task instances."""
    task_service.add_task({"title": "First", "description": ""})
    task_service.add_task(Task(title="Second", description=""))

    tasks = task_service.get_all_tasks()
    assert all(isinstance(task, Task) for task in tasks)


def test_update_task_refreshes_timestamp_and_embeddings(task_service: TaskService, knowledge_graph, dummy_embedding_service: DummyEmbeddingService) -> None:
    """Updating a task should persist changes and refresh embeddings when needed."""
    task_id = task_service.add_task({"title": "Initial", "description": "Alpha"})
    original_updated_at = knowledge_graph.get_task(task_id)["updated_at"]

    task_service.update_task(task_id, {"description": "Updated description"})

    stored = knowledge_graph.get_task(task_id)
    assert stored["description"] == "Updated description"
    assert stored["updated_at"] != original_updated_at
    assert dummy_embedding_service.updated_embeddings[task_id]["embedding"].endswith("Updated description")


def test_mark_task_completed_and_in_progress(task_service: TaskService, knowledge_graph) -> None:
    """Completion and status transitions should sync with the graph."""
    task_id = task_service.add_task({"title": "Task", "description": ""})

    completed = task_service.mark_task_completed(task_id)
    assert completed is not None
    assert knowledge_graph.get_task(task_id)["status"] == Task.STATUS_COMPLETED

    restarted = task_service.mark_task_in_progress(task_id)
    assert restarted is not None
    assert knowledge_graph.get_task(task_id)["status"] == Task.STATUS_IN_PROGRESS


def test_task_filters_and_queries(task_service: TaskService) -> None:
    """Filtering helpers should return the expected subsets."""
    task_service.add_task({
        "title": "Pending",
        "description": "",
        "status": Task.STATUS_PENDING,
        "project": "Alpha",
        "tags": ["team"],
    })
    in_progress_id = task_service.add_task({
        "title": "Active",
        "description": "",
        "status": Task.STATUS_IN_PROGRESS,
        "priority": Task.PRIORITY_HIGH,
        "due_date": (datetime.now() + timedelta(days=1)).isoformat(),
        "tags": ["team"],
        "project": "Alpha",
    })
    overdue_id = task_service.add_task({
        "title": "Overdue",
        "description": "",
        "status": Task.STATUS_PENDING,
        "due_date": (datetime.now() - timedelta(days=2)).isoformat(),
        "tags": ["urgent"],
        "project": "Beta",
    })

    assert {task.id for task in task_service.get_tasks_by_status(Task.STATUS_IN_PROGRESS)} == {in_progress_id}
    assert {task.id for task in task_service.get_tasks_by_project("Alpha")} >= {in_progress_id}
    assert {task.id for task in task_service.get_tasks_by_tag("team")}
    assert {task.id for task in task_service.get_overdue_tasks()} == {overdue_id}
    due_soon_ids = {task.id for task in task_service.get_tasks_due_soon(2)}
    assert overdue_id not in due_soon_ids
    assert in_progress_id in due_soon_ids


def test_search_tasks_semantic_and_fallback(task_service: TaskService, dummy_embedding_service: DummyEmbeddingService) -> None:
    """Semantic search should use embeddings when available and fall back otherwise."""
    first_id = task_service.add_task({"title": "Documentation", "description": "Write API docs"})
    task_service.add_task({"title": "Review", "description": "Review PR"})

    dummy_embedding_service.semantic_matches = [
        {"id": first_id, "score": 0.9, "snippet": "", "metadata": {"type": "task"}},
    ]
    semantic_results = task_service.search_tasks("docs")
    assert semantic_results[0]["task"]["id"] == first_id

    # Disable embeddings to trigger text search
    plain_service = TaskService(task_service.knowledge_graph, None, None)
    plain_results = plain_service.search_tasks("review")
    assert plain_results[0]["task"]["title"] == "Review"


def test_process_recurring_tasks_generates_instances(task_service: TaskService, knowledge_graph) -> None:
    """Recurring tasks should spawn new tasks when the next run is due."""
    recurring = Task(
        title="Daily standup",
        description="Post standup notes",
        is_recurring=True,
        recurrence_frequency=Task.FREQUENCY_DAILY,
        recurrence_next_run=(datetime.now() - timedelta(minutes=5)).isoformat(),
    )
    knowledge_graph.add_task(recurring.to_dict())

    new_tasks = task_service.process_recurring_tasks()
    assert new_tasks
    generated_tags: List[str] = new_tasks[0].tags
    assert "generated_from_recurring" in generated_tags

    updated_recurring = task_service.get_task(recurring.id)
    assert updated_recurring.recurrence_next_run != recurring.recurrence_next_run


def test_delete_task_removes_embeddings(task_service: TaskService, dummy_embedding_service: DummyEmbeddingService) -> None:
    """Deleting a task should also clean up associated embeddings."""
    task_id = task_service.add_task({"title": "Cleanup", "description": ""})
    assert task_service.delete_task(task_id) is True
    assert task_id in dummy_embedding_service.deleted_embeddings
