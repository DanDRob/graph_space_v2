from typing import Dict, List, Any, Optional, Tuple, Union
import numpy as np
import os
import json
import uuid

from graph_space_v2.ai.embedding.embedding_service import EmbeddingService
from graph_space_v2.utils.errors.exceptions import EmbeddingError


class VectorStore:
    """
    A simplified wrapper around EmbeddingService focused on document storage and retrieval.
    Optimized for chunked documents with metadata.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        collection_name: str = "default"
    ):
        """
        Initialize the vector store.

        Args:
            embedding_service: The embedding service to use
            collection_name: Name of the collection to store vectors in
        """
        self.embedding_service = embedding_service
        self.collection_name = collection_name
        self.storage_path = os.path.join(
            self.embedding_service.storage_path,
            collection_name
        )

        # Create storage directory
        os.makedirs(self.storage_path, exist_ok=True)

    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Add multiple texts to the vector store.

        Args:
            texts: List of texts to add
            metadatas: Optional list of metadata dictionaries
            ids: Optional list of IDs for the texts

        Returns:
            List of IDs of the added texts
        """
        if not texts:
            return []

        # Generate IDs if not provided
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in texts]
        elif len(ids) != len(texts):
            raise ValueError("Length of ids must match length of texts")

        # Default empty metadata if not provided
        if metadatas is None:
            metadatas = [{} for _ in texts]
        elif len(metadatas) != len(texts):
            raise ValueError("Length of metadatas must match length of texts")

        # Generate embeddings for all texts
        try:
            embeddings = self.embedding_service.embed_texts(texts)
        except Exception as e:
            raise EmbeddingError(f"Error generating embeddings: {e}")

        # Store embeddings
        stored_ids = []
        for i, (text_id, text, metadata, embedding) in enumerate(zip(ids, texts, metadatas, embeddings)):
            # Add collection metadata
            metadata["collection"] = self.collection_name
            metadata["text"] = text

            # Store embedding
            self.embedding_service.store_embedding(
                id=text_id,
                embedding=embedding,
                metadata=metadata
            )
            stored_ids.append(text_id)

        return stored_ids

    def add_text(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        id: Optional[str] = None
    ) -> str:
        """
        Add a single text to the vector store.

        Args:
            text: Text to add
            metadata: Optional metadata dictionary
            id: Optional ID for the text

        Returns:
            ID of the added text
        """
        ids = self.add_texts(
            texts=[text],
            metadatas=[metadata] if metadata else None,
            ids=[id] if id else None
        )
        return ids[0]

    def similarity_search(
        self,
        query: str,
        k: int = 4,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar texts using the query.

        Args:
            query: Query text
            k: Number of results to return
            filter_metadata: Optional metadata filter

        Returns:
            List of dictionaries containing text, metadata, and score
        """
        # Add collection filter if not specified
        if filter_metadata is None:
            filter_metadata = {"collection": self.collection_name}
        elif "collection" not in filter_metadata:
            filter_metadata["collection"] = self.collection_name

        # Generate query embedding
        query_embedding = self.embedding_service.embed_text(query)

        # Search
        results = self.embedding_service.search(
            query_embedding=query_embedding,
            limit=k,
            filter_by=filter_metadata
        )

        # Format results
        formatted_results = []
        for match in results.get("matches", []):
            formatted_results.append({
                "id": match["id"],
                "text": match["text"],
                "metadata": match["metadata"],
                "score": match["score"]
            })

        return formatted_results

    def similarity_search_by_vector(
        self,
        embedding: np.ndarray,
        k: int = 4,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar texts using an embedding vector.

        Args:
            embedding: Query embedding
            k: Number of results to return
            filter_metadata: Optional metadata filter

        Returns:
            List of dictionaries containing text, metadata, and score
        """
        # Add collection filter if not specified
        if filter_metadata is None:
            filter_metadata = {"collection": self.collection_name}
        elif "collection" not in filter_metadata:
            filter_metadata["collection"] = self.collection_name

        # Search
        results = self.embedding_service.search(
            query_embedding=embedding,
            limit=k,
            filter_by=filter_metadata
        )

        # Format results
        formatted_results = []
        for match in results.get("matches", []):
            formatted_results.append({
                "id": match["id"],
                "text": match["text"],
                "metadata": match["metadata"],
                "score": match["score"]
            })

        return formatted_results

    def delete(self, ids: List[str]) -> None:
        """
        Delete texts from the vector store.

        Args:
            ids: List of IDs to delete
        """
        for id in ids:
            self.embedding_service.delete_embedding(id)

    def delete_collection(self) -> None:
        """
        Delete the entire collection.
        """
        # Get all embeddings with this collection
        to_delete = []
        for id, item in self.embedding_service.embeddings.items():
            if item.metadata.get("collection") == self.collection_name:
                to_delete.append(id)

        # Delete them
        for id in to_delete:
            self.embedding_service.delete_embedding(id)

    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the collection.

        Returns:
            Dictionary with collection statistics
        """
        # Count embeddings in this collection
        count = 0
        for item in self.embedding_service.embeddings.values():
            if item.metadata.get("collection") == self.collection_name:
                count += 1

        return {
            "collection_name": self.collection_name,
            "count": count,
            "storage_path": self.storage_path
        }
