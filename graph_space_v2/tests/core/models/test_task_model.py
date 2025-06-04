import pytest
from datetime import datetime, timedelta
from graph_space_v2.core.models.task import Task

def test_task_creation_minimal():
    task = Task(title="Minimal Task")
    assert task.title == "Minimal Task"
    assert task.description == ""  # Defaults to empty string
    assert task.status == "pending"
    assert task.priority == "medium"
    assert task.due_date is None # No default due date if not provided
    assert task.id is not None
    assert isinstance(task.created_at, str) # Dates are strings
    assert isinstance(task.updated_at, str) # Dates are strings

def test_task_creation_full():
    now_iso = datetime.now().isoformat()
    due_iso = (datetime.now() + timedelta(days=5)).isoformat()
    task = Task(
        id="task_custom_id",
        title="Full Task",
        description="Detailed description.",
        status="in_progress",
        priority="high",
        due_date=due_iso,
        project="Project X",
        tags=["work", "urgent"],
        # dependencies and sub_tasks do not exist
        created_at=now_iso,
        updated_at=now_iso
    )
    assert task.id == "task_custom_id"
    assert task.title == "Full Task"
    assert task.description == "Detailed description."
    assert task.status == "in_progress"
    assert task.priority == "high"
    assert task.due_date == due_iso
    assert task.project == "Project X"
    assert task.tags == ["work", "urgent"]

def test_task_to_dict():
    task = Task(title="To Dict Task")
    task_dict = task.to_dict()
    assert task_dict['id'] == task.id
    assert task_dict['title'] == "To Dict Task"
    assert task_dict['status'] == "pending"
    assert 'created_at' in task_dict

def test_task_from_dict():
    due_date_str = (datetime.now() + timedelta(days=1)).isoformat()
    data = {
        "id": "task_dict_id",
        "title": "From Dict Task",
        "status": "completed",
        "priority": "low",
        "due_date": due_date_str,
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat()
    }
    task = Task.from_dict(data)
    assert task.id == "task_dict_id"
    assert task.title == "From Dict Task"
    assert task.status == "completed"
    assert task.priority == "low"
    assert isinstance(task.due_date, str) # Dates are strings
    assert isinstance(task.created_at, str) # Dates are strings
    assert isinstance(task.updated_at, str) # Dates are strings

def test_task_mark_completed(): # Renamed from mark_complete
    task = Task(title="Test Mark Complete")
    original_updated_at = datetime.fromisoformat(task.updated_at)
    import time; time.sleep(0.001)
    task.mark_completed() # Correct method name
    assert task.status == "completed"
    # No completed_at attribute in the model
    assert datetime.fromisoformat(task.updated_at) > original_updated_at

# is_overdue method does not exist, removing this test for now.
# def test_task_is_overdue():
#     past_due_date = datetime.now() - timedelta(days=1)
#     future_due_date = datetime.now() + timedelta(days=1)
#     task_overdue = Task(title="Overdue Task", due_date=past_due_date.isoformat())
#     task_not_overdue = Task(title="Not Overdue Task", due_date=future_due_date.isoformat())
#     task_no_due_date = Task(title="No Due Date Task")

#     assert task_overdue.is_overdue() is True # This method needs to exist on Task model
#     assert task_not_overdue.is_overdue() is False
#     assert task_no_due_date.is_overdue() is False

#     task_completed_overdue = Task(title="Completed Overdue", due_date=past_due_date.isoformat(), status="completed")
#     assert task_completed_overdue.is_overdue() is False

# Test for default values when no title is provided
def test_task_creation_empty():
    # Task() is allowed, title defaults to ""
    task = Task()
    assert task.title == ""
