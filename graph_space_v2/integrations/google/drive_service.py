from typing import Dict, List, Any, Optional, BinaryIO
import os
import io
import tempfile
from datetime import datetime
import json

# Import MediaIoBaseDownload directly for downloading files
try:
    from googleapiclient.http import MediaIoBaseDownload
except ImportError:
    pass

from graph_space_v2.integrations.document.document_processor import DocumentProcessor
from graph_space_v2.integrations.google.auth import GoogleAuth, GOOGLE_API_AVAILABLE
from graph_space_v2.utils.helpers.path_utils import ensure_dir_exists, get_data_dir


class GoogleDriveService:
    def __init__(
        self,
        credentials_file: Optional[str] = None,
        token_file: Optional[str] = None,
        document_processor: Optional[DocumentProcessor] = None,
        scopes: Optional[List[str]] = None
    ):
        if not GOOGLE_API_AVAILABLE:
            raise ImportError(
                "Google API client libraries are required but not installed. "
                "Install them with: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib"
            )

        self.credentials_file = credentials_file
        self.token_file = token_file or os.path.join(
            get_data_dir(), "credentials", "token.json")
        ensure_dir_exists(os.path.dirname(self.token_file))

        self.document_processor = document_processor
        self.scopes = scopes or [
            'https://www.googleapis.com/auth/drive.readonly']

        # Initialize Google Auth
        self.auth = GoogleAuth(
            credentials_file=credentials_file,
            token_file=self.token_file,
            scopes=self.scopes
        )

        self.creds = None
        self.service = None

        # Controls whether to authenticate immediately or defer
        self.auth_required = False
        self.authenticated = False

        # Only authenticate immediately if auth is not deferred
        if not self.auth_required:
            self._authenticate()

    def _authenticate(self) -> None:
        """Authenticate with Google Drive API"""
        try:
            # Get credentials from the auth manager
            self.creds = self.auth.get_credentials()

            if not self.creds:
                if self.auth_required:
                    # Just mark as not authenticated, don't raise exception
                    self.authenticated = False
                    return
                else:
                    raise ValueError("No valid credentials found")

            # Build the service
            from googleapiclient.discovery import build
            self.service = build('drive', 'v3', credentials=self.creds)
            self.authenticated = True
        except Exception as e:
            self.authenticated = False
            if not self.auth_required:
                raise ValueError(
                    f"Failed to authenticate with Google Drive: {e}")
            print(f"Warning: Failed to authenticate with Google Drive: {e}")

    def _ensure_authenticated(self) -> bool:
        """Ensure service is authenticated before making API calls"""
        if not self.authenticated or not self.service:
            self._authenticate()
        return self.authenticated

    def list_files(
        self,
        folder_id: Optional[str] = None,
        mime_types: Optional[List[str]] = None,
        query: Optional[str] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        List files in Google Drive, optionally filtered by folder, type or query.

        Args:
            folder_id: ID of folder to list (or None for root/all files)
            mime_types: List of MIME types to filter by
            query: Additional search query
            max_results: Maximum number of results to return

        Returns:
            List of file metadata
        """
        if not self._ensure_authenticated():
            raise ValueError("Not authenticated with Google Drive")

        # Build query string
        query_parts = []

        # Add folder constraint if specified
        if folder_id:
            query_parts.append(f"'{folder_id}' in parents")

        # Add mime type filter if specified
        if mime_types:
            mime_type_conditions = [
                f"mimeType='{mime_type}'" for mime_type in mime_types]
            query_parts.append("(" + " or ".join(mime_type_conditions) + ")")

        # Add custom query if specified
        if query:
            query_parts.append(query)

        # Combine all query parts
        query_string = " and ".join(query_parts) if query_parts else None

        # Get the list of files
        results = []
        page_token = None

        while True:
            # Call the Drive API
            response = self.service.files().list(
                q=query_string,
                pageSize=min(max_results - len(results),
                             100),  # Max 100 per page
                fields="nextPageToken, files(id, name, mimeType, createdTime, modifiedTime, size, webViewLink, parents)",
                pageToken=page_token
            ).execute()

            # Add files to results
            files = response.get('files', [])
            results.extend(files)

            # Check if we have more pages and if we need more results
            page_token = response.get('nextPageToken')
            if not page_token or len(results) >= max_results:
                break

        return results[:max_results]

    def download_file(self, file_id: str) -> bytes:
        """
        Download a file from Google Drive.

        Args:
            file_id: ID of the file to download

        Returns:
            The file content as bytes
        """
        if not self._ensure_authenticated():
            raise ValueError("Not authenticated with Google Drive")

        # Get the file metadata
        file_metadata = self.service.files().get(fileId=file_id).execute()

        # For Google Docs/Sheets/Slides, we need to export them
        if file_metadata['mimeType'] in [
            'application/vnd.google-apps.document',
            'application/vnd.google-apps.spreadsheet',
            'application/vnd.google-apps.presentation'
        ]:
            return self._export_google_doc(file_id, file_metadata['mimeType'])

        # For regular files, we can download directly
        request = self.service.files().get_media(fileId=file_id)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        return file_content.getvalue()

    def _export_google_doc(self, file_id: str, mime_type: str) -> bytes:
        """
        Export a Google Doc/Sheet/Slide to a standard format.

        Args:
            file_id: ID of the file to export
            mime_type: MIME type of the file

        Returns:
            The file content as bytes
        """
        # Choose export format based on file type
        export_mime_type = 'application/pdf'  # Default to PDF
        if mime_type == 'application/vnd.google-apps.document':
            export_mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'  # DOCX
        elif mime_type == 'application/vnd.google-apps.spreadsheet':
            export_mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'  # XLSX
        elif mime_type == 'application/vnd.google-apps.presentation':
            export_mime_type = 'application/vnd.openxmlformats-officedocument.presentationml.presentation'  # PPTX

        # Export the file
        request = self.service.files().export_media(
            fileId=file_id, mimeType=export_mime_type)
        file_content = io.BytesIO()
        downloader = MediaIoBaseDownload(file_content, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()

        return file_content.getvalue()

    def import_document(self, file_id: str) -> str:
        """
        Import a document from Google Drive into the knowledge graph.

        Args:
            file_id: ID of the file to import

        Returns:
            ID of the imported document
        """
        if not self._ensure_authenticated():
            raise ValueError("Not authenticated with Google Drive")

        if not self.document_processor:
            raise ValueError("Document processor not initialized")

        # Get file metadata
        file_metadata = self.service.files().get(
            fileId=file_id, fields="name,mimeType").execute()
        file_name = file_metadata.get('name', 'untitled')
        mime_type = file_metadata.get('mimeType', 'application/octet-stream')

        # Download file content
        content = self.download_file(file_id)

        # Process the document
        document_id = self.document_processor.process_document(
            content=content,
            filename=file_name,
            mime_type=mime_type
        )

        return document_id

    def set_credentials(self, credentials):
        """
        Set credentials for use with web-based authentication flow.

        Args:
            credentials: OAuth2 credentials from web auth flow
        """
        self.creds = credentials
        # Rebuild the service with the new credentials
        from googleapiclient.discovery import build
        self.service = build('drive', 'v3', credentials=self.creds)
        self.authenticated = True

    def process_file(self, file_id: str) -> Dict[str, Any]:
        """
        Download and process a single file from Google Drive.

        Args:
            file_id: ID of the file to process

        Returns:
            Processing results
        """
        if not self.document_processor:
            raise ValueError(
                "document_processor is required for processing files")

        try:
            # Get file metadata
            file_metadata = self.service.files().get(fileId=file_id).execute()

            # Download file
            file_bytes = self.download_file(file_id)

            # Save to temporary file for processing
            with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file_metadata['name']}") as temp:
                temp.write(file_bytes)
                temp_path = temp.name

            # Process the file
            result = self.document_processor.process_single_file(temp_path)

            # Add Google Drive metadata
            result["google_drive"] = {
                "file_id": file_id,
                "name": file_metadata['name'],
                "mime_type": file_metadata['mimeType'],
                "web_view_link": file_metadata.get('webViewLink', ''),
                "created_time": file_metadata.get('createdTime', ''),
                "modified_time": file_metadata.get('modifiedTime', '')
            }

            # Clean up temporary file
            try:
                os.unlink(temp_path)
            except:
                pass

            return result

        except Exception as e:
            return {
                "file_id": file_id,
                "error": str(e),
                "success": False,
                "processed_at": datetime.now().isoformat()
            }

    def process_folder(self, folder_id: str) -> Dict[str, Any]:
        """
        Process all files in a Google Drive folder.

        Args:
            folder_id: ID of the folder to process

        Returns:
            Processing results for all files
        """
        # List all files in the folder
        files = self.list_files(
            folder_id=folder_id,
            # Filter for supported document types
            mime_types=[
                'application/pdf',
                'text/plain',
                'text/markdown',
                'text/html',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.google-apps.document',
                'application/vnd.google-apps.spreadsheet'
            ]
        )

        if not files:
            return {
                "folder_id": folder_id,
                "files_processed": 0,
                "results": []
            }

        # Process each file
        results = []
        for file in files:
            result = self.process_file(file['id'])
            results.append(result)

        return {
            "folder_id": folder_id,
            "files_processed": len(results),
            "results": results
        }
