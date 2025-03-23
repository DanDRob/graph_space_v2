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
        knowledge_graph: Optional[Any] = None,
        max_workers: int = 4,
        chunk_size: int = 500,
        storage_dir: Optional[str] = None
    ):
        self.llm_service = llm_service
        self.embedding_service = embedding_service
        self.knowledge_graph = knowledge_graph
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

    def process_single_file(self, file_path: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process a single document file.

        Args:
            file_path: Path to the file to process
            metadata: Optional metadata to associate with the document

        Returns:
            Dictionary with processing results
        """
        try:
            print(f"Processing document: {file_path}")
            # Extract text and metadata using appropriate extractor
            doc_info = ExtractorFactory.extract_from_file(file_path)

            # Add additional metadata if provided
            if metadata:
                doc_info.metadata.update(metadata)

            # Use LLM to enhance document metadata if available
            summary = ""
            topics = []
            entities = {}

            if self.llm_service:
                # Generate a summary
                print(f"Calling LLM to generate_summary...")
                summary = self.llm_service.generate_summary(doc_info.content)
                print(f"Summary generated: {summary[:50]}...")

                # Extract topics/tags
                print(f"Calling LLM to extract_tags...")
                topics = self.llm_service.extract_tags(doc_info.content)
                print(f"Tags extracted: {topics}")

                # Extract named entities
                print(f"Calling LLM to extract_entities...")
                entities = self.llm_service.extract_entities(doc_info.content)
                print(
                    f"Entities extracted: {list(entities.keys()) if entities else 'None'}")

            # Convert topics to list if it's not already
            if not isinstance(topics, list):
                if isinstance(topics, str):
                    topics = [t.strip() for t in topics.split(",")]
                else:
                    topics = []

            # Ensure we have at least some basic tags if none were extracted
            if not topics and doc_info.title:
                # Split title into words and use as basic tags
                words = doc_info.title.lower().split()
                # Use up to 3 longer words
                topics = [w for w in words if len(w) > 3][:3]
                print(
                    f"No topics found, using basic tags from title: {topics}")

            # Create embeddings if embedding service is available
            chunk_embeddings = []
            if self.embedding_service and doc_info.content:
                # Process content in chunks if it's too large
                chunks = self._chunk_text(doc_info.content, self.chunk_size)

                for i, chunk in enumerate(chunks):
                    embedding = self.embedding_service.embed_text(chunk)
                    chunk_id = f"{os.path.basename(file_path)}_chunk_{i}"

                    # Store the embedding with metadata including tags
                    self.embedding_service.store_embedding(
                        chunk_id,
                        embedding,
                        {
                            "type": "document_chunk",
                            "document_id": os.path.basename(file_path),
                            "chunk_index": i,
                            "content": chunk,
                            "title": doc_info.title,
                            "tags": topics  # Include tags with chunk for better retrieval
                        }
                    )

                    chunk_embeddings.append({
                        "chunk_id": chunk_id,
                        "chunk_index": i
                    })
                print(f"Created {len(chunks)} chunk embeddings for document")

            # Store processing results
            result = {
                "id": os.path.basename(file_path),
                "file_path": file_path,
                "file_name": os.path.basename(file_path),
                "title": doc_info.title,
                "content": doc_info.content,
                "content_length": len(doc_info.content),
                "metadata": doc_info.metadata,
                "file_type": doc_info.file_type,
                "summary": summary,
                "topics": topics,
                "tags": topics,  # Duplicate topics as tags for consistency
                "entities": entities,
                "processed_at": datetime.now().isoformat(),
                "chunks": len(chunk_embeddings),
                "chunk_embeddings": chunk_embeddings,
                "type": "document"  # Add type for consistency with other entities
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
                    "topics": topics,
                    "tags": topics  # Include tags here too
                }
                self._save_metadata()

            # Add document to knowledge graph if available
            if self.knowledge_graph:
                print(
                    f"Adding document to knowledge graph: {result['id']} with tags: {topics}")
                doc_id = self.knowledge_graph.add_document(result)
                print(f"Document added to knowledge graph with ID: {doc_id}")

                # Force graph rebuild to ensure connections are made
                print("Rebuilding knowledge graph connections...")
                self.knowledge_graph.build_graph()

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

    def process_document(self, content: bytes, filename: str, mime_type: str = None) -> str:
        """
        Process a document from binary content (e.g., content downloaded from Google Drive).

        Args:
            content: Binary content of the document
            filename: Name of the file
            mime_type: MIME type of the file

        Returns:
            Document ID (usually the filename)
        """
        # Create a temporary file to process
        import tempfile
        import uuid

        try:
            # Create a unique temporary file with the correct extension
            file_extension = os.path.splitext(filename)[1]
            if not file_extension and mime_type:
                # Try to get extension from mime type
                if 'pdf' in mime_type:
                    file_extension = '.pdf'
                elif 'word' in mime_type or 'docx' in mime_type:
                    file_extension = '.docx'
                elif 'excel' in mime_type or 'xlsx' in mime_type:
                    file_extension = '.xlsx'
                elif 'text' in mime_type:
                    file_extension = '.txt'
                elif 'html' in mime_type:
                    file_extension = '.html'
                elif 'markdown' in mime_type:
                    file_extension = '.md'

            # Generate a unique filename with the correct extension
            temp_filename = f"{uuid.uuid4().hex}{file_extension}"
            temp_filepath = os.path.join(self.storage_dir, temp_filename)

            print(
                f"Saving temporary file to {temp_filepath} (type: {mime_type})")

            # Write content to temporary file
            with open(temp_filepath, 'wb') as f:
                f.write(content)

            # Process the temporary file using the existing method
            metadata = {
                "source": "google_drive",
                "original_filename": filename,
                "mime_type": mime_type,
                "imported_at": datetime.now().isoformat()
            }

            result = self.process_single_file(temp_filepath, metadata)

            if result.get('error'):
                print(f"Error processing document: {result['error']}")
                raise ValueError(
                    f"Failed to process document: {result['error']}")

            document_id = result.get('id')
            if not document_id:
                print("Document processed but no ID returned")
                document_id = os.path.basename(temp_filepath)

            print(f"Document processed successfully, ID: {document_id}")
            return document_id

        except Exception as e:
            print(f"Error processing document content: {str(e)}")
            traceback.print_exc()
            raise ValueError(f"Failed to process document content: {str(e)}")
