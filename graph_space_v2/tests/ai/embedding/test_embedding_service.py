import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import tempfile
import pickle
import json
import numpy as np
import networkx as nx

from graph_space_v2.ai.embedding.embedding_service import EmbeddingService, EmbeddingItem
from graph_space_v2.utils.errors.exceptions import EmbeddingServiceError

# Define a fixed dimension for testing
TEST_DIMENSION = 3

def mock_sentence_transformer_encode(texts, convert_to_tensor=False):
    """
    Mock of SentenceTransformer.encode.
    Returns a list of dummy embeddings or a single dummy embedding.
    """
    if isinstance(texts, str): # Single text
        # Simple hash-based deterministic "embedding" for testing
        val = hash(texts) % 1000 / 1000.0
        emb = np.array([val, val + 0.1, val + 0.2], dtype=np.float32)[:TEST_DIMENSION]
    else: # Batch of texts
        emb = []
        for text in texts:
            val = hash(text) % 1000 / 1000.0
            emb.append(np.array([val, val + 0.1, val + 0.2], dtype=np.float32)[:TEST_DIMENSION])

    # Mocking SentenceTransformer's output structure (numpy arrays)
    if convert_to_tensor: # As used in the service
        # This part is tricky because the service converts to tensor then back to numpy.
        # For the mock, we just need to ensure the final numpy output is correct.
        # The actual tensor conversion won't happen with this mock.
        # The service does: embedding.cpu().numpy().astype(np.float32)
        # So, our direct numpy output here is fine.
        pass # No need to actually convert to tensor for the mock's purpose

    return MagicMock(cpu=MagicMock(return_value=MagicMock(numpy=MagicMock(return_value=np.array(emb, dtype=np.float32))))) if isinstance(texts, str) else \
           [MagicMock(cpu=MagicMock(return_value=MagicMock(numpy=MagicMock(return_value=np.array(e, dtype=np.float32))))) for e in emb]


