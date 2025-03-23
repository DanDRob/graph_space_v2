from typing import Dict, Any, Optional, List
import os
import json
import secrets
from urllib.parse import urlencode

from flask import url_for, session, redirect, request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from graph_space_v2.utils.helpers.path_utils import ensure_dir_exists, get_data_dir
from graph_space_v2.utils.errors.exceptions import IntegrationError


class GoogleWebAuth:
    """Google API authentication helper for web applications."""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scopes: Optional[List[str]] = None,
        token_storage_dir: Optional[str] = None
    ):
        """
        Initialize Google Web authentication.

        Args:
            client_id: Google client ID
            client_secret: Google client secret
            redirect_uri: OAuth redirect URI
            scopes: API scopes to request
            token_storage_dir: Directory to store tokens
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.scopes = scopes or [
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/calendar.readonly"
        ]

        self.token_storage_dir = token_storage_dir or os.path.join(
            get_data_dir(), "credentials")
        ensure_dir_exists(self.token_storage_dir)

    def start_auth_flow(self, user_id: str, state: Optional[str] = None) -> str:
        """
        Start the OAuth flow by creating a authorization URL.

        Args:
            user_id: User identifier
            state: State parameter for CSRF protection

        Returns:
            Authorization URL to redirect the user to
        """
        # Use InstalledAppFlow instead of Flow for better local server handling
        flow = InstalledAppFlow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            },
            scopes=self.scopes
        )

        # Generate secure state if not provided
        if not state:
            state = secrets.token_urlsafe(16)

        # Store state in session for verification
        session['google_auth_state'] = state

        # Generate the authorization URL with state
        authorization_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',
            state=state
        )

        return authorization_url

    def handle_callback(self, request_url: str) -> Dict[str, Any]:
        """
        Handle the OAuth callback.

        Args:
            request_url: The full callback URL with query parameters

        Returns:
            Dictionary with token information
        """
        # Get the state from the request
        state = request.args.get('state')

        # Verify state matches what we stored
        if state != session.get('google_auth_state'):
            raise IntegrationError(
                "Invalid state parameter. Authentication session may have expired.")

        # Create flow with client config
        flow = InstalledAppFlow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri]
                }
            },
            scopes=self.scopes,
            redirect_uri=self.redirect_uri
        )

        # Exchange the auth code in the callback for credentials
        authorization_response = request_url
        flow.fetch_token(authorization_response=authorization_response)

        # Get credentials
        credentials = flow.credentials

        # Convert credentials to token info
        token_info = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes,
            'expiry': credentials.expiry.isoformat() if credentials.expiry else None
        }

        # Clean up session
        if 'google_auth_state' in session:
            del session['google_auth_state']

        return token_info

    def save_token(self, token_info: Dict[str, Any], user_id: str) -> None:
        """
        Save token information for a user.

        Args:
            token_info: Token information
            user_id: User identifier
        """
        token_file = os.path.join(
            self.token_storage_dir, f"{user_id}_token.json")

        with open(token_file, 'w') as f:
            json.dump(token_info, f)

    def get_credentials(self, user_id: str) -> Optional[Credentials]:
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

            # Refresh token if expired
            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # Save the refreshed token
                token_info = {
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': creds.scopes,
                    'expiry': creds.expiry.isoformat() if creds.expiry else None
                }
                self.save_token(token_info, user_id)

            return creds

        except Exception as e:
            print(f"Error loading credentials: {e}")
            return None

    def revoke_token(self, user_id: str) -> bool:
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
