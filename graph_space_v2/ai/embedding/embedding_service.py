from typing import Dict, List, Any, Optional, Tuple, Union
import torch
import numpy as np
from sentence_transformers import SentenceTransformer
import os
import json
import uuid
from dataclasses import dataclass, field
import faiss
import pickle
import networkx as nx

from graph_space_v2.utils.errors.exceptions import EmbeddingError
from graph_space_v2.utils.helpers.path_utils import ensure_dir_exists, get_data_dir


@dataclass
class EmbeddingItem:
    """Class for storing item with its embedding."""
    id: str
    text: str
    embedding: np.ndarray
    metadata: Dict[str, Any] = field(default_factory=dict)


class EmbeddingService:
    """Service for text embeddings and semantic search."""

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-mpnet-base-v2",
        dimension: int = 768,
        device: Optional[str] = None,
        storage_path: Optional[str] = None
    ):
        """
        Initialize the embedding service.

        Args:
            model_name: The name or path of the embedding model to use
            dimension: The dimension of the embeddings
            device: The device to use for the model ('cpu' or 'cuda')
            storage_path: Path to store embeddings and index
        """
        # Disable FAISS GPU usage to avoid error messages when GPU is not properly configured
        try:
            import faiss.contrib.torch_utils
            faiss.contrib.torch_utils.using_gpu = False
        except ImportError:
            pass

        self.model_name = model_name
        self.dimension = dimension
        self.storage_path = storage_path or os.path.join(
            get_data_dir(), "embeddings")
        ensure_dir_exists(self.storage_path)

        # Determine device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device

        # Initialize model
        try:
            self.model = SentenceTransformer(model_name, device=self.device)
            print(f"Loaded embedding model: {model_name} on {self.device}")
        except Exception as e:
            print(f"Error loading embedding model: {e}")
            print("Using a randomly initialized embedding function instead.")
            self.model = None

        # Create storage directory if it doesn't exist
        os.makedirs(self.storage_path, exist_ok=True)

        # Initialize embeddings storage
        self.embeddings: Dict[str, EmbeddingItem] = {}
        self.index = None

        # Load existing embeddings if available
        self._load_embeddings()
        self._build_index()

        # Cache for embeddings
        self.embeddings_cache = {}
        self._load_cache()

    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for a piece of text.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        if not text.strip():
            return np.zeros(self.dimension)

        if self.model is None:
            # Fallback to random embeddings
            return np.random.randn(self.dimension).astype(np.float32)

        try:
            # Generate embedding
            embedding = self.model.encode(text, convert_to_tensor=True)
            return embedding.cpu().numpy().astype(np.float32)
        except Exception as e:
            raise EmbeddingError(f"Error generating embedding: {e}")

    def embed_texts(self, texts: List[str]) -> List[np.ndarray]:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        if self.model is None:
            # Fallback to random embeddings
            return [np.random.randn(self.dimension).astype(np.float32) for _ in texts]

        try:
            # Generate embeddings
            embeddings = self.model.encode(texts, convert_to_tensor=True)
            return [e.cpu().numpy().astype(np.float32) for e in embeddings]
        except Exception as e:
            raise EmbeddingError(f"Error generating batch embeddings: {e}")

    def store_embedding(self, id: str, embedding: np.ndarray, metadata: Dict[str, Any] = None) -> None:
        """
        Store an embedding with metadata.

        Args:
            id: ID for the embedding
            embedding: The embedding vector
            metadata: Optional metadata
        """
        metadata = metadata or {}
        text = metadata.get("text", "")

        # Store the embedding
        self.embeddings[id] = EmbeddingItem(
            id=id,
            text=text,
            embedding=embedding,
            metadata=metadata
        )

        # Rebuild the index
        self._build_index()

        # Save to disk
        self._save_embeddings()

    def update_embedding(self, id: str, embedding: np.ndarray, metadata: Dict[str, Any] = None) -> bool:
        """
        Update an existing embedding.

        Args:
            id: ID of the embedding to update
            embedding: New embedding vector
            metadata: Optional new metadata

        Returns:
            True if successful, False if not found
        """
        if id not in self.embeddings:
            return False

        existing_item = self.embeddings[id]

        # Update embedding
        existing_item.embedding = embedding

        # Update metadata if provided
        if metadata is not None:
            existing_item.metadata.update(metadata)
            if "text" in metadata:
                existing_item.text = metadata["text"]

        # Rebuild the index
        self._build_index()

        # Save to disk
        self._save_embeddings()

        return True

    def delete_embedding(self, id: str) -> bool:
        """
        Delete an embedding.

        Args:
            id: ID of the embedding to delete

        Returns:
            True if successful, False if not found
        """
        if id not in self.embeddings:
            return False

        # Remove the embedding
        del self.embeddings[id]

        # Rebuild the index
        self._build_index()

        # Save to disk
        self._save_embeddings()

        return True

    def get_embedding(self, id: str) -> Optional[np.ndarray]:
        """
        Get an embedding by ID.

        Args:
            id: ID of the embedding

        Returns:
            The embedding vector or None if not found
        """
        if id not in self.embeddings:
            return None

        return self.embeddings[id].embedding

    def search(self, query_embedding: np.ndarray, limit: int = 5, filter_by: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Search for similar embeddings.

        Args:
            query_embedding: The query embedding vector
            limit: Maximum number of results to return
            filter_by: Optional filter criteria

        Returns:
            Dictionary with search results
        """
        if not self.embeddings:
            return {"matches": []}

        if self.index is None:
            self._build_index()

        # If we still don't have an index, return empty results
        if self.index is None:
            return {"matches": []}

        # Normalize the query embedding if necessary
        query_embedding = query_embedding.astype(np.float32)
        if np.linalg.norm(query_embedding) > 0:
            query_embedding = query_embedding / np.linalg.norm(query_embedding)

        # Search the index
        scores, indices = self.index.search(
            np.expand_dims(query_embedding, axis=0),
            min(limit * 2, len(self.embeddings))  # Fetch more for filtering
        )

        # Convert to list of IDs and filter results
        id_list = list(self.embeddings.keys())
        matches = []

        for i, idx in enumerate(indices[0]):
            if idx < 0 or idx >= len(id_list):
                continue

            item_id = id_list[idx]
            item = self.embeddings[item_id]

            # Apply filters if any
            if filter_by and not self._matches_filter(item.metadata, filter_by):
                continue

            matches.append({
                "id": item.id,
                "text": item.text,
                "score": float(scores[0][i]),
                "metadata": item.metadata
            })

            if len(matches) >= limit:
                break

        return {"matches": matches}

    def _matches_filter(self, metadata: Dict[str, Any], filter_by: Dict[str, Any]) -> bool:
        """Check if metadata matches the filter criteria."""
        for key, value in filter_by.items():
            if key not in metadata:
                return False

            # Handle list of allowed values
            if isinstance(value, list):
                if metadata[key] not in value:
                    return False
            # Handle exact match
            elif metadata[key] != value:
                return False

        return True

    def _build_index(self) -> None:
        """Build or rebuild the search index."""
        if not self.embeddings:
            self.index = None
            return

        # Create FAISS index - explicitly using CPU version to avoid GPU loading errors
        try:
            # Make sure we're using the CPU implementation
            import faiss.contrib.torch_utils
            faiss.contrib.torch_utils.using_gpu = False

            self.index = faiss.IndexFlatL2(self.dimension)

            # Add embeddings to the index
            embeddings_array = np.stack(
                [item.embedding for item in self.embeddings.values()])

            # Normalize embeddings
            faiss.normalize_L2(embeddings_array)

            # Add to index
            self.index.add(embeddings_array)
        except Exception as e:
            print(f"Error building index: {e}")
            self.index = None

    def _load_embeddings(self) -> None:
        """Load embeddings from disk."""
        embeddings_file = os.path.join(self.storage_path, "embeddings.json")
        if not os.path.exists(embeddings_file):
            return

        try:
            with open(embeddings_file, "r") as f:
                data = json.load(f)

            # Load embeddings from data
            for item_data in data:
                item = EmbeddingItem(
                    id=item_data["id"],
                    text=item_data["text"],
                    embedding=np.array(
                        item_data["embedding"], dtype=np.float32),
                    metadata=item_data["metadata"]
                )
                self.embeddings[item.id] = item

            print(
                f"Loaded {len(self.embeddings)} embeddings from {embeddings_file}")
        except Exception as e:
            print(f"Error loading embeddings: {e}")
            self.embeddings = {}

    def _save_embeddings(self) -> None:
        """Save embeddings to disk."""
        embeddings_file = os.path.join(self.storage_path, "embeddings.json")

        try:
            # Convert embeddings to JSON-serializable format
            data = []
            for item in self.embeddings.values():
                item_data = {
                    "id": item.id,
                    "text": item.text,
                    "embedding": item.embedding.tolist(),
                    "metadata": item.metadata
                }
                data.append(item_data)

            # Save to file
            with open(embeddings_file, "w") as f:
                json.dump(data, f)

            print(
                f"Saved {len(self.embeddings)} embeddings to {embeddings_file}")
        except Exception as e:
            print(f"Error saving embeddings: {e}")

    def train_on_graph(self, graph) -> None:
        """
        Train embeddings on graph structure using node2vec or similar.

        Args:
            graph: NetworkX graph
        """
        # Skip if graph is too small
        if len(graph.nodes) < 2:
            return

        try:
            import node2vec
            import networkx as nx

            # Prepare node2vec model
            n2v = node2vec.Node2Vec(
                graph,
                dimensions=self.dimension,
                walk_length=30,
                num_walks=200,
                workers=4
            )
            model = n2v.fit(window=10, min_count=1)

            # Get embeddings for all nodes
            for node in graph.nodes():
                try:
                    # Get node embedding from model
                    node_vec = model.wv[node]

                    # Extract ID from node name (e.g., "note_123" -> "123")
                    if "_" in node:
                        node_type, node_id = node.split("_", 1)

                        # Get text content from node attributes
                        node_data = graph.nodes[node]
                        text = ""
                        if node_type == "note":
                            text = node_data.get("content", "")
                        elif node_type == "task":
                            text = node_data.get("description", "")
                        elif node_type == "contact":
                            name = node_data.get("name", "")
                            email = node_data.get("email", "")
                            text = f"{name} {email}"

                        # Store embedding
                        self.store_embedding(
                            id=node_id,
                            embedding=node_vec,
                            metadata={
                                "type": node_type,
                                "text": text,
                                "source": "graph_embedding"
                            }
                        )
                except KeyError:
                    # Skip nodes not in vocabulary
                    continue

            print(
                f"Trained and stored embeddings for {len(graph.nodes)} nodes")
        except ImportError:
            print("Could not train graph embeddings: node2vec package not available")
        except Exception as e:
            print(f"Error training graph embeddings: {e}")

    def get_vector_store_info(self) -> Dict[str, Any]:
        """
        Get information about the vector store.

        Returns:
            Dictionary with vector store statistics
        """
        entity_types = {}
        for item in self.embeddings.values():
            entity_type = item.metadata.get("type", "unknown")
            entity_types[entity_type] = entity_types.get(entity_type, 0) + 1

        return {
            "total_embeddings": len(self.embeddings),
            "model_name": self.model_name,
            "dimension": self.dimension,
            "storage_path": self.storage_path,
            "entity_types": entity_types,
            "index_built": self.index is not None
        }

    def _load_cache(self) -> None:
        """Load embeddings cache from disk."""
        cache_file = os.path.join(self.storage_path, "embeddings_cache.pkl")
        if not os.path.exists(cache_file):
            return

        try:
            with open(cache_file, "rb") as f:
                self.embeddings_cache = pickle.load(f)
            print(
                f"Loaded {len(self.embeddings_cache)} embeddings from {cache_file}")
        except Exception as e:
            print(f"Error loading embeddings cache: {e}")
            self.embeddings_cache = {}

    def _save_cache(self) -> None:
        """Save embeddings cache to disk."""
        cache_file = os.path.join(self.storage_path, "embeddings_cache.pkl")

        try:
            # Save to file
            with open(cache_file, "wb") as f:
                pickle.dump(self.embeddings_cache, f)
            print(
                f"Saved {len(self.embeddings_cache)} embeddings to {cache_file}")
        except Exception as e:
            print(f"Error saving embeddings cache: {e}")
