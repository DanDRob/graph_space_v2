from typing import Dict, List, Any, BinaryIO
import os

from graph_space_v2.integrations.document.extractors.base import DocumentExtractor, DocumentInfo


class TextExtractor(DocumentExtractor):
    def extract(self, file_obj: BinaryIO, file_path: str) -> DocumentInfo:
        """Extract text and metadata from a text-based document (txt, md, html)"""
        # Extract filename from path as fallback title
        filename = os.path.basename(file_path)
        base_filename = os.path.splitext(filename)[0]
        file_extension = os.path.splitext(filename)[1].lower()

        try:
            # Read the content, attempting different encodings if needed
            content = None
            encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']

            # Get the position at the start of the file
            file_obj.seek(0)
            file_bytes = file_obj.read()

            # Try different encodings
            for encoding in encodings:
                try:
                    content = file_bytes.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue

            # If all encodings failed, use utf-8 with errors='replace'
            if content is None:
                content = file_bytes.decode('utf-8', errors='replace')

            # Clean the extracted text
            content = self.clean_text(content)

            # Extract title from the first line or use filename
            title = self.extract_title_from_text(content, base_filename)

            # Handle specific file types
            file_type = "text"
            if file_extension == '.md':
                file_type = "markdown"
            elif file_extension in ['.html', '.htm']:
                file_type = "html"

                # For HTML, try to extract title from <title> tag
                import re
                title_match = re.search(
                    r'<title>(.*?)</title>', content, re.IGNORECASE | re.DOTALL)
                if title_match:
                    title = title_match.group(1).strip()

            # Estimate pages (approximately 3000 characters per page)
            estimated_pages = max(1, len(content) // 3000)

            return DocumentInfo(
                title=title,
                content=content,
                metadata={
                    "filename": filename,
                    "extension": file_extension
                },
                file_path=file_path,
                file_type=file_type,
                pages=estimated_pages
            )

        except Exception as e:
            # Handle extraction errors
            return DocumentInfo(
                title=base_filename,
                content=f"Error extracting text content: {str(e)}",
                metadata={"error": str(e)},
                file_path=file_path,
                file_type="text",
                pages=0
            )
