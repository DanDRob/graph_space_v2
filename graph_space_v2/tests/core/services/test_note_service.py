import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
import uuid

from graph_space_v2.core.services.note_service import NoteService
from graph_space_v2.core.models.note import Note
from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph
from graph_space_v2.ai.embedding.embedding_service import EmbeddingService
from graph_space_v2.ai.llm.llm_service import LLMService
from graph_space_v2.utils.errors.exceptions import NoteServiceError, EntityNotFoundError, EmbeddingServiceError, LLMServiceError

class TestNoteService(unittest.TestCase):

    def setUp(self):
        self.mock_kg = MagicMock(spec=KnowledgeGraph)
        self.mock_embedding_service = MagicMock(spec=EmbeddingService)
        self.mock_llm_service = MagicMock(spec=LLMService)

        # Default LLM service to enabled for most tests
        self.mock_llm_service.enabled = True

        self.note_service = NoteService(
            knowledge_graph=self.mock_kg,
            embedding_service=self.mock_embedding_service,
            llm_service=self.mock_llm_service
        )

        # Reset mocks before each test
        self.mock_kg.reset_mock()
        self.mock_embedding_service.reset_mock()
        self.mock_llm_service.reset_mock()
        self.mock_llm_service.enabled = True # Ensure it's reset for each test

    def _get_sample_note_data_dict(self, id_val=None, content="Test content", title="Test Title", tags=None):
        if tags is None:
            tags = ["test"]
        return {
            "id": id_val or str(uuid.uuid4()),
            "title": title,
            "content": content,
            "tags": tags,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

    def test_add_note_simple_success(self):
        note_dict = self._get_sample_note_data_dict()
        note_id = note_dict["id"]
        self.mock_kg.add_note.return_value = note_id

        # Disable LLM and Embedding for this test
        self.note_service.llm_service = None
        self.note_service.embedding_service = None

        result_id = self.note_service.add_note(note_dict)

        self.assertEqual(result_id, note_id)
        self.mock_kg.add_note.assert_called_once()
        # Ensure that the data passed to kg.add_note is the processed dict
        called_note_data = self.mock_kg.add_note.call_args[0][0]
        self.assertEqual(called_note_data["id"], note_id)

    def test_add_note_with_llm_and_embedding(self):
        note_dict_initial = {"content": "This is a new note about AI.", "id": str(uuid.uuid4())}
        note_id = note_dict_initial["id"]

        self.mock_llm_service.generate_title.return_value = "AI Note"
        self.mock_llm_service.extract_tags.return_value = ["AI", "technology"]
        self.mock_embedding_service.embed_text.return_value = [0.1, 0.2, 0.3] # Dummy embedding
        self.mock_kg.add_note.return_value = note_id

        result_id = self.note_service.add_note(note_dict_initial)

        self.assertEqual(result_id, note_id)
        self.mock_llm_service.generate_title.assert_called_once_with("This is a new note about AI.")
        self.mock_llm_service.extract_tags.assert_called_once_with("This is a new note about AI.")
        self.mock_embedding_service.embed_text.assert_called_once_with("This is a new note about AI.")
        self.mock_embedding_service.store_embedding.assert_called_once()
        self.mock_kg.add_note.assert_called_once()

        called_note_data = self.mock_kg.add_note.call_args[0][0]
        self.assertEqual(called_note_data["title"], "AI Note")
        self.assertEqual(called_note_data["tags"], ["AI", "technology"])

    def test_add_note_kg_failure(self):
        note_dict = self._get_sample_note_data_dict()
        self.mock_kg.add_note.return_value = None # Simulate failure

        with self.assertRaises(NoteServiceError):
            self.note_service.add_note(note_dict)

    def test_get_note_found(self):
        note_id = "note123"
        note_data_dict = self._get_sample_note_data_dict(id_val=note_id)
        self.mock_kg.get_note.return_value = note_data_dict

        note_obj = self.note_service.get_note(note_id)

        self.assertIsNotNone(note_obj)
        self.assertIsInstance(note_obj, Note)
        self.assertEqual(note_obj.id, note_id)
        self.assertEqual(note_obj.title, note_data_dict["title"])
        self.mock_kg.get_note.assert_called_once_with(note_id)

    def test_get_note_not_found(self):
        note_id = "note123"
        self.mock_kg.get_note.return_value = None

        with self.assertRaises(NoteServiceError):
            self.note_service.get_note(note_id)
        self.mock_kg.get_note.assert_called_once_with(note_id)

    def test_get_all_notes(self):
        note_data_list = [self._get_sample_note_data_dict("1"), self._get_sample_note_data_dict("2")]
        self.mock_kg.data = {"notes": note_data_list} # Mock the .data attribute

        notes = self.note_service.get_all_notes()

        self.assertEqual(len(notes), 2)
        self.assertEqual(notes[0]["id"], "1")

    def test_update_note_success(self):
        note_id = "note123"
        original_note_data = self._get_sample_note_data_dict(id_val=note_id, content="Original content")
        update_payload = {"title": "Updated Title", "content": "Updated content."}

        # Mock KG interactions
        self.mock_kg.update_note.return_value = True
        # get_note is called after update to return the updated note
        updated_data_for_get = original_note_data.copy()
        updated_data_for_get.update(update_payload)
        updated_data_for_get["updated_at"] = datetime.now().isoformat() # approx
        self.mock_kg.get_note.return_value = updated_data_for_get

        # Mock embedding service
        self.mock_embedding_service.embed_text.return_value = [0.4,0.5,0.6]
        self.mock_embedding_service.update_embedding.return_value = True

        updated_note = self.note_service.update_note(note_id, update_payload)

        self.mock_kg.update_note.assert_called_once()
        # Ensure updated_at was added to payload before calling kg.update_note
        final_payload_to_kg = self.mock_kg.update_note.call_args[0][1]
        self.assertIn("updated_at", final_payload_to_kg)
        self.assertEqual(final_payload_to_kg["title"], "Updated Title")

        self.mock_embedding_service.embed_text.assert_called_once_with("Updated content.")
        self.mock_embedding_service.update_embedding.assert_called_once_with(note_id, [0.4,0.5,0.6])

        self.assertIsNotNone(updated_note)
        self.assertEqual(updated_note.title, "Updated Title")

    def test_update_note_llm_generation(self):
        note_id = "note_llm_update"
        original_note_data = self._get_sample_note_data_dict(id_val=note_id, title="Old Title", tags=["old"])
        # Update payload only has content, title and tags are empty, expecting LLM to fill them.
        update_payload = {"content": "New insightful content.", "title": "", "tags": []}

        self.mock_kg.update_note.return_value = True

        # Mock LLM responses
        self.mock_llm_service.generate_title.return_value = "Insightful Title"
        self.mock_llm_service.extract_tags.return_value = ["insight", "content"]

        # Mock get_note for the final retrieval
        final_note_data = original_note_data.copy()
        final_note_data.update(update_payload) # content updated
        final_note_data["title"] = "Insightful Title" # LLM generated
        final_note_data["tags"] = ["insight", "content"] # LLM generated
        self.mock_kg.get_note.return_value = final_note_data

        self.note_service.update_note(note_id, update_payload)

        self.mock_llm_service.generate_title.assert_called_once_with("New insightful content.")
        self.mock_llm_service.extract_tags.assert_called_once_with("New insightful content.")

        # Check that the data passed to kg.update_note includes LLM generated fields
        called_kg_payload = self.mock_kg.update_note.call_args[0][1]
        self.assertEqual(called_kg_payload["title"], "Insightful Title")
        self.assertEqual(called_kg_payload["tags"], ["insight", "content"])

    def test_update_note_not_found_kg(self):
        note_id = "note_not_exist"
        update_payload = {"title": "Ghost Title"}
        self.mock_kg.update_note.return_value = False # KG update fails
        self.mock_kg.get_note.return_value = None # KG confirms note doesn't exist

        with self.assertRaisesRegex(NoteServiceError, f"Note with ID {note_id} not found, cannot update."):
            self.note_service.update_note(note_id, update_payload)

    def test_delete_note_success(self):
        note_id = "note_to_delete"
        self.mock_kg.delete_note.return_value = True
        self.mock_embedding_service.delete_embedding.return_value = True # Assume success

        success = self.note_service.delete_note(note_id)

        self.assertTrue(success)
        self.mock_kg.delete_note.assert_called_once_with(note_id)
        self.mock_embedding_service.delete_embedding.assert_called_once_with(note_id)

    def test_delete_note_kg_failure(self):
        note_id = "note_fail_delete"
        self.mock_kg.delete_note.return_value = False
        # Simulate that the note still exists after failed deletion attempt
        self.mock_kg.get_note.return_value = self._get_sample_note_data_dict(id_val=note_id)

        with self.assertRaisesRegex(NoteServiceError, f"Failed to delete note with ID {note_id} from knowledge graph."):
            self.note_service.delete_note(note_id)

    def test_search_notes_semantic_success(self):
        query = "find my note"
        mock_embedding = [0.1,0.2,0.3]
        self.mock_embedding_service.embed_text.return_value = mock_embedding
        search_matches = [{"id": "note1", "score": 0.9, "text": "content1"}]
        self.mock_embedding_service.search.return_value = {"matches": search_matches}
        self.mock_kg.get_note.return_value = self._get_sample_note_data_dict(id_val="note1", content="content1")

        results = self.note_service.search_notes_by_content(query)

        self.mock_embedding_service.embed_text.assert_called_once_with(query)
        self.mock_embedding_service.search.assert_called_once_with(mock_embedding, 5, filter_by={"type": "note"})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["note"].id, "note1")

    def test_search_notes_fallback_to_simple(self):
        query = "find this"
        # Simulate embedding service not being available
        self.note_service.embedding_service = None

        # Mock KG data for simple search
        note_data1 = self._get_sample_note_data_dict("note_simple1", content="Contains find this query")
        note_data2 = self._get_sample_note_data_dict("note_simple2", content="Another note")
        self.mock_kg.data = {"notes": [note_data1, note_data2]}

        with patch.object(self.note_service, '_simple_text_search', return_value=[{"note": Note.from_dict(note_data1), "score":1}]) as mock_simple_search:
            results = self.note_service.search_notes_by_content(query)
            mock_simple_search.assert_called_once_with(query, 5)
            self.assertEqual(len(results), 1)

    def test_generate_tags_llm_success(self):
        note_id = "note_tag_gen"
        note_content = "Some interesting content for tags."
        original_tags = ["initial"]
        generated_tags = ["interesting", "content"]

        self.mock_kg.get_note.return_value = self._get_sample_note_data_dict(id_val=note_id, content=note_content, tags=original_tags)
        self.mock_llm_service.extract_tags.return_value = generated_tags
        self.mock_kg.update_note.return_value = True # Assume update is successful

        # Mock the get_note call that happens inside update_note
        # This is a bit tricky because update_note calls get_note. We need to handle multiple calls to get_note.
        updated_note_data_for_get = self._get_sample_note_data_dict(id_val=note_id, content=note_content, tags=list(set(original_tags + generated_tags)))

        # To handle multiple calls to get_note in a sequence within the tested method:
        self.mock_kg.get_note.side_effect = [
            self._get_sample_note_data_dict(id_val=note_id, content=note_content, tags=original_tags), # First call in generate_tags
            updated_note_data_for_get # Call from within update_note called by generate_tags
        ]

        tags = self.note_service.generate_tags(note_id)

        self.assertEqual(tags, generated_tags)
        self.mock_llm_service.extract_tags.assert_called_once_with(note_content)
        self.mock_kg.update_note.assert_called_once()
        # Check that the update payload had the merged tags
        update_payload_tags = self.mock_kg.update_note.call_args[0][1]["tags"]
        self.assertIn("initial", update_payload_tags)
        self.assertIn("interesting", update_payload_tags)

    def test_generate_tags_llm_disabled(self):
        self.mock_llm_service.enabled = False
        tags = self.note_service.generate_tags("note1")
        self.assertEqual(tags, [])
        self.mock_llm_service.extract_tags.assert_not_called()

    def test_summarize_note_llm_success(self):
        note_id = "note_summarize"
        note_content = "This is a long note that needs summarization."
        summary = "Long note summarized."

        self.mock_kg.get_note.return_value = self._get_sample_note_data_dict(id_val=note_id, content=note_content)
        self.mock_llm_service.summarize_text.return_value = summary

        result_summary = self.note_service.summarize_note(note_id)

        self.assertEqual(result_summary, summary)
        self.mock_llm_service.summarize_text.assert_called_once_with(note_content)

    def test_summarize_note_llm_disabled(self):
        self.mock_llm_service.enabled = False
        summary = self.note_service.summarize_note("note1")
        self.assertIsNone(summary)
        self.mock_llm_service.summarize_text.assert_not_called()

    def test_get_related_notes(self):
        note_id = "center_note"
        # Setup main note
        self.mock_kg.get_note.side_effect = lambda nid: {
            "center_note": self._get_sample_note_data_dict(id_val="center_note", content="Content of center note"),
            "graph_related_note": self._get_sample_note_data_dict(id_val="graph_related_note", content="Graph related"),
            "semantic_note1": self._get_sample_note_data_dict(id_val="semantic_note1", content="Semantic 1"),
        }.get(nid)

        # Mock KG relation
        kg_relation = [{"id": "graph_related_note", "type": "note", "relationship": "linked", "relationship_data": {"weight": 0.8}}]
        self.mock_kg.get_related_entities.return_value = kg_relation

        # Mock Embedding relation
        main_note_embedding = [0.1,0.1,0.1]
        self.mock_embedding_service.get_embedding.return_value = main_note_embedding
        semantic_search_matches = [{"id": "semantic_note1", "score": 0.95, "text": "Semantic 1"}]
        self.mock_embedding_service.search.return_value = {"matches": semantic_search_matches}

        related_notes = self.note_service.get_related_notes(note_id, max_results=5)

        self.assertEqual(len(related_notes), 2)
        ids_found = {r["note"].id for r in related_notes}
        self.assertIn("graph_related_note", ids_found)
        self.assertIn("semantic_note1", ids_found)

        self.mock_kg.get_related_entities.assert_called_once_with(note_id, "note")
        self.mock_embedding_service.get_embedding.assert_called_once_with(note_id)
        self.mock_embedding_service.search.assert_called_once()

if __name__ == '__main__':
    unittest.main()

# Need timedelta for task data generation
from datetime import timedelta
