import unittest
import os
import tempfile
import json
import networkx as nx
from datetime import datetime

from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph
from graph_space_v2.core.models.note import Note
from graph_space_v2.core.models.task import Task
from graph_space_v2.core.models.contact import Contact
# Assuming Document might be a dict or a simple class not needing specific import for basic tests
from graph_space_v2.utils.errors.exceptions import EntityNotFoundError, KnowledgeGraphError

class TestKnowledgeGraph(unittest.TestCase):

    def setUp(self):
        """Set up a temporary data file for each test."""
        # Create a temporary file and get its path
        self.temp_file = tempfile.NamedTemporaryFile(delete=False, mode='w+', encoding='utf-8')
        self.temp_file_path = self.temp_file.name
        self.temp_file.close() # Close it so KnowledgeGraph can open/manage it

        # Initialize KnowledgeGraph with the temporary file path
        self.kg = KnowledgeGraph(data_path=self.temp_file_path)
        # Ensure a clean slate by explicitly creating an empty graph structure if _load_graph_data doesn't.
        # Based on current KG, _load_graph_data will create and save an empty graph if file is new/empty.

    def tearDown(self):
        """Clean up the temporary data file after each test."""
        try:
            if os.path.exists(self.temp_file_path):
                os.remove(self.temp_file_path)
        except Exception as e:
            print(f"Error removing temporary file {self.temp_file_path}: {e}")

    def _create_sample_note_data(self, id_suffix="1", title="Test Note", content="This is a test note.", tags=None):
        if tags is None:
            tags = ["test", "sample"]
        return {
            "id": f"note_{id_suffix}",
            "title": title,
            "content": content,
            "tags": tags,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

    def _create_sample_task_data(self, id_suffix="1", title="Test Task", description="This is a test task.", tags=None):
        if tags is None:
            tags = ["work", "important"]
        return {
            "id": f"task_{id_suffix}",
            "title": title,
            "description": description,
            "status": "pending",
            "tags": tags,
            "due_date": (datetime.now() + timedelta(days=1)).isoformat(),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

    def _create_sample_contact_data(self, id_suffix="1", name="John Doe", email="john.doe@example.com", tags=None):
        if tags is None:
            tags = ["friend"]
        return {
            "id": f"contact_{id_suffix}",
            "name": name,
            "email": email,
            "phone": "123-456-7890",
            "organization": "Example Corp",
            "tags": tags,
            "created_at": datetime.now().isoformat()
        }

    def _create_sample_document_data(self, id_suffix="1", title="Test Document", content="Document content.", tags=None):
        if tags is None:
            tags = ["research", "paper"]
        return {
            "id": f"doc_{id_suffix}", # Assuming KG prefixes this with "document_" internally for node ID
            "title": title,
            "content": content, # Or path, depending on implementation
            "tags": tags,
            "created_at": datetime.now().isoformat(),
            "processed_at": datetime.now().isoformat()
        }

    # --- Note Tests ---
    def test_add_and_get_note(self):
        note_data = self._create_sample_note_data(id_suffix="addget")
        added_note_id = self.kg.add_note(note_data)
        self.assertEqual(added_note_id, note_data["id"])

        retrieved_note_data = self.kg.get_note(note_data["id"])
        self.assertIsNotNone(retrieved_note_data)
        self.assertEqual(retrieved_note_data["title"], note_data["title"])

        # Check graph directly
        graph_node_id = f"note_{note_data['id']}"
        self.assertTrue(self.kg.graph.has_node(graph_node_id))
        self.assertEqual(self.kg.graph.nodes[graph_node_id]['data']['title'], note_data['title'])

        self.assertIsNone(self.kg.get_note("non_existent_note"))

    def test_update_note(self):
        note_data = self._create_sample_note_data(id_suffix="update")
        self.kg.add_note(note_data)

        update_payload = {"title": "Updated Title", "content": "Updated content."}
        success = self.kg.update_note(note_data["id"], update_payload)
        self.assertTrue(success)

        updated_note = self.kg.get_note(note_data["id"])
        self.assertIsNotNone(updated_note)
        self.assertEqual(updated_note["title"], "Updated Title")
        self.assertEqual(updated_note["content"], "Updated content.")

        # Check graph directly
        graph_node_id = f"note_{note_data['id']}"
        self.assertEqual(self.kg.graph.nodes[graph_node_id]['data']['title'], "Updated Title")

        # Test updating non-existent note
        self.assertFalse(self.kg.update_note("non_existent_note", {"title": "Ghost Title"}))

    def test_delete_note(self):
        note_data = self._create_sample_note_data(id_suffix="delete")
        self.kg.add_note(note_data)

        graph_node_id = f"note_{note_data['id']}"
        self.assertTrue(self.kg.graph.has_node(graph_node_id)) # Ensure it's there before delete

        success = self.kg.delete_note(note_data["id"])
        self.assertTrue(success)
        self.assertIsNone(self.kg.get_note(note_data["id"]))
        self.assertFalse(self.kg.graph.has_node(graph_node_id)) # Check graph directly

        # Test deleting non-existent note
        self.assertFalse(self.kg.delete_note("non_existent_note"))

    # --- Task Tests ---
    def test_add_and_get_task(self):
        task_data = self._create_sample_task_data(id_suffix="addget")
        added_task_id = self.kg.add_task(task_data)
        self.assertEqual(added_task_id, task_data["id"])

        retrieved_task_data = self.kg.get_task(task_data["id"])
        self.assertIsNotNone(retrieved_task_data)
        self.assertEqual(retrieved_task_data["title"], task_data["title"])

        graph_node_id = f"task_{task_data['id']}"
        self.assertTrue(self.kg.graph.has_node(graph_node_id))
        self.assertEqual(self.kg.graph.nodes[graph_node_id]['data']['title'], task_data['title'])

        self.assertIsNone(self.kg.get_task("non_existent_task"))

    def test_update_task(self):
        task_data = self._create_sample_task_data(id_suffix="update")
        self.kg.add_task(task_data)

        update_payload = {"title": "Updated Task Title", "status": "completed"}
        success = self.kg.update_task(task_data["id"], update_payload)
        self.assertTrue(success)

        updated_task = self.kg.get_task(task_data["id"])
        self.assertIsNotNone(updated_task)
        self.assertEqual(updated_task["title"], "Updated Task Title")
        self.assertEqual(updated_task["status"], "completed")

        self.assertFalse(self.kg.update_task("non_existent_task", {"title": "Ghost Task"}))

    def test_delete_task(self):
        task_data = self._create_sample_task_data(id_suffix="delete")
        self.kg.add_task(task_data)
        graph_node_id = f"task_{task_data['id']}"

        success = self.kg.delete_task(task_data["id"])
        self.assertTrue(success)
        self.assertIsNone(self.kg.get_task(task_data["id"]))
        self.assertFalse(self.kg.graph.has_node(graph_node_id))

        self.assertFalse(self.kg.delete_task("non_existent_task"))

    # --- Contact Tests ---
    def test_add_and_get_contact(self):
        contact_data = self._create_sample_contact_data(id_suffix="addget")
        added_contact_id = self.kg.add_contact(contact_data)
        self.assertEqual(added_contact_id, contact_data["id"])

        retrieved_contact_data = self.kg.get_contact(contact_data["id"]) # Assuming get_contact exists
        self.assertIsNotNone(retrieved_contact_data)
        self.assertEqual(retrieved_contact_data["name"], contact_data["name"])

        graph_node_id = f"contact_{contact_data['id']}"
        self.assertTrue(self.kg.graph.has_node(graph_node_id))
        self.assertEqual(self.kg.graph.nodes[graph_node_id]['data']['name'], contact_data['name'])

        self.assertIsNone(self.kg.get_contact("non_existent_contact"))

    # --- Document Tests ---
    def test_add_and_get_document(self):
        doc_data = self._create_sample_document_data(id_suffix="addget")
        added_doc_id = self.kg.add_document(doc_data)
        self.assertEqual(added_doc_id, doc_data["id"])

        retrieved_doc_data = self.kg.get_document(doc_data["id"])
        self.assertIsNotNone(retrieved_doc_data)
        self.assertEqual(retrieved_doc_data["title"], doc_data["title"])

        graph_node_id = f"document_{doc_data['id']}"
        self.assertTrue(self.kg.graph.has_node(graph_node_id))
        self.assertEqual(self.kg.graph.nodes[graph_node_id]['data']['title'], doc_data['title'])

        self.assertIsNone(self.kg.get_document("non_existent_document"))

    # --- Relationship, Search, Path, Persistence Tests ---
    def test_add_relationship(self):
        note_data = self._create_sample_note_data("rel_note")
        task_data = self._create_sample_task_data("rel_task")
        self.kg.add_note(note_data)
        self.kg.add_task(task_data)

        success = self.kg.add_relationship(
            note_data["id"], task_data["id"], "related_to", {"reason": "testing"}
        )
        self.assertTrue(success)

        note_node_id = f"note_{note_data['id']}"
        task_node_id = f"task_{task_data['id']}"
        self.assertTrue(self.kg.graph.has_edge(note_node_id, task_node_id))
        edge_data = self.kg.graph.get_edge_data(note_node_id, task_node_id)
        self.assertEqual(edge_data["relationship"], "related_to")
        self.assertEqual(edge_data["reason"], "testing")

        # Test adding relationship with non-existent entity
        self.assertFalse(self.kg.add_relationship("non_existent_id", task_data["id"], "related_to"))

    def test_get_related_entities(self):
        note1_data = self._create_sample_note_data("related1")
        note2_data = self._create_sample_note_data("related2", title="Note 2")
        task_data = self._create_sample_task_data("related_task")
        self.kg.add_note(note1_data)
        self.kg.add_note(note2_data)
        self.kg.add_task(task_data)

        self.kg.add_relationship(note1_data["id"], note2_data["id"], "mentions")
        self.kg.add_relationship(note1_data["id"], task_data["id"], "assigned_to")

        related = self.kg.get_related_entities(note1_data["id"], "note")
        self.assertEqual(len(related), 2)
        related_ids = {r["id"] for r in related}
        self.assertIn(note2_data["id"], related_ids)
        self.assertIn(task_data["id"], related_ids)

        with self.assertRaises(EntityNotFoundError):
            self.kg.get_related_entities("non_existent_id", "note")

    def test_find_path(self):
        note1 = self._create_sample_note_data("path_n1")
        note2 = self._create_sample_note_data("path_n2")
        task1 = self._create_sample_task_data("path_t1")
        self.kg.add_note(note1)
        self.kg.add_note(note2)
        self.kg.add_task(task1)

        self.kg.add_relationship(note1["id"], task1["id"], "connects_to")
        self.kg.add_relationship(task1["id"], note2["id"], "leads_to")

        path = self.kg.find_path(note1["id"], "note", note2["id"], "note")
        self.assertEqual(len(path), 3) # note1 -> task1 -> note2
        self.assertEqual(path[0]["id"], note1["id"])
        self.assertEqual(path[1]["id"], task1["id"])
        self.assertEqual(path[2]["id"], note2["id"])

        # Test no path
        note3 = self._create_sample_note_data("path_n3")
        self.kg.add_note(note3)
        no_path = self.kg.find_path(note1["id"], "note", note3["id"], "note")
        self.assertEqual(len(no_path), 0)

        with self.assertRaises(EntityNotFoundError):
            self.kg.find_path("non_existent_id", "note", note1["id"], "note")


    def test_search_by_tag(self):
        note1 = self.kg.add_note(self._create_sample_note_data("tag_n1", tags=["apple", "banana"]))
        note2 = self.kg.add_note(self._create_sample_note_data("tag_n2", tags=["banana", "cherry"]))
        task1 = self.kg.add_task(self._create_sample_task_data("tag_t1", tags=["apple", "work"]))

        banana_results = self.kg.search_by_tag("banana")
        self.assertEqual(len(banana_results), 2)
        result_ids_banana = {r["id"] for r in banana_results}
        self.assertIn("tag_n1", result_ids_banana) # Note: search_by_tag returns entity_id without prefix
        self.assertIn("tag_n2", result_ids_banana)


        apple_results = self.kg.search_by_tag("apple")
        self.assertEqual(len(apple_results), 2)
        result_ids_apple = {r["id"] for r in apple_results}
        self.assertIn("tag_n1", result_ids_apple)
        self.assertIn("tag_t1", result_ids_apple)

        non_existent_results = self.kg.search_by_tag("grape")
        self.assertEqual(len(non_existent_results), 0)

    def test_load_and_save_graph(self):
        note_data = self._create_sample_note_data("persist_note")
        task_data = self._create_sample_task_data("persist_task")
        self.kg.add_note(note_data)
        self.kg.add_task(task_data)
        self.kg.add_relationship(note_data["id"], task_data["id"], "linked")

        # Save is usually handled by each add/update/delete method due to _save_graph calls
        # Here, we can explicitly call it if needed, or rely on the incremental saves.
        # For this test, let's assume _save_graph is called by the add methods.

        # Create a new KG instance loading from the same file
        kg_loaded = KnowledgeGraph(data_path=self.temp_file_path)

        # Verify notes
        self.assertEqual(len(kg_loaded.data["notes"]), 1)
        loaded_note = kg_loaded.get_note(note_data["id"])
        self.assertIsNotNone(loaded_note)
        self.assertEqual(loaded_note["title"], note_data["title"])

        # Verify tasks
        self.assertEqual(len(kg_loaded.data["tasks"]), 1)
        loaded_task = kg_loaded.get_task(task_data["id"])
        self.assertIsNotNone(loaded_task)
        self.assertEqual(loaded_task["title"], task_data["title"])

        # Verify graph structure (nodes)
        note_node_id = f"note_{note_data['id']}"
        task_node_id = f"task_{task_data['id']}"
        self.assertTrue(kg_loaded.graph.has_node(note_node_id))
        self.assertTrue(kg_loaded.graph.has_node(task_node_id))

        # Verify graph structure (edges)
        self.assertTrue(kg_loaded.graph.has_edge(note_node_id, task_node_id))
        edge_data = kg_loaded.graph.get_edge_data(note_node_id, task_node_id)
        self.assertEqual(edge_data.get("relationship"), "linked")

    def test_update_node_generic(self):
        note_data = self._create_sample_note_data("generic_update")
        self.kg.add_note(note_data)

        updated_title = "Generic Updated Title"
        success = self.kg.update_node(note_data["id"], {"title": updated_title, "custom_field": "value"})
        self.assertTrue(success)

        retrieved_note = self.kg.get_note(note_data["id"])
        self.assertEqual(retrieved_note["title"], updated_title)
        self.assertEqual(retrieved_note["custom_field"], "value") # Assuming update_node updates self.data list correctly

        graph_node_id = f"note_{note_data['id']}"
        self.assertEqual(self.kg.graph.nodes[graph_node_id]['data']['title'], updated_title)
        self.assertEqual(self.kg.graph.nodes[graph_node_id]['data']['custom_field'], "value")
        self.assertEqual(self.kg.graph.nodes[graph_node_id]['title'], updated_title) # Check top-level attr if it's set

    def test_delete_node_generic(self):
        task_data = self._create_sample_task_data("generic_delete")
        self.kg.add_task(task_data)
        graph_node_id = f"task_{task_data['id']}"

        self.assertTrue(self.kg.graph.has_node(graph_node_id))

        success = self.kg.delete_node(task_data["id"])
        self.assertTrue(success)

        self.assertIsNone(self.kg.get_task(task_data["id"]))
        self.assertFalse(self.kg.graph.has_node(graph_node_id))

        # Test deleting non-existent node
        self.assertFalse(self.kg.delete_node("non_existent_generic_id"))


if __name__ == '__main__':
    unittest.main()

# Helper for timedelta if not imported in main file (it's usually part of datetime)
from datetime import timedelta
