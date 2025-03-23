from typing import Dict, List, Any, Optional
import os
import json
import datetime
import pickle

# Google API client libraries
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build, Resource
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

from graph_space_v2.utils.helpers.path_utils import ensure_dir_exists, get_data_dir


class GoogleAuth:
    """Google API authentication helper."""

    def __init__(
        self,
        credentials_file: Optional[str] = None,
        token_file: Optional[str] = None,
        scopes: Optional[list] = None,
        credentials_dir: Optional[str] = None
    ):
        """
        Initialize Google authentication.

        Args:
            credentials_file: Path to credentials JSON file
            token_file: Path to token file
            scopes: API scopes to request
            credentials_dir: Directory to store credentials
        """
        self.credentials_dir = credentials_dir or os.path.join(
            get_data_dir(), "credentials")
        ensure_dir_exists(self.credentials_dir)

        self.credentials_file = credentials_file
        self.token_file = token_file or os.path.join(
            self.credentials_dir, "token.json")
        self.scopes = scopes or [
            "https://www.googleapis.com/auth/drive.readonly"]
        self.credentials = None

    def get_credentials(self, user_id: str = "default") -> Optional[Credentials]:
        """
        Get OAuth2 credentials for a user.

        Args:
            user_id: Identifier for the user

        Returns:
            OAuth2 credentials or None if not available
        """
        token_file = os.path.join(
            self.credentials_dir, f"{user_id}_token.json")
        pickle_file = os.path.join(
            self.credentials_dir, f"{user_id}_token.pickle")

        creds = None

        # Check for token.json first (newer format)
        if os.path.exists(token_file):
            try:
                with open(token_file, 'r') as f:
                    creds = Credentials.from_authorized_user_info(
                        json.load(f), self.scopes)
            except Exception as e:
                print(f"Error loading credentials from token file: {e}")

        # Try pickle file as fallback (older format)
        elif os.path.exists(pickle_file):
            try:
                with open(pickle_file, 'rb') as f:
                    creds = pickle.load(f)
            except Exception as e:
                print(f"Error loading credentials from pickle file: {e}")

        # Refresh token if expired
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_credentials(creds, user_id)
            except Exception as e:
                print(f"Error refreshing credentials: {e}")
                creds = None

        return creds

    def authenticate(self, user_id: str = "default") -> Credentials:
        """
        Authenticate with Google and get credentials.

        Args:
            user_id: Identifier for the user

        Returns:
            OAuth2 credentials
        """
        # Check for existing credentials
        creds = self.get_credentials(user_id)

        # If no valid credentials, run the OAuth flow
        if not creds or not creds.valid:
            if not self.credentials_file:
                raise ValueError(
                    "credentials_file is required for new authentication")

            flow = InstalledAppFlow.from_client_secrets_file(
                self.credentials_file, self.scopes)
            creds = flow.run_local_server(port=0)

            # Save credentials
            self._save_credentials(creds, user_id)

        return creds

    def _save_credentials(self, creds: Credentials, user_id: str = "default") -> None:
        """Save credentials to the token file"""
        token_file = os.path.join(
            self.credentials_dir, f"{user_id}_token.json")

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

    def revoke_credentials(self, user_id: str = "default") -> bool:
        """
        Revoke OAuth credentials for a user.

        Args:
            user_id: Identifier for the user

        Returns:
            True if revoked successfully, False otherwise
        """
        creds = self.get_credentials(user_id)
        if not creds:
            return False

        token_file = os.path.join(
            self.credentials_dir, f"{user_id}_token.json")
        pickle_file = os.path.join(
            self.credentials_dir, f"{user_id}_token.pickle")

        try:
            # Try to revoke the token
            creds.revoke(Request())

            # Delete the token files
            if os.path.exists(token_file):
                os.remove(token_file)

            if os.path.exists(pickle_file):
                os.remove(pickle_file)

            return True

        except Exception as e:
            print(f"Error revoking credentials: {e}")
            return False
