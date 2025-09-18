"""Pytest fixtures and stubs for GraphSpace v2 tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import types

import numpy as np

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # pragma: no branch - executes once during import
    sys.path.insert(0, str(ROOT))

if "dotenv" not in sys.modules:  # pragma: no branch - ensures optional dependency
    dotenv_module = types.ModuleType("dotenv")
    dotenv_module.load_dotenv = lambda *args, **kwargs: None
    sys.modules["dotenv"] = dotenv_module

if "torch" not in sys.modules:  # pragma: no branch - avoid heavy dependency
    torch_module = types.ModuleType("torch")

    class _Cuda:
        @staticmethod
        def is_available() -> bool:  # pragma: no cover - simple stub
            return False

    torch_module.cuda = _Cuda()
    sys.modules["torch"] = torch_module

if "sentence_transformers" not in sys.modules:  # pragma: no branch
    st_module = types.ModuleType("sentence_transformers")

    class _SentenceTransformer:
        def __init__(self, *args, **kwargs):  # pragma: no cover - trivial stub
            pass

        def encode(self, texts, convert_to_tensor=False):  # pragma: no cover
            if isinstance(texts, list):
                return np.zeros((len(texts), 1), dtype=np.float32)
            return np.zeros((1,), dtype=np.float32)

    st_module.SentenceTransformer = _SentenceTransformer
    sys.modules["sentence_transformers"] = st_module

if "faiss" not in sys.modules:  # pragma: no branch
    faiss_module = types.ModuleType("faiss")

    class _IndexFlatL2:
        def __init__(self, dimension: int):  # pragma: no cover
            self.dimension = dimension

        def reset(self) -> None:  # pragma: no cover
            pass

        def add_with_ids(self, embeddings, ids) -> None:  # pragma: no cover
            pass

        def search(self, queries, k):  # pragma: no cover
            return np.zeros((len(queries), k)), np.zeros((len(queries), k))

    class _IndexIDMap:
        def __init__(self, index):  # pragma: no cover
            self.index = index

    def normalize_L2(vectors):  # pragma: no cover
        return vectors

    faiss_module.IndexFlatL2 = _IndexFlatL2
    faiss_module.IndexIDMap = _IndexIDMap
    faiss_module.normalize_L2 = normalize_L2
    sys.modules["faiss"] = faiss_module

    contrib_module = types.ModuleType("faiss.contrib")
    torch_utils_module = types.ModuleType("faiss.contrib.torch_utils")
    torch_utils_module.using_gpu = False
    sys.modules["faiss.contrib"] = contrib_module
    sys.modules["faiss.contrib.torch_utils"] = torch_utils_module

from graph_space_v2.core.graph.knowledge_graph import KnowledgeGraph


@pytest.fixture()
def data_file(tmp_path: Path) -> Path:
    """Create an isolated user data file for a test case."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    data_path = data_dir / "user_data.json"
    data = {"notes": [], "tasks": [], "contacts": [], "documents": []}
    data_path.write_text(json.dumps(data))
    return data_path


@pytest.fixture()
def knowledge_graph(data_file: Path) -> KnowledgeGraph:
    """Provide a fresh knowledge graph backed by a temporary file."""
    return KnowledgeGraph(str(data_file))


class DummyEmbeddingService:
    """In-memory embedding service used to isolate tests from heavy models."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.stored_embeddings: Dict[str, Dict[str, Any]] = {}
        self.updated_embeddings: Dict[str, Any] = {}
        self.deleted_embeddings: List[str] = []
        self.semantic_matches: List[Dict[str, Any]] = []
        self.trained_graph_nodes: List[str] | None = None

    def embed_text(self, text: str) -> str:
        return f"embedding:{text}"

    def embed_texts(self, texts: List[str]) -> List[str]:
        return [self.embed_text(text) for text in texts]

    def store_embedding(self, item_id: str, embedding: Any, metadata: Dict[str, Any] | None = None) -> None:
        self.stored_embeddings[item_id] = {
            "embedding": embedding,
            "metadata": metadata or {},
        }

    def update_embedding(self, item_id: str, embedding: Any, metadata: Dict[str, Any] | None = None) -> bool:
        self.updated_embeddings[item_id] = {
            "embedding": embedding,
            "metadata": metadata or {},
        }
        return True

    def delete_embedding(self, item_id: str) -> bool:
        self.deleted_embeddings.append(item_id)
        return True

    def search_embeddings(self, query_embedding: Any, filter_metadata: Dict[str, Any] | None = None, limit: int = 5) -> List[Dict[str, Any]]:
        return self.semantic_matches[:limit]

    def search(self, query_embedding: Any, max_results: int, filter_by: Dict[str, Any] | None = None) -> Dict[str, Any]:
        return {"matches": self.semantic_matches[:max_results]}

    def train_on_graph(self, graph) -> None:  # pragma: no cover - used for integration wiring
        self.trained_graph_nodes = list(graph.nodes)


class DummyLLMService:
    """Simple LLM stub that records invocations for assertions."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.generated_titles: List[str] = []
        self.tag_inputs: List[str] = []

    def generate_title(self, text: str) -> str:
        self.generated_titles.append(text)
        return f"Title for {text[:10]}".strip()

    def extract_tags(self, text: str) -> List[str]:
        self.tag_inputs.append(text)
        return ["llm-tag", "auto"]

    def generate_summary(self, text: str) -> str:  # pragma: no cover - document processing stub
        return text[:50]

    def extract_entities(self, text: str) -> Dict[str, Any]:  # pragma: no cover
        return {"entities": []}

    def generate_text(self, *args: Any, **kwargs: Any) -> str:  # pragma: no cover
        return "generated"

    def generate_answer(self, *args: Any, **kwargs: Any) -> str:  # pragma: no cover
        return "answer"


@pytest.fixture()
def dummy_embedding_service() -> DummyEmbeddingService:
    """Fixture exposing a fresh embedding stub per test."""
    return DummyEmbeddingService()


@pytest.fixture()
def dummy_llm_service() -> DummyLLMService:
    """Fixture exposing a fresh LLM stub per test."""
    return DummyLLMService()
