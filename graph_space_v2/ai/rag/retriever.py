from typing import Dict, List, Any, Optional, Union
import numpy as np

from graph_space_v2.ai.embedding.embedding_service import EmbeddingService
from graph_space_v2.ai.embedding.vector_store import VectorStore
from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph


class Retriever:
    """Retriever component for the RAG system."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        knowledge_graph: Optional[KnowledgeGraph] = None,
        vector_store: Optional[VectorStore] = None
    ):
        """
        Initialize the retriever.

        Args:
            embedding_service: Embedding service for semantic search
            knowledge_graph: Optional knowledge graph for graph-based retrieval
            vector_store: Optional vector store for dense retrieval
        """
        self.embedding_service = embedding_service
        self.knowledge_graph = knowledge_graph
        self.vector_store = vector_store

        # Create vector store if not provided
        if self.vector_store is None and self.embedding_service is not None:
            self.vector_store = VectorStore(
                embedding_service=self.embedding_service,
                collection_name="rag_collection"
            )

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        retrieval_type: str = "hybrid",
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve contexts for a query.

        Args:
            query: Query text
            top_k: Number of results to retrieve
            retrieval_type: Type of retrieval (dense, sparse, hybrid, or graph)
            filters: Optional filters to apply

        Returns:
            List of retrieved contexts with metadata
        """
        if retrieval_type == "dense":
            return self._dense_retrieval(query, top_k, filters)
        elif retrieval_type == "graph":
            return self._graph_retrieval(query, top_k, filters)
        elif retrieval_type == "hybrid":
            return self._hybrid_retrieval(query, top_k, filters)
        else:
            # Default to dense retrieval
            return self._dense_retrieval(query, top_k, filters)

    def _dense_retrieval(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform dense retrieval using the vector store.

        Args:
            query: Query text
            top_k: Number of results to retrieve
            filters: Optional filters to apply

        Returns:
            List of retrieved contexts with metadata
        """
        if self.vector_store is None:
            return []

        results = self.vector_store.similarity_search(
            query=query,
            k=top_k,
            filter_metadata=filters
        )

        return [
            {
                "text": result["text"],
                "metadata": result["metadata"],
                "score": result["score"],
                "id": result["id"],
                "source": "vector_store"
            }
            for result in results
        ]

    def _graph_retrieval(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform graph-based retrieval using the knowledge graph.

        Args:
            query: Query text
            top_k: Number of results to retrieve
            filters: Optional filters to apply

        Returns:
            List of retrieved contexts with metadata
        """
        if self.knowledge_graph is None:
            return []

        # First, embed the query to find semantically similar nodes
        query_embedding = self.embedding_service.embed_text(query)

        # Find nearest nodes in the graph
        nearest_nodes = []

        for node_id, node_embedding in self.knowledge_graph.node_embeddings.items():
            if not node_embedding.size:
                continue

            # Calculate cosine similarity
            similarity = np.dot(query_embedding, node_embedding) / (
                np.linalg.norm(query_embedding) *
                np.linalg.norm(node_embedding)
            )

            # Filter by entity type if specified
            if filters and "entity_type" in filters:
                node_type = node_id.split("_")[0] if "_" in node_id else ""
                if node_type != filters["entity_type"]:
                    continue

            nearest_nodes.append((node_id, similarity))

        # Sort by similarity and take top_k
        nearest_nodes.sort(key=lambda x: x[1], reverse=True)
        nearest_nodes = nearest_nodes[:top_k]

        # Convert node IDs to entity data
        results = []
        for node_id, score in nearest_nodes:
            node_type = node_id.split("_")[0] if "_" in node_id else ""
            entity_id = node_id.split("_")[1] if "_" in node_id else node_id

            if node_type == "note":
                entity = self.knowledge_graph.get_note(entity_id)
                if entity:
                    text = entity.get("content", "")
                    results.append({
                        "text": text,
                        "metadata": {
                            "type": "note",
                            "id": entity_id,
                            "title": entity.get("title", "")
                        },
                        "score": float(score),
                        "id": entity_id,
                        "source": "knowledge_graph"
                    })
            elif node_type == "task":
                entity = self.knowledge_graph.get_task(entity_id)
                if entity:
                    text = entity.get("description", "")
                    results.append({
                        "text": text,
                        "metadata": {
                            "type": "task",
                            "id": entity_id,
                            "title": entity.get("title", "")
                        },
                        "score": float(score),
                        "id": entity_id,
                        "source": "knowledge_graph"
                    })

        return results

    def _hybrid_retrieval(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid retrieval combining dense and graph-based approaches.

        Args:
            query: Query text
            top_k: Number of results to retrieve
            filters: Optional filters to apply

        Returns:
            List of retrieved contexts with metadata
        """
        # Get results from both methods
        dense_results = self._dense_retrieval(query, top_k, filters)
        graph_results = self._graph_retrieval(query, top_k, filters)

        # Combine and deduplicate results
        combined_results = {}

        for result in dense_results + graph_results:
            result_id = result["id"]
            if result_id not in combined_results or result["score"] > combined_results[result_id]["score"]:
                combined_results[result_id] = result

        # Sort by score and take top_k
        sorted_results = sorted(
            combined_results.values(),
            key=lambda x: x["score"],
            reverse=True
        )[:top_k]

        return sorted_results

    def add_texts(
        self,
        texts: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Add texts to the retriever.

        Args:
            texts: List of texts to add
            metadatas: Optional list of metadata for each text
            ids: Optional list of IDs for each text

        Returns:
            List of IDs of added texts
        """
        if self.vector_store is None:
            return []

        return self.vector_store.add_texts(texts, metadatas, ids)

    def add_nodes_from_graph(self) -> int:
        """
        Add nodes from the knowledge graph to the vector store.

        Returns:
            Number of nodes added
        """
        if self.knowledge_graph is None or self.vector_store is None:
            return 0

        count = 0

        # Add notes
        for note in self.knowledge_graph.data.get("notes", []):
            if "content" in note and note["content"].strip():
                self.vector_store.add_text(
                    text=note["content"],
                    metadata={
                        "type": "note",
                        "id": note["id"],
                        "title": note.get("title", ""),
                        "tags": note.get("tags", [])
                    },
                    id=f"note_{note['id']}"
                )
                count += 1

        # Add tasks
        for task in self.knowledge_graph.data.get("tasks", []):
            if "description" in task and task["description"].strip():
                self.vector_store.add_text(
                    text=task["description"],
                    metadata={
                        "type": "task",
                        "id": task["id"],
                        "title": task.get("title", ""),
                        "tags": task.get("tags", []),
                        "status": task.get("status", "")
                    },
                    id=f"task_{task['id']}"
                )
                count += 1

        return count
