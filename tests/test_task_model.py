"""Tests covering the task domain model behaviour."""
from __future__ import annotations

from datetime import datetime, timedelta

from graph_space_v2.core.models.task import Task


def test_task_serialization_includes_domain_fields() -> None:
    """Task.to_dict should include both base and domain-specific attributes."""
    task = Task(
        title="Draft proposal",
        description="Prepare slide deck",
        status=Task.STATUS_IN_PROGRESS,
        due_date=datetime.now().isoformat(),
        priority=Task.PRIORITY_HIGH,
        tags=["planning"],
        project="Q4",
        is_recurring=True,
        recurrence_frequency=Task.FREQUENCY_WEEKLY,
        calendar_sync=True,
        calendar_provider="google",
    )

    serialized = task.to_dict()

    assert serialized["title"] == "Draft proposal"
    assert serialized["status"] == Task.STATUS_IN_PROGRESS
    assert serialized["project"] == "Q4"
    assert serialized["calendar_sync"] is True
    assert serialized["calendar_provider"] == "google"
    assert serialized["is_recurring"] is True


def test_task_mark_completed_updates_recurrence_schedule() -> None:
    """Completing a recurring task should advance its next run and reset status."""
    due = datetime.now() - timedelta(days=1)
    task = Task(
        title="Daily report",
        description="Send the daily metrics",
        due_date=due.isoformat(),
        is_recurring=True,
        recurrence_frequency=Task.FREQUENCY_DAILY,
    )
    previous_next_run = task.recurrence_next_run

    task.mark_completed()

    assert task.status == Task.STATUS_PENDING  # reset for the next occurrence
    assert task.recurrence_next_run is not None
    assert task.recurrence_next_run != previous_next_run
    assert datetime.fromisoformat(task.recurrence_next_run) > due


def test_task_update_applies_changes_and_refreshes_timestamp() -> None:
    """Updating a task should mutate relevant fields and bump updated_at."""
    task = Task(title="Initial")
    original_updated_at = task.updated_at

    task.update({
        "title": "Updated",
        "description": "New description",
        "status": Task.STATUS_COMPLETED,
        "tags": ["done"],
        "project": "Revamp",
        "calendar_sync": True,
    })

    assert task.title == "Updated"
    assert task.description == "New description"
    assert task.status == Task.STATUS_COMPLETED
    assert task.tags == ["done"]
    assert task.project == "Revamp"
    assert task.calendar_sync is True
    assert task.updated_at != original_updated_at
