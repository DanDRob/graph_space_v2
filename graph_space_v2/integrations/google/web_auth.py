from typing import Dict, Any, Optional, List
import os
import json
from urllib.parse import urlencode

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from graph_space_v2.utils.helpers.path_utils import ensure_dir_exists, get_data_dir
from graph_space_v2.utils.errors.exceptions import IntegrationError


class GoogleWebAuth:
    """Google API authentication helper for web and desktop applications."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        client_type: str = "web",
        redirect_uri: Optional[str] = None,
        scopes: Optional[List[str]] = None,
        token_storage_dir: Optional[str] = None
    ):
        """
        Initialize Google Web/Desktop authentication.

        Args:
            client_id: Google client ID
            client_secret: Google client secret
            client_type: Type of client ("web" or "desktop"/"installed")
            redirect_uri: Optional OAuth redirect URI
            scopes: API scopes to request
            token_storage_dir: Directory to store tokens
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.client_type = client_type.lower()
        self.redirect_uri = redirect_uri or "http://localhost"
        self.scopes = scopes or [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/calendar.readonly"
        ]

        self.token_storage_dir = token_storage_dir or os.path.join(
            get_data_dir(), "credentials")
        ensure_dir_exists(self.token_storage_dir)

    def authenticate(self, user_id: str = "default", port: int = 0) -> Credentials:
        """
        Authenticate with Google using a local server flow.

        This method will open a browser window for the user to authenticate with Google,
        and then capture the response via a local web server.

        Args:
            user_id: User identifier for storing credentials
            port: Port to use for the local server (0 means auto-select)

        Returns:
            OAuth2 credentials
        """
        # Check if we already have valid credentials
        creds = self.get_credentials(user_id)
        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            # Refresh the credentials
            creds.refresh(Request())
            # Save the refreshed credentials
            self.save_credentials(creds, user_id)
            return creds

        # Create client config based on client type
        if self.client_type in ["desktop", "installed"]:
            client_config = {
                "installed": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": [self.redirect_uri]
                }
            }
        else:  # web (default)
            client_config = {
                "installed": {  # Using "installed" key even for web flow in InstalledAppFlow
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            }

        # Create flow and run local server to get credentials
        flow = InstalledAppFlow.from_client_config(
            client_config,
            scopes=self.scopes
        )

        # Run the local server to handle authentication
        creds = flow.run_local_server(port=port)

        # Save the credentials
        self.save_credentials(creds, user_id)

        return creds

    def save_credentials(self, creds: Credentials, user_id: str = "default") -> None:
        """
        Save credentials for a user.

        Args:
            creds: OAuth2 credentials
            user_id: User identifier
        """
        token_file = os.path.join(
            self.token_storage_dir, f"{user_id}_token.json")

        token_data = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes,
            'expiry': creds.expiry.isoformat() if creds.expiry else None
        }

        with open(token_file, 'w') as f:
            json.dump(token_data, f)

    def get_credentials(self, user_id: str = "default") -> Optional[Credentials]:
        """
        Get credentials for a user.

        Args:
            user_id: User identifier

        Returns:
            OAuth2 credentials or None if not available
        """
        token_file = os.path.join(
            self.token_storage_dir, f"{user_id}_token.json")

        if not os.path.exists(token_file):
            return None

        try:
            with open(token_file, 'r') as f:
                token_info = json.load(f)

            creds = Credentials.from_authorized_user_info(
                token_info, self.scopes)

            return creds

        except Exception as e:
            print(f"Error loading credentials: {e}")
            return None

    def revoke_token(self, user_id: str = "default") -> bool:
        """
        Revoke OAuth token for a user.

        Args:
            user_id: User identifier

        Returns:
            True if revoked successfully, False otherwise
        """
        creds = self.get_credentials(user_id)
        if not creds:
            return False

        token_file = os.path.join(
            self.token_storage_dir, f"{user_id}_token.json")

        try:
            # Try to revoke the token
            if hasattr(creds, 'revoke'):
                creds.revoke(Request())

            # Delete the token file
            if os.path.exists(token_file):
                os.remove(token_file)

            return True

        except Exception as e:
            print(f"Error revoking token: {e}")
            return False
