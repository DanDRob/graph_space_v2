import pytest
from unittest.mock import MagicMock, patch, mock_open
import os # Ensure os is imported for os.path.basename
from graph_space_v2.integrations.document.document_processor import DocumentProcessor
from graph_space_v2.integrations.document.extractors.base import DocumentInfo

@pytest.fixture
def mock_kg():
    kg = MagicMock()
    def mock_add_document(doc_dict):
        return doc_dict.get("id", "default_doc_id")
    kg.add_document.side_effect = mock_add_document
    return kg

@pytest.fixture
def mock_embedding_service():
    mock = MagicMock()
    mock.model = MagicMock()
    mock.embed_text.return_value = [0.1, 0.2, 0.3]
    mock.embed_texts.return_value = [[0.1, 0.2, 0.3]]
    return mock

@pytest.fixture
def mock_llm_service():
    mock = MagicMock()
    mock.generate_summary.return_value = "Test summary."
    mock.extract_tags.return_value = ["tag1", "tag2"]
    mock.extract_entities.return_value = {"PERSON": ["Test Person"]}
    mock.summarize_text_for_storage.return_value = "KG storage summary."
    return mock

@pytest.fixture
def document_processor(mock_kg, mock_embedding_service, mock_llm_service):
    return DocumentProcessor(
        llm_service=mock_llm_service,
        embedding_service=mock_embedding_service,
        knowledge_graph=mock_kg
    )

@patch('graph_space_v2.integrations.document.document_processor.ExtractorFactory.extract_from_file')
def test_process_single_file_text(mock_extract_from_file, document_processor, mock_llm_service, mock_embedding_service, mock_kg):
    file_path = "dummy/test.txt"
    mock_file_content = "This is a test text file."

    extracted_doc_info = DocumentInfo(title="test.txt", content=mock_file_content, file_type="txt", file_path=file_path)
    mock_extract_from_file.return_value = extracted_doc_info

    result_dict = document_processor.process_single_file(file_path)

    mock_extract_from_file.assert_called_with(file_path)
    assert result_dict is not None
    assert result_dict['content'] == mock_file_content
    assert result_dict['title'] == "test.txt"
    assert result_dict['summary'] == "Test summary."
    assert "tag1" in result_dict['tags']

    mock_embedding_service.embed_text.assert_called()
    mock_embedding_service.store_embedding.assert_called()

    mock_kg.add_document.assert_called_once()
    added_doc_arg = mock_kg.add_document.call_args[0][0]
    assert added_doc_arg['id'] == "test.txt"
    assert added_doc_arg['title'] == "test.txt"

@patch('graph_space_v2.integrations.document.document_processor.ExtractorFactory.extract_from_file')
def test_process_single_file_pdf(mock_extract_from_file, document_processor):
    file_path = "dummy/test.pdf"
    mock_pdf_text = "This is PDF content."

    extracted_doc_info = DocumentInfo(title="test.pdf", content=mock_pdf_text, file_type="pdf", file_path=file_path)
    mock_extract_from_file.return_value = extracted_doc_info

    result_dict = document_processor.process_single_file(file_path)

    mock_extract_from_file.assert_called_with(file_path)
    assert result_dict['content'] == mock_pdf_text
    assert result_dict['title'] == "test.pdf"

@patch('graph_space_v2.integrations.document.document_processor.ExtractorFactory.extract_from_file')
def test_process_single_file_docx(mock_extract_from_file, document_processor):
    file_path = "dummy/test.docx"
    mock_docx_text = "This is DOCX content."

    extracted_doc_info = DocumentInfo(title="test.docx", content=mock_docx_text, file_type="docx", file_path=file_path)
    mock_extract_from_file.return_value = extracted_doc_info

    result_dict = document_processor.process_single_file(file_path)

    mock_extract_from_file.assert_called_with(file_path)
    assert result_dict['content'] == mock_docx_text
    assert result_dict['title'] == "test.docx"