@patch('graph_space_v2.ai.embedding.embedding_service.SentenceTransformer')
class TestEmbeddingService(unittest.TestCase):

    def setUp(self, MockSentenceTransformer):
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.temp_storage_path = self.temp_dir_obj.name

        self.mock_model_instance = MagicMock()
        # Configure the encode method of the mock model instance
        self.mock_model_instance.encode.side_effect = mock_sentence_transformer_encode
        MockSentenceTransformer.return_value = self.mock_model_instance

        self.service = EmbeddingService(
            model_name="mock-model",
            dimension=TEST_DIMENSION,
            storage_path=self.temp_storage_path
        )
        # Reset call counts for each test
        self.mock_model_instance.encode.reset_mock()


    def tearDown(self):
        self.temp_dir_obj.cleanup()

    def test_embed_text_new(self, MockSentenceTransformer):
        text = "hello world"
        embedding = self.service.embed_text(text)

        self.assertIsNotNone(embedding)
        self.assertEqual(embedding.shape, (TEST_DIMENSION,))
        self.mock_model_instance.encode.assert_called_once_with(text, convert_to_tensor=True)
        self.assertIn(text, self.service.embeddings_cache) # Check if cached

    def test_embed_text_cached(self, MockSentenceTransformer):
        text = "hello world"
        self.service.embed_text(text) # First call, caches
        self.mock_model_instance.encode.reset_mock() # Reset mock after first call

        embedding = self.service.embed_text(text) # Second call, should use cache

        self.assertIsNotNone(embedding)
        self.assertEqual(embedding.shape, (TEST_DIMENSION,))
        self.mock_model_instance.encode.assert_not_called() # Should not be called due to cache hit

    def test_embed_text_empty_string(self, MockSentenceTransformer):
        embedding = self.service.embed_text("   ") # Empty or whitespace only
        self.assertTrue(np.array_equal(embedding, np.zeros(TEST_DIMENSION)))
        self.mock_model_instance.encode.assert_not_called()
        # Check cache behavior for empty strings (might not be cached, or cached as zeros)
        # Current implementation does not cache empty/whitespace strings prior to zero vector return.
        self.assertNotIn("   ", self.service.embeddings_cache)


    def test_embed_texts_all_new(self, MockSentenceTransformer):
        texts = ["text one", "text two"]
        embeddings = self.service.embed_texts(texts)

        self.assertEqual(len(embeddings), 2)
        self.assertEqual(embeddings[0].shape, (TEST_DIMENSION,))
        self.assertEqual(embeddings[1].shape, (TEST_DIMENSION,))
        # Check if encode was called with the list of texts needing embedding
        self.mock_model_instance.encode.assert_called_once_with(texts, convert_to_tensor=True)
        self.assertIn(texts[0], self.service.embeddings_cache)
        self.assertIn(texts[1], self.service.embeddings_cache)

    def test_embed_texts_mixed_cache(self, MockSentenceTransformer):
        texts = ["text one", "text two", "text one"]

        # First call for "text one" to cache it
        self.service.embed_text("text one")
        self.mock_model_instance.encode.reset_mock() # Reset after caching "text one"

        embeddings = self.service.embed_texts(texts)

        self.assertEqual(len(embeddings), 3)
        self.assertEqual(embeddings[0].shape, (TEST_DIMENSION,)) # from cache
        self.assertEqual(embeddings[1].shape, (TEST_DIMENSION,)) # new
        self.assertEqual(embeddings[2].shape, (TEST_DIMENSION,)) # from cache

        # Encode should only be called for "text two"
        self.mock_model_instance.encode.assert_called_once_with(["text two"], convert_to_tensor=True)
        self.assertIn("text two", self.service.embeddings_cache)

        # Verify "text one" embedding is consistent
        self.assertTrue(np.array_equal(embeddings[0], embeddings[2]))
        self.assertTrue(np.array_equal(embeddings[0], self.service.embeddings_cache["text one"]))

    def test_embed_texts_all_cached(self, MockSentenceTransformer):
        texts = ["text one", "text two"]
        self.service.embed_texts(texts) # Cache them
        self.mock_model_instance.encode.reset_mock()

        embeddings = self.service.embed_texts(texts)
        self.assertEqual(len(embeddings), 2)
        self.mock_model_instance.encode.assert_not_called()

    def test_embed_texts_with_empty_strings(self, MockSentenceTransformer):
        texts = ["text one", "  ", "text two"]
        embeddings = self.service.embed_texts(texts)
        self.assertEqual(len(embeddings), 3)
        self.assertFalse(np.all(embeddings[0] == 0)) # text one should not be zeros
        self.assertTrue(np.array_equal(embeddings[1], np.zeros(TEST_DIMENSION))) # empty string
        self.assertFalse(np.all(embeddings[2] == 0)) # text two should not be zeros

        # Encode should be called for "text one" and "text two"
        self.mock_model_instance.encode.assert_called_once_with(["text one", "text two"], convert_to_tensor=True)

    # --- Store, Get, Update, Delete Tests ---
    @patch('graph_space_v2.ai.embedding.embedding_service.EmbeddingService._build_index')
    @patch('graph_space_v2.ai.embedding.embedding_service.EmbeddingService._save_embeddings')
    def test_store_and_get_embedding(self, mock_save, mock_build_index, MockSentenceTransformer):
        emb_id = "test_id_1"
        embedding_vector = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        metadata = {"text": "some text for id1", "type": "test"}

        self.service.store_embedding(emb_id, embedding_vector, metadata)
        mock_save.assert_called_once()
        mock_build_index.assert_called_once() # store_embedding rebuilds index

        retrieved_embedding = self.service.get_embedding(emb_id)
        self.assertTrue(np.array_equal(retrieved_embedding, embedding_vector))

        # Test getting non-existent
        with self.assertRaises(EmbeddingServiceError):
            self.service.get_embedding("non_existent_id")

    @patch('graph_space_v2.ai.embedding.embedding_service.EmbeddingService._build_index')
    @patch('graph_space_v2.ai.embedding.embedding_service.EmbeddingService._save_embeddings')
    def test_update_embedding(self, mock_save, mock_build_index, MockSentenceTransformer):
        emb_id = "test_id_update"
        initial_embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        updated_embedding = np.array([0.4, 0.5, 0.6], dtype=np.float32)
        metadata = {"text": "initial text"}

        self.service.store_embedding(emb_id, initial_embedding, metadata) # This calls save and build_index once
        mock_save.reset_mock()
        mock_build_index.reset_mock()

        success = self.service.update_embedding(emb_id, updated_embedding, {"text": "updated text"})
        self.assertTrue(success)
        mock_save.assert_called_once()
        mock_build_index.assert_called_once()

        retrieved = self.service.get_embedding(emb_id)
        self.assertTrue(np.array_equal(retrieved, updated_embedding))
        self.assertEqual(self.service.embeddings[emb_id].metadata["text"], "updated text")

        with self.assertRaises(EmbeddingServiceError):
            self.service.update_embedding("non_existent_id", updated_embedding)

    @patch('graph_space_v2.ai.embedding.embedding_service.EmbeddingService._build_index')
    @patch('graph_space_v2.ai.embedding.embedding_service.EmbeddingService._save_embeddings')
    def test_delete_embedding(self, mock_save, mock_build_index, MockSentenceTransformer):
        emb_id = "test_id_delete"
        embedding_vector = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        self.service.store_embedding(emb_id, embedding_vector)
        mock_save.reset_mock()
        mock_build_index.reset_mock()

        success = self.service.delete_embedding(emb_id)
        self.assertTrue(success)
        mock_save.assert_called_once()
        mock_build_index.assert_called_once()

        with self.assertRaises(EmbeddingServiceError):
            self.service.get_embedding(emb_id)

        with self.assertRaises(EmbeddingServiceError):
            self.service.delete_embedding("non_existent_id")

    # --- Persistence Tests ---
    @patch('graph_space_v2.ai.embedding.embedding_service.EmbeddingService._build_index') # Mock build_index for these
    def test_load_and_save_embeddings_json(self, mock_build_index, MockSentenceTransformer):
        emb_id1 = "persist_id1"
        emb_vec1 = np.array([0.1,0.2,0.3], dtype=np.float32)
        meta1 = {"text": "text1"}
        self.service.store_embedding(emb_id1, emb_vec1, meta1) # This calls _save_embeddings

        # Create new service instance to load from the saved file
        service2 = EmbeddingService(
            model_name="mock-model",
            dimension=TEST_DIMENSION,
            storage_path=self.temp_storage_path
        )
        # Ensure the mock is correctly applied to service2 as well if SentenceTransformer is called in its __init__
        # MockSentenceTransformer should still be active due to class-level patch

        loaded_emb = service2.get_embedding(emb_id1)
        self.assertIsNotNone(loaded_emb)
        self.assertTrue(np.array_equal(loaded_emb, emb_vec1))
        self.assertEqual(service2.embeddings[emb_id1].metadata["text"], "text1")

    def test_load_and_save_cache_pkl(self, MockSentenceTransformer):
        text_to_cache = "this text will be cached"
        # First call embeds and saves to cache file
        original_embedding = self.service.embed_text(text_to_cache)

        # Create new service instance, it should load the cache
        service2 = EmbeddingService(
            model_name="mock-model",
            dimension=TEST_DIMENSION,
            storage_path=self.temp_storage_path
        )
        self.mock_model_instance.encode.reset_mock() # Reset mock before testing cache hit

        # This call should hit the cache loaded from file
        cached_embedding = service2.embed_text(text_to_cache)
        self.mock_model_instance.encode.assert_not_called()
        self.assertTrue(np.array_equal(original_embedding, cached_embedding))


    # --- Search and Train Tests (More complex mocking) ---
    @patch('graph_space_v2.ai.embedding.embedding_service.faiss')
    @patch('graph_space_v2.ai.embedding.embedding_service.EmbeddingService._save_embeddings') # No need to save during search test
    def test_search_embeddings(self, mock_save_embeddings, mock_faiss, MockSentenceTransformer):
        # Configure faiss mock
        mock_index_instance = MagicMock()
        mock_faiss.IndexFlatL2.return_value = mock_index_instance

        # Populate some embeddings
        emb_data = {
            "id1": {"text": "apple pie", "embedding": np.array([0.1, 0.2, 0.3], dtype=np.float32)},
            "id2": {"text": "banana bread", "embedding": np.array([0.4, 0.1, 0.2], dtype=np.float32)},
            "id3": {"text": "apple crumble", "embedding": np.array([0.1, 0.3, 0.4], dtype=np.float32)},
        }
        for id_key, data in emb_data.items():
            self.service.store_embedding(id_key, data["embedding"], {"text": data["text"], "type":"food"})

        # _build_index would have been called by store_embedding
        mock_faiss.IndexFlatL2.assert_called_with(TEST_DIMENSION) # Check index initialized correctly
        self.assertTrue(mock_index_instance.add.called)

        # Mock search results (scores, indices)
        # Indices should correspond to the order items were added if self.embeddings.values() is stable,
        # or map to keys. For simplicity, assume order of insertion.
        # Let's say query is most similar to id3, then id1
        # FAISS returns distances, so lower is better. Search method should handle this.
        # The service normalizes embeddings, so scores are cosine similarities (higher is better).
        # Let's assume _build_index stores items in order id1, id2, id3
        # So indices from faiss.search would be 0, 1, 2
        # If query is like "apple", we want id3 and id1.

        # Faiss search result: (distances, indices)
        # Let's say query matches "id3" (index 2) best, then "id1" (index 0)
        # Note: The service normalizes and uses IndexFlatL2, then does its own score adjustment.
        # For testing, we care that the IDs returned by `search` are correct based on mocked faiss output.
        # The service currently gets list(self.embeddings.keys()) for id_list. Order matters.
        # Let's assume keys are ordered: id1, id2, id3

        mock_index_instance.search.return_value = (
            np.array([[0.1, 0.5]], dtype=np.float32), # scores/distances
            np.array([[2, 0]], dtype=np.int64)      # indices (id3, then id1)
        )

        query_vec = np.array([0.11, 0.21, 0.31], dtype=np.float32) # Dummy query
        results = self.service.search(query_vec, limit=2)

        mock_index_instance.search.assert_called_once()
        self.assertEqual(len(results["matches"]), 2)
        self.assertEqual(results["matches"][0]["id"], "id3") # Corresponds to index 2
        self.assertEqual(results["matches"][1]["id"], "id1") # Corresponds to index 0


    @patch('graph_space_v2.ai.embedding.embedding_service.node2vec')
    @patch('graph_space_v2.ai.embedding.embedding_service.EmbeddingService._build_index') # Mock build_index
    @patch('graph_space_v2.ai.embedding.embedding_service.EmbeddingService._save_embeddings') # Mock save
    def test_train_on_graph(self, mock_save, mock_build, mock_node2vec_module, MockSentenceTransformer):
        # Prepare mock for node2vec
        mock_n2v_instance = MagicMock()
        mock_node2vec_module.Node2Vec.return_value = mock_n2v_instance

        mock_wv = MagicMock()
        # Let wv act like a dictionary for node embeddings
        node_embeddings_dict = {
            "note_graph1": np.array([0.5,0.6,0.7], dtype=np.float32),
            "task_graph2": np.array([0.8,0.9,0.1], dtype=np.float32),
        }
        mock_wv.__getitem__.side_effect = lambda key: node_embeddings_dict[key]
        mock_n2v_instance.fit.return_value = MagicMock(wv=mock_wv)

        # Create a sample graph
        g = nx.Graph()
        g.add_node("note_graph1", content="Content for graph note 1")
        g.add_node("task_graph2", description="Description for graph task 2")
        g.add_node("contact_graph3", name="Graph Contact") # No specific content field defined in service for contacts
        g.add_edge("note_graph1", "task_graph2")

        self.service.train_on_graph(g)

        mock_node2vec_module.Node2Vec.assert_called_once()
        mock_n2v_instance.fit.assert_called_once()

        # Check if store_embedding was called for the nodes that had text and were in node_embeddings_dict
        # (store_embedding calls _save_embeddings and _build_index)
        # There should be 2 calls to store_embedding (note_graph1, task_graph2)
        # Each store_embedding calls _save_embeddings and _build_index once
        self.assertEqual(mock_save.call_count, 2)
        self.assertEqual(mock_build.call_count, 2)

        # Verify embeddings were stored
        retrieved_note_emb = self.service.get_embedding("graph1")
        self.assertTrue(np.array_equal(retrieved_note_emb, node_embeddings_dict["note_graph1"]))

        retrieved_task_emb = self.service.get_embedding("graph2")
        self.assertTrue(np.array_equal(retrieved_task_emb, node_embeddings_dict["task_graph2"]))

        # Check metadata was stored
        self.assertEqual(self.service.embeddings["graph1"].metadata["type"], "note")
        self.assertEqual(self.service.embeddings["graph1"].metadata["source"], "graph_embedding")
        self.assertEqual(self.service.embeddings["graph2"].metadata["type"], "task")


if __name__ == '__main__':
    unittest.main()
