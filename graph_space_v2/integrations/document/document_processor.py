from typing import Dict, List, Any, Optional, Union, Callable
import os
import concurrent.futures
import threading
from datetime import datetime
import traceback
import json

from graph_space_v2.integrations.document.extractors import ExtractorFactory, DocumentInfo
from graph_space_v2.ai.llm.llm_service import LLMService
from graph_space_v2.ai.embedding.embedding_service import EmbeddingService
from graph_space_v2.utils.helpers.path_utils import ensure_dir_exists


class DocumentProcessor:
    def __init__(
        self,
        llm_service: Optional[LLMService] = None,
        embedding_service: Optional[EmbeddingService] = None,
        max_workers: int = 4,
        chunk_size: int = 500,
        storage_dir: Optional[str] = None
    ):
        self.llm_service = llm_service
        self.embedding_service = embedding_service
        self.max_workers = max_workers
        self.chunk_size = chunk_size

        # Use the storage directory from the path utils or fall back to default
        from graph_space_v2.utils.helpers.path_utils import get_data_dir
        self.storage_dir = storage_dir or os.path.join(
            get_data_dir(), "documents")

        # Create storage directory if it doesn't exist
        ensure_dir_exists(self.storage_dir)

        # Thread safety lock
        self.lock = threading.Lock()

        # Metadata for processed files
        self.processed_files_metadata = {}
        self._load_metadata()

    def _load_metadata(self):
        """Load metadata of previously processed files"""
        metadata_path = os.path.join(self.storage_dir, "metadata.json")
        if os.path.exists(metadata_path):
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    self.processed_files_metadata = json.load(f)
            except Exception as e:
                print(f"Error loading document metadata: {e}")

    def _save_metadata(self):
        """Save metadata of processed files"""
        metadata_path = os.path.join(self.storage_dir, "metadata.json")
        try:
            with open(metadata_path, 'w', encoding='utf-8') as f:
                json.dump(self.processed_files_metadata, f, indent=2)
        except Exception as e:
            print(f"Error saving document metadata: {e}")

    def process_single_file(self, file_path: str) -> Dict[str, Any]:
        """
        Process a single document file.

        Args:
            file_path: Path to the file to process

        Returns:
            Dictionary with processing results
        """
        try:
            # Extract text and metadata using appropriate extractor
            doc_info = ExtractorFactory.extract_from_file(file_path)

            # Use LLM to enhance document metadata if available
            if self.llm_service:
                # Generate a summary
                summary = self.llm_service.generate_summary(doc_info.content)

                # Extract topics/tags
                topics = self.llm_service.extract_tags(doc_info.content)

                # Extract named entities
                entities = self.llm_service.extract_entities(doc_info.content)
            else:
                summary = ""
                topics = []
                entities = {}

            # Create embeddings if embedding service is available
            if self.embedding_service and doc_info.content:
                # Process content in chunks if it's too large
                chunks = self._chunk_text(doc_info.content, self.chunk_size)
                chunk_embeddings = []

                for i, chunk in enumerate(chunks):
                    embedding = self.embedding_service.embed_text(chunk)
                    chunk_id = f"{os.path.basename(file_path)}_chunk_{i}"

                    # Store the embedding
                    self.embedding_service.store_embedding(
                        chunk_id,
                        embedding,
                        {
                            "type": "document_chunk",
                            "document_id": os.path.basename(file_path),
                            "chunk_index": i,
                            "content": chunk,
                            "title": doc_info.title
                        }
                    )

                    chunk_embeddings.append({
                        "chunk_id": chunk_id,
                        "chunk_index": i
                    })
            else:
                chunk_embeddings = []

            # Store processing results
            result = {
                "file_path": file_path,
                "file_name": os.path.basename(file_path),
                "title": doc_info.title,
                "content_length": len(doc_info.content),
                "metadata": doc_info.metadata,
                "file_type": doc_info.file_type,
                "summary": summary,
                "topics": topics,
                "entities": entities,
                "processed_at": datetime.now().isoformat(),
                "chunks": len(chunk_embeddings),
                "chunk_embeddings": chunk_embeddings
            }

            # Update metadata
            with self.lock:
                self.processed_files_metadata[os.path.basename(file_path)] = {
                    "title": doc_info.title,
                    "file_path": file_path,
                    "file_type": doc_info.file_type,
                    "processed_at": result["processed_at"],
                    "content_length": len(doc_info.content),
                    "chunks": len(chunk_embeddings),
                    "topics": topics
                }
                self._save_metadata()

            return result

        except Exception as e:
            # Log the error and return error information
            print(f"Error processing file {file_path}: {e}")
            traceback.print_exc()

            return {
                "file_path": file_path,
                "error": str(e),
                "processed_at": datetime.now().isoformat(),
                "success": False
            }

    def process_directory(self, directory_path: str) -> Dict[str, Any]:
        """
        Process all supported documents in a directory.

        Args:
            directory_path: Path to directory containing documents

        Returns:
            Dictionary with processing results for all files
        """
        # Collect all supported files in the directory
        supported_files = []

        for root, _, files in os.walk(directory_path):
            for file in files:
                file_path = os.path.join(root, file)
                if self._is_supported_file(file_path):
                    supported_files.append(file_path)

        if not supported_files:
            return {
                "directory": directory_path,
                "files_processed": 0,
                "results": []
            }

        # Process files in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = list(executor.map(
                self.process_single_file, supported_files))

        return {
            "directory": directory_path,
            "files_processed": len(results),
            "results": results
        }

    def _is_supported_file(self, file_path: str) -> bool:
        """Check if a file is supported for processing"""
        # Check if it's a file
        if not os.path.isfile(file_path):
            return False

        # Get the file extension
        _, ext = os.path.splitext(file_path)
        ext = ext.lower()

        # Check supported extensions
        return ext in ['.txt', '.pdf', '.docx', '.md', '.html']

    def get_processed_files(self) -> List[Dict[str, Any]]:
        """Get information about all processed files"""
        return list(self.processed_files_metadata.values())

    def get_document_by_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a processed document by ID (filename)"""
        return self.processed_files_metadata.get(document_id)

    def search_documents(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search for documents relevant to a query using embeddings.

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of relevant document chunks with similarity scores
        """
        if not self.embedding_service:
            return []

        try:
            # Embed the query
            query_embedding = self.embedding_service.embed_text(query)

            # Search for similar document chunks
            results = self.embedding_service.search_embeddings(
                query_embedding,
                filter_metadata={"type": "document_chunk"},
                limit=max_results
            )

            return results
        except Exception as e:
            print(f"Error searching documents: {e}")
            return []

    def _chunk_text(self, text: str, chunk_size: int = 500) -> List[str]:
        """Split text into chunks of approximately equal size"""
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        current_chunk = ""

        # Split by paragraphs first
        paragraphs = text.split('\n\n')

        for para in paragraphs:
            # If adding this paragraph exceeds chunk size and we already have content,
            # store the current chunk and start a new one
            if len(current_chunk) + len(para) > chunk_size and current_chunk:
                chunks.append(current_chunk)
                current_chunk = para
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para

        # Add the last chunk if it has content
        if current_chunk:
            chunks.append(current_chunk)

        return chunks
