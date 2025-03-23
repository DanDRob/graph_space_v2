from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, BinaryIO
import os
import re


class DocumentInfo:
    def __init__(
        self,
        title: str = "",
        content: str = "",
        metadata: Dict[str, Any] = None,
        file_path: str = "",
        file_type: str = "",
        pages: int = 0
    ):
        self.title = title
        self.content = content
        self.metadata = metadata or {}
        self.file_path = file_path
        self.file_type = file_type
        self.pages = pages

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "content": self.content,
            "metadata": self.metadata,
            "file_path": self.file_path,
            "file_type": self.file_type,
            "pages": self.pages
        }


class DocumentExtractor(ABC):
    @abstractmethod
    def extract(self, file_obj: BinaryIO, file_path: str) -> DocumentInfo:
        """
        Extract text and metadata from a document.

        Args:
            file_obj: File-like object containing the document data
            file_path: Path to the original file

        Returns:
            DocumentInfo object containing extracted information
        """
        pass

    @staticmethod
    def clean_text(text: str) -> str:
        """Clean up extracted text"""
        # Replace multiple whitespaces with a single space
        text = re.sub(r'\s+', ' ', text)
        # Replace multiple newlines with a single newline
        text = re.sub(r'\n+', '\n', text)
        # Remove leading and trailing whitespace
        return text.strip()

    @staticmethod
    def extract_title_from_text(text: str, default_title: str = "Untitled Document") -> str:
        """Try to extract a title from the text content"""
        # Try to find the first non-empty line
        if not text:
            return default_title

        lines = text.split('\n')
        for line in lines:
            line = line.strip()
            if line and len(line) < 100:  # Assume title is not too long
                return line

        return default_title


class ExtractorFactory:
    @staticmethod
    def get_extractor(file_extension: str) -> DocumentExtractor:
        """Get the appropriate extractor for a file extension"""
        from graph_space_v2.integrations.document.extractors.text_extractor import TextExtractor
        from graph_space_v2.integrations.document.extractors.pdf_extractor import PDFExtractor
        from graph_space_v2.integrations.document.extractors.docx_extractor import DocxExtractor

        file_extension = file_extension.lower()

        if file_extension in ['.txt', '.md', '.html', '.htm']:
            return TextExtractor()
        elif file_extension == '.pdf':
            return PDFExtractor()
        elif file_extension in ['.docx', '.doc']:
            return DocxExtractor()
        else:
            # Default to text extractor
            return TextExtractor()

    @staticmethod
    def extract_from_file(file_path: str) -> DocumentInfo:
        """Extract information from a file on disk"""
        # Get file extension
        _, file_extension = os.path.splitext(file_path)

        # Get appropriate extractor
        extractor = ExtractorFactory.get_extractor(file_extension)

        # Extract content
        with open(file_path, 'rb') as file_obj:
            return extractor.extract(file_obj, file_path)

    @staticmethod
    def extract_from_bytes(file_bytes: bytes, file_name: str) -> DocumentInfo:
        """Extract information from bytes"""
        import io

        # Get file extension
        _, file_extension = os.path.splitext(file_name)

        # Get appropriate extractor
        extractor = ExtractorFactory.get_extractor(file_extension)

        # Extract content
        file_obj = io.BytesIO(file_bytes)
        return extractor.extract(file_obj, file_name)
