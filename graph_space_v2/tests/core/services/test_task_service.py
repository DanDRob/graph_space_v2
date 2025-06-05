import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
import uuid

from graph_space_v2.core.services.task_service import TaskService
from graph_space_v2.core.models.task import Task
from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph
from graph_space_v2.ai.embedding.embedding_service import EmbeddingService
from graph_space_v2.ai.llm.llm_service import LLMService
from graph_space_v2.utils.errors.exceptions import TaskServiceError, EntityNotFoundError, EmbeddingServiceError, LLMServiceError

class TestTaskService(unittest.TestCase):

    def setUp(self):
        self.mock_kg = MagicMock(spec=KnowledgeGraph)
        self.mock_embedding_service = MagicMock(spec=EmbeddingService)
        self.mock_llm_service = MagicMock(spec=LLMService)

        self.mock_llm_service.enabled = True # Default to enabled

        self.task_service = TaskService(
            knowledge_graph=self.mock_kg,
            embedding_service=self.mock_embedding_service,
            llm_service=self.mock_llm_service
        )

        self.mock_kg.reset_mock()
        self.mock_embedding_service.reset_mock()
        self.mock_llm_service.reset_mock()
        self.mock_llm_service.enabled = True


    def _get_sample_task_data_dict(self, id_val=None, description="Test description", title="Test Title", tags=None, status="pending", due_date_offset_days=1, is_recurring=False, recurrence_next_run=None):
        if tags is None:
            tags = ["test_task_tag"]
        now = datetime.now()
        return {
            "id": id_val or str(uuid.uuid4()),
            "title": title,
            "description": description,
            "tags": tags,
            "status": status,
            "priority": "medium",
            "due_date": (now + timedelta(days=due_date_offset_days)).isoformat() if due_date_offset_days is not None else None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "project": "TestProject",
            "is_recurring": is_recurring,
            "recurrence_rule": "RRULE:FREQ=DAILY;INTERVAL=1" if is_recurring else None,
            "recurrence_next_run": recurrence_next_run.isoformat() if recurrence_next_run else None,
            "recurrence_enabled": is_recurring,
        }

    def test_add_task_simple_success(self):
        task_dict = self._get_sample_task_data_dict()
        task_id = task_dict["id"]
        self.mock_kg.add_task.return_value = task_id

        self.task_service.llm_service = None
        self.task_service.embedding_service = None

        result_id = self.task_service.add_task(task_dict)

        self.assertEqual(result_id, task_id)
        self.mock_kg.add_task.assert_called_once()
        called_task_data = self.mock_kg.add_task.call_args[0][0]
        self.assertEqual(called_task_data["id"], task_id)

    def test_add_task_with_llm_and_embedding(self):
        task_dict_initial = {"description": "A complex task about system design.", "id": str(uuid.uuid4())}
        task_id = task_dict_initial["id"]

        self.mock_llm_service.generate_title.return_value = "System Design Task"
        self.mock_llm_service.extract_tags.return_value = ["system design", "architecture"]
        self.mock_embedding_service.embed_text.return_value = [0.3, 0.2, 0.1]
        self.mock_kg.add_task.return_value = task_id

        result_id = self.task_service.add_task(task_dict_initial)

        self.assertEqual(result_id, task_id)
        self.mock_llm_service.generate_title.assert_called_once_with("A complex task about system design.")
        self.mock_llm_service.extract_tags.assert_called_once_with("A complex task about system design.")
        self.mock_embedding_service.embed_text.assert_called_once_with("A complex task about system design.")
        self.mock_embedding_service.store_embedding.assert_called_once()
        self.mock_kg.add_task.assert_called_once()

        called_task_data = self.mock_kg.add_task.call_args[0][0]
        self.assertEqual(called_task_data["title"], "System Design Task")
        self.assertEqual(called_task_data["tags"], ["system design", "architecture"])

    def test_add_task_kg_failure(self):
        task_dict = self._get_sample_task_data_dict()
        self.mock_kg.add_task.side_effect = Exception("KG Save Error")

        with self.assertRaisesRegex(TaskServiceError, "Error adding task"):
            self.task_service.add_task(task_dict)

    def test_get_task_found(self):
        task_id = "task123"
        task_data_dict = self._get_sample_task_data_dict(id_val=task_id)
        self.mock_kg.get_task.return_value = task_data_dict

        task_obj = self.task_service.get_task(task_id)

        self.assertIsNotNone(task_obj)
        self.assertIsInstance(task_obj, Task)
        self.assertEqual(task_obj.id, task_id)
        self.assertEqual(task_obj.title, task_data_dict["title"])
        self.mock_kg.get_task.assert_called_once_with(task_id)

    def test_get_task_not_found(self):
        task_id = "task123"
        self.mock_kg.get_task.return_value = None

        with self.assertRaisesRegex(TaskServiceError, f"Task with ID {task_id} not found."):
            self.task_service.get_task(task_id)

    def test_get_all_tasks(self):
        task_data_list = [self._get_sample_task_data_dict("1"), self._get_sample_task_data_dict("2")]
        # get_all_tasks expects kg.data.get("tasks") to return list of dicts
        self.mock_kg.data = {"tasks": task_data_list}

        tasks = self.task_service.get_all_tasks() # This returns list of Dicts

        self.assertEqual(len(tasks), 2)
        self.assertEqual(tasks[0]["id"], "1")
        self.assertIsInstance(tasks[0], dict)


    def test_update_task_success(self):
        task_id = "task_update1"
        original_task_data = self._get_sample_task_data_dict(id_val=task_id, description="Original desc")
        update_payload = {"title": "Updated Task Title", "description": "Updated desc."}

        self.mock_kg.update_task.return_value = True
        updated_data_for_get = original_task_data.copy()
        updated_data_for_get.update(update_payload)
        # updated_at will be set by the service method
        self.mock_kg.get_task.return_value = updated_data_for_get

        self.mock_embedding_service.embed_text.return_value = [0.5,0.5,0.5]
        self.mock_embedding_service.update_embedding.return_value = True

        updated_task = self.task_service.update_task(task_id, update_payload)

        self.mock_kg.update_task.assert_called_once()
        final_payload_to_kg = self.mock_kg.update_task.call_args[0][1]
        self.assertIn("updated_at", final_payload_to_kg)
        self.assertEqual(final_payload_to_kg["title"], "Updated Task Title")

        self.mock_embedding_service.embed_text.assert_called_once_with("Updated desc.")
        self.mock_embedding_service.update_embedding.assert_called_once_with(task_id, [0.5,0.5,0.5])

        self.assertIsNotNone(updated_task)
        self.assertEqual(updated_task.title, "Updated Task Title")

    def test_update_task_llm_generation(self):
        task_id = "task_llm_upd"
        update_payload = {"description": "New important task description.", "title": "", "tags": []}

        self.mock_kg.update_task.return_value = True
        self.mock_llm_service.generate_title.return_value = "Important Task Title"
        self.mock_llm_service.extract_tags.return_value = ["important", "new"]

        # Mock for the get_task call at the end of update_task
        final_task_data = self._get_sample_task_data_dict(id_val=task_id)
        final_task_data.update(update_payload)
        final_task_data["title"] = "Important Task Title"
        final_task_data["tags"] = ["important", "new"]
        self.mock_kg.get_task.return_value = final_task_data

        self.task_service.update_task(task_id, update_payload)

        self.mock_llm_service.generate_title.assert_called_once_with("New important task description.")
        self.mock_llm_service.extract_tags.assert_called_once_with("New important task description.")

        called_kg_payload = self.mock_kg.update_task.call_args[0][1]
        self.assertEqual(called_kg_payload["title"], "Important Task Title")
        self.assertEqual(called_kg_payload["tags"], ["important", "new"])

    def test_delete_task_success(self):
        task_id = "task_del1"
        self.mock_kg.delete_task.return_value = True
        self.mock_embedding_service.delete_embedding.return_value = True

        success = self.task_service.delete_task(task_id)

        self.assertTrue(success)
        self.mock_kg.delete_task.assert_called_once_with(task_id)
        self.mock_embedding_service.delete_embedding.assert_called_once_with(task_id)

    def test_get_tasks_by_status(self):
        task1 = self._get_sample_task_data_dict("t1", status="pending")
        task2 = self._get_sample_task_data_dict("t2", status="completed")
        task3 = self._get_sample_task_data_dict("t3", status="pending")
        self.mock_kg.data = {"tasks": [task1, task2, task3]}

        pending_tasks = self.task_service.get_tasks_by_status("pending")
        self.assertEqual(len(pending_tasks), 2)
        self.assertTrue(all(isinstance(t, Task) for t in pending_tasks))
        self.assertTrue(all(t.status == "pending" for t in pending_tasks))

    def test_get_overdue_tasks(self):
        now = datetime.now()
        task1 = self._get_sample_task_data_dict("t_overdue1", status="pending", due_date_offset_days=-1) # Overdue
        task2 = self._get_sample_task_data_dict("t_notoverdue1", status="pending", due_date_offset_days=1) # Not overdue
        task3 = self._get_sample_task_data_dict("t_completed_overdue", status="completed", due_date_offset_days=-2) # Completed
        self.mock_kg.data = {"tasks": [task1, task2, task3]}

        overdue = self.task_service.get_overdue_tasks()
        self.assertEqual(len(overdue), 1)
        self.assertEqual(overdue[0].id, "t_overdue1")

    def test_mark_task_completed(self):
        task_id = "task_mark_comp"
        original_task_dict = self._get_sample_task_data_dict(id_val=task_id, status="pending")

        # get_task is called first
        self.mock_kg.get_task.return_value = original_task_dict
        # update_task is called by mark_task_completed, which itself calls get_task again
        # We need to ensure the second get_task call (inside update_task) gets the updated data

        updated_task_data_for_kg = original_task_dict.copy()
        updated_task_data_for_kg["status"] = Task.STATUS_COMPLETED
        # updated_at will be handled by update_task itself.

        self.mock_kg.update_task.return_value = True
        # This is the get_task call inside update_task, AFTER the update has happened.
        # So it should return the data with status "completed".
        # We need a side effect if get_task is called multiple times with same ID but different expected states

        def get_task_side_effect(tid):
            if tid == task_id:
                # If update_task has been called, it means status should be completed for this get_task call
                if self.mock_kg.update_task.called:
                    temp_data = original_task_dict.copy()
                    temp_data["status"] = Task.STATUS_COMPLETED
                    return temp_data
                return original_task_dict # First call to get_task
            return None

        self.mock_kg.get_task.side_effect = get_task_side_effect

        completed_task = self.task_service.mark_task_completed(task_id)

        self.assertIsNotNone(completed_task)
        self.assertEqual(completed_task.status, Task.STATUS_COMPLETED)
        self.mock_kg.update_task.assert_called_once()
        # Check that the data passed to update_task had the completed status
        payload_to_kg = self.mock_kg.update_task.call_args[0][1]
        self.assertEqual(payload_to_kg["status"], Task.STATUS_COMPLETED)

    # test_search_tasks and test_process_recurring_tasks are more complex and would follow similar patterns
    # of mocking dependencies and asserting interactions or final results.
    # For brevity in this example, they are sketched out.

    @patch.object(TaskService, '_simple_text_search')
    def test_search_tasks_semantic(self, mock_simple_search):
        query = "find my task"
        mock_embedding = [0.1,0.2,0.3]
        self.mock_embedding_service.embed_text.return_value = mock_embedding
        search_matches = [{"id": "task1", "score": 0.9, "description": "desc1"}] # Corrected structure
        self.mock_embedding_service.search.return_value = {"matches": search_matches}

        # Mocking get_task called inside search_tasks
        self.mock_kg.get_task.return_value = self._get_sample_task_data_dict(id_val="task1", description="desc1")

        results = self.task_service.search_tasks(query)

        self.mock_embedding_service.embed_text.assert_called_once_with(query)
        self.mock_embedding_service.search.assert_called_once_with(mock_embedding, filter_by={"type": "task"}, limit=5)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["task"]["id"], "task1")
        mock_simple_search.assert_not_called()

    def test_search_tasks_fallback(self):
        query = "find this"
        self.task_service.embedding_service = None # Disable embedding service

        task_data1 = self._get_sample_task_data_dict("task_simple1", description="Contains find this query")
        self.mock_kg.data = {"tasks": [task_data1]} # Mock for get_all_tasks used by _simple_text_search

        results = self.task_service.search_tasks(query)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["task"]["id"], "task_simple1")

    def test_process_recurring_tasks(self):
        now = datetime.now()
        # Task that should recur now
        task1_data = self._get_sample_task_data_dict(
            "task_recur1",
            is_recurring=True,
            recurrence_next_run=(now - timedelta(days=1)) # Due yesterday
        )
        # Task that should not recur now
        task2_data = self._get_sample_task_data_dict(
            "task_recur2",
            is_recurring=True,
            recurrence_next_run=(now + timedelta(days=5)) # Due in 5 days
        )

        # Mock get_all_tasks (which get_recurring_tasks uses)
        self.mock_kg.data = {"tasks": [task1_data, task2_data]}

        # Mock add_task for the new instance
        new_task_id = "new_recurring_instance"
        self.mock_kg.add_task.return_value = new_task_id

        # Mock get_task for retrieving the newly added task and for updating original
        # This needs careful side_effect mocking if IDs are dynamic
        def get_task_side_effect(task_id_param):
            if task_id_param == new_task_id:
                return self._get_sample_task_data_dict(id_val=new_task_id, title=f"{task1_data['title']} ({now.strftime('%Y-%m-%d')})")
            elif task_id_param == task1_data["id"]:
                # Return original for first get_task, then updated for the get_task inside update_task
                if self.mock_kg.update_task.call_count > 0 and \
                   self.mock_kg.update_task.call_args[0][0] == task1_data["id"]: # if update_task was called for task1
                    updated_t1_data = task1_data.copy()
                    # This part is tricky as calculate_next_recurrence is on the model
                    # For simplicity, assume update_task is called with some date
                    return updated_t1_data
                return task1_data
            return None
        self.mock_kg.get_task.side_effect = get_task_side_effect
        self.mock_kg.update_task.return_value = True


        new_tasks = self.task_service.process_recurring_tasks()

        self.assertEqual(len(new_tasks), 1)
        self.assertEqual(new_tasks[0].id, new_task_id)
        self.mock_kg.add_task.assert_called_once() # One new task created

        # Check that the original recurring task (task1_data) had its next_run_date updated
        # This means update_task should have been called for task1_data["id"]
        update_calls = [call for call in self.mock_kg.update_task.call_args_list if call[0][0] == task1_data["id"]]
        self.assertEqual(len(update_calls), 1)
        self.assertIn("recurrence_next_run", update_calls[0][0][1])


if __name__ == '__main__':
    unittest.main()
