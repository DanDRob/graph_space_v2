import pytest
from unittest.mock import MagicMock
from graph_space_v2.core.services.task_service import TaskService
from graph_space_v2.core.models.task import Task
from datetime import datetime, timedelta

@pytest.fixture
def mock_kg():
    return MagicMock()

@pytest.fixture
def mock_embedding_service():
    return MagicMock()

@pytest.fixture
def mock_llm_service():
    return MagicMock()

@pytest.fixture
def task_service(mock_kg, mock_embedding_service, mock_llm_service):
    return TaskService(
        knowledge_graph=mock_kg,
        embedding_service=mock_embedding_service,
        llm_service=mock_llm_service
    )

def test_add_task(task_service, mock_kg): # Renamed from test_create_task
    task_data_input = {"title": "Test Task", "description": "A test task."}

    expected_task_id = "some_uuid_for_task"
    mock_kg.add_task.return_value = expected_task_id

    created_task_id = task_service.add_task(task_data_input)

    assert created_task_id == expected_task_id

    mock_kg.add_task.assert_called_once()
    call_args = mock_kg.add_task.call_args[0][0]
    assert call_args['title'] == "Test Task"
    assert 'id' in call_args
    assert 'created_at' in call_args
    assert 'updated_at' in call_args


def test_get_task(task_service, mock_kg):
    task_id = "test_task_id"
    task_data_from_kg = {
        "id": task_id, "title": "Fetched Task", "description": "Desc",
        "status": "pending", "priority": "medium", "due_date": None,
        "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat(),
        "tags": [], "project": ""
    }
    mock_kg.get_task.return_value = task_data_from_kg

    task_obj = task_service.get_task(task_id)

    assert task_obj is not None
    assert isinstance(task_obj, Task)
    assert task_obj.id == task_id
    assert task_obj.title == "Fetched Task"
    mock_kg.get_task.assert_called_with(task_id)

def test_get_all_tasks(task_service, mock_kg):
    tasks_data_from_kg = [
        {"id": "task1", "title": "Task 1", "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat(), "status": "pending", "priority": "medium", "tags": [], "project": ""},
        {"id": "task2", "title": "Task 2", "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat(), "status": "in_progress", "priority": "high", "tags": [], "project": ""}
    ]
    mock_kg.data = {"tasks": tasks_data_from_kg}

    tasks_list_of_dicts = task_service.get_all_tasks()

    assert len(tasks_list_of_dicts) == 2
    assert isinstance(tasks_list_of_dicts[0], dict)
    assert tasks_list_of_dicts[0]['title'] == "Task 1"
    assert tasks_list_of_dicts[1]['status'] == "in_progress"

def test_update_task(task_service, mock_kg):
    task_id = "task_to_update"
    update_data_payload = {"title": "Updated Task Title", "status": "completed"}

    original_task_data_from_kg = {
        "id": task_id, "title": "Original Task", "status": "pending", "priority": "medium",
        "created_at": datetime.now().isoformat(),
        "updated_at": (datetime.now() - timedelta(seconds=10)).isoformat(),
        "tags": [], "project": ""
    }

    final_task_data_in_kg = {
        "id": task_id, "title": "Updated Task Title", "status": "completed", "priority": "medium",
        "created_at": original_task_data_from_kg['created_at'],
        "updated_at": datetime.now().isoformat(),
        "tags": [], "project": ""
    }

    mock_kg.update_task.return_value = True
    mock_kg.get_task.return_value = final_task_data_in_kg # For the get_task call in service's update_task

    updated_task_obj = task_service.update_task(task_id, update_data_payload)

    assert updated_task_obj is not None
    assert isinstance(updated_task_obj, Task)
    assert updated_task_obj.title == "Updated Task Title"
    assert updated_task_obj.status == "completed"
    assert updated_task_obj.updated_at == final_task_data_in_kg['updated_at']

    mock_kg.update_task.assert_called_once()
    args_to_kg_update_task = mock_kg.update_task.call_args[0]
    assert args_to_kg_update_task[0] == task_id
    payload_to_kg = args_to_kg_update_task[1]
    assert payload_to_kg['title'] == "Updated Task Title"
    assert payload_to_kg['status'] == "completed"
    assert 'updated_at' in payload_to_kg
    assert 'id' not in payload_to_kg

    mock_kg.get_task.assert_called_with(task_id)


def test_delete_task(task_service, mock_kg):
    task_id = "task_to_delete"
    mock_kg.delete_task.return_value = True

    result = task_service.delete_task(task_id)

    assert result is True
    mock_kg.delete_task.assert_called_with(task_id)

def test_mark_task_completed(task_service, mock_kg):
    task_id = "task_to_complete"
    original_task_data = {
        "id": task_id, "title": "To Complete", "status": "pending", "priority": "medium",
        "created_at": datetime.now().isoformat(), "updated_at": datetime.now().isoformat(),
        "tags": [], "project": ""
    }
    # Service calls get_task once, then update_task. It returns the modified local Task object.
    mock_kg.get_task.return_value = original_task_data
    mock_kg.update_task.return_value = True

    completed_task_obj = task_service.mark_task_completed(task_id)

    assert isinstance(completed_task_obj, Task)
    assert completed_task_obj.status == Task.STATUS_COMPLETED

    mock_kg.get_task.assert_called_once_with(task_id) # Called once by service to get the task
    mock_kg.update_task.assert_called_once()
    updated_data_arg = mock_kg.update_task.call_args[0][1]
    assert updated_data_arg['status'] == Task.STATUS_COMPLETED
    assert 'updated_at' in updated_data_arg
    assert updated_data_arg['id'] == task_id
