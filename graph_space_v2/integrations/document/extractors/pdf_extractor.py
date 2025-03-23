from typing import Dict, List, Any, BinaryIO
import os

from graph_space_v2.integrations.document.extractors.base import DocumentExtractor, DocumentInfo

# Use PyPDF2 for PDF processing
try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False


class PDFExtractor(DocumentExtractor):
    def extract(self, file_obj: BinaryIO, file_path: str) -> DocumentInfo:
        """Extract text and metadata from a PDF document"""
        if not PYPDF2_AVAILABLE:
            raise ImportError(
                "PyPDF2 is required for PDF extraction but is not installed.")

        # Extract filename from path as fallback title
        filename = os.path.basename(file_path)
        base_filename = os.path.splitext(filename)[0]

        try:
            # Create a PDF reader object
            pdf_reader = PyPDF2.PdfReader(file_obj)

            # Extract metadata
            metadata = {}
            if pdf_reader.metadata:
                for key, value in pdf_reader.metadata.items():
                    if key.startswith('/'):
                        clean_key = key[1:]  # Remove leading slash
                        metadata[clean_key] = value
                    else:
                        metadata[key] = value

            # Extract title from metadata or use filename
            title = metadata.get('Title', base_filename)

            # Extract text from all pages
            content = ""
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    content += page_text + "\n\n"

            # Clean the extracted text
            content = self.clean_text(content)

            # If title is empty or None, try to extract it from content
            if not title:
                title = self.extract_title_from_text(content, base_filename)

            return DocumentInfo(
                title=title,
                content=content,
                metadata=metadata,
                file_path=file_path,
                file_type="pdf",
                pages=len(pdf_reader.pages)
            )

        except Exception as e:
            # Handle extraction errors
            return DocumentInfo(
                title=base_filename,
                content=f"Error extracting PDF content: {str(e)}",
                metadata={"error": str(e)},
                file_path=file_path,
                file_type="pdf",
                pages=0
            )