@patch('graph_space_v2.integrations.document.document_processor.ExtractorFactory.extract_from_file')
def test_process_unsupported_document_type_error(mock_extract_from_file, document_processor):
    file_path = "dummy/test.unsupported"
    mock_extract_from_file.side_effect = ValueError("Unsupported file type or extraction error")

    result_dict = document_processor.process_single_file(file_path)

    assert result_dict is not None
    assert result_dict['success'] is False
    assert "error" in result_dict
    assert "unsupported file type or extraction error" in result_dict['error'].lower()

@patch('graph_space_v2.integrations.document.document_processor.ExtractorFactory.extract_from_file')
def test_process_single_file_chunking_and_embedding(mock_extract_from_file, document_processor, mock_embedding_service):
    file_path = "dummy/long_doc.txt"
    document_processor.chunk_size = 15
    mock_file_content_for_chunking = "Chunk one text.\n\nChunk two text."

    extracted_doc_info = DocumentInfo(title="long_doc.txt", content=mock_file_content_for_chunking, file_type="txt", file_path=file_path)
    mock_extract_from_file.return_value = extracted_doc_info

    def embed_text_side_effect(text):
        if "Chunk one text" in text: return [1.0, 1.0]
        if "Chunk two text" in text: return [2.0, 2.0]
        return [0.0, 0.0]
    mock_embedding_service.embed_text.side_effect = embed_text_side_effect

    document_processor.process_single_file(file_path)

    assert mock_embedding_service.embed_text.call_count == 2
    mock_embedding_service.embed_text.assert_any_call("Chunk one text.")
    mock_embedding_service.embed_text.assert_any_call("Chunk two text.")

    assert mock_embedding_service.store_embedding.call_count == 2

    # Check first chunk embedding storage
    args_chunk1_call = mock_embedding_service.store_embedding.call_args_list[0][0]
    assert args_chunk1_call[0] == f"{os.path.basename(file_path)}_chunk_0"  # chunk_id (the string)
    assert args_chunk1_call[1] == [1.0, 1.0]  # embedding
    metadata_chunk1 = args_chunk1_call[2]      # metadata dict
    assert metadata_chunk1['document_id'] == os.path.basename(file_path) # Corrected key
    assert metadata_chunk1['chunk_index'] == 0 # Corrected key
    assert metadata_chunk1['content'] == "Chunk one text."

    # Check second chunk embedding storage
    args_chunk2_call = mock_embedding_service.store_embedding.call_args_list[1][0]
    assert args_chunk2_call[0] == f"{os.path.basename(file_path)}_chunk_1"
    assert args_chunk2_call[1] == [2.0, 2.0]
    metadata_chunk2 = args_chunk2_call[2]
    assert metadata_chunk2['document_id'] == os.path.basename(file_path) # Corrected key
    assert metadata_chunk2['chunk_index'] == 1 # Corrected key
    assert metadata_chunk2['content'] == "Chunk two text."

@patch('graph_space_v2.integrations.document.document_processor.ExtractorFactory.extract_from_file')
def test_process_single_file_stores_in_kg(mock_extract_from_file, document_processor, mock_kg, mock_llm_service):
    file_path = "dummy/another_doc.txt"
    mock_file_content = "Content for KG storage."
    doc_id = os.path.basename(file_path)

    extracted_doc_info = DocumentInfo(title="another_doc.txt", content=mock_file_content, file_type="txt", file_path=file_path)
    mock_extract_from_file.return_value = extracted_doc_info

    mock_llm_service.generate_summary.return_value = "KG storage summary."
    mock_llm_service.extract_tags.return_value = ["kg_tag"]

    document_processor.process_single_file(file_path)

    mock_kg.add_document.assert_called_once()
    added_doc_arg = mock_kg.add_document.call_args[0][0]
    assert added_doc_arg['id'] == doc_id
    assert added_doc_arg['title'] == "another_doc.txt"
    assert added_doc_arg['summary'] == "KG storage summary."
    assert "kg_tag" in added_doc_arg['tags']
