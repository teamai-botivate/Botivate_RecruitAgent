"""
Gmail OAuth 2.0 Service
Handles Google OAuth flow and token management for Gmail access
"""

import os
import json
import pickle
from pathlib import Path
from typing import Optional, Dict
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build


class GmailOAuthService:
    """
    Manages Gmail OAuth 2.0 authentication and token storage
    """
    
    SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
    CLIENT_SECRET_FILE = 'client_secret.json'
    TOKEN_DIR = 'tokens'  # Directory to store user tokens
    
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent.parent  # Backend directory
        self.client_secret_path = self.base_dir / self.CLIENT_SECRET_FILE
        self.token_dir = self.base_dir / self.TOKEN_DIR
        
        # Create token directory if it doesn't exist
        self.token_dir.mkdir(exist_ok=True)
        
        # Verify client_secret.json exists (Warn instead of crash at startup)
        if not self.client_secret_path.exists():
            print(f"⚠️  WARNING: client_secret.json not found at {self.client_secret_path}")
            print("   Gmail integration will be disabled. Download it from Google Cloud Console to enable.")
    
    def get_authorization_url(self, company_id: str, redirect_uri: str) -> tuple[str, str]:
        """
        Generate OAuth authorization URL
        
        Args:
            company_id: Unique identifier for the company
            redirect_uri: Callback URL (e.g., http://localhost:8000/auth/gmail/callback)
        
        Returns:
            (auth_url, state): Authorization URL and state token
        """
        flow = Flow.from_client_secrets_file(
            str(self.client_secret_path),
            scopes=self.SCOPES,
            redirect_uri=redirect_uri
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',  # Get refresh token
            include_granted_scopes='true',
            prompt='consent'  # Force consent screen to get refresh token
        )
        
        # Store state for verification (in production, use Redis/DB)
        state_file = self.token_dir / f"{company_id}_state.json"
        with open(state_file, 'w') as f:
            json.dump({"state": state, "redirect_uri": redirect_uri}, f)
        
        return authorization_url, state
    
    def handle_callback(self, company_id: str, code: str, state: str) -> Dict:
        """
        Handle OAuth callback and exchange code for tokens
        
        Args:
            company_id: Unique identifier for the company
            code: Authorization code from Google
            state: State token for CSRF protection
        
        Returns:
            dict with status and user info
        """
        # Verify state
        state_file = self.token_dir / f"{company_id}_state.json"
        if not state_file.exists():
            raise ValueError("Invalid state: No matching OAuth session found")
        
        with open(state_file, 'r') as f:
            stored_data = json.load(f)
        
        if stored_data['state'] != state:
            raise ValueError("Invalid state: CSRF protection failed")
        
        # Exchange code for tokens
        flow = Flow.from_client_secrets_file(
            str(self.client_secret_path),
            scopes=self.SCOPES,
            redirect_uri=stored_data['redirect_uri']
        )
        
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Save tokens
        self._save_credentials(company_id, credentials)
        
        # Get user email
        gmail_service = build('gmail', 'v1', credentials=credentials)
        profile = gmail_service.users().getProfile(userId='me').execute()
        user_email = profile.get('emailAddress')
        
        # Clean up state file
        state_file.unlink()
        
        return {
            "status": "success",
            "email": user_email,
            "message": f"Gmail connected successfully for {user_email}"
        }
    
    def get_credentials(self, company_id: str) -> Optional[Credentials]:
        """
        Get stored credentials for a company
        
        Args:
            company_id: Unique identifier for the company
        
        Returns:
            Credentials object or None if not found
        """
        token_file = self.token_dir / f"{company_id}_token.pickle"
        
        if not token_file.exists():
            return None
        
        with open(token_file, 'rb') as f:
            credentials = pickle.load(f)
        
        # Refresh if expired
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
            self._save_credentials(company_id, credentials)
        
        return credentials
    
    def _save_credentials(self, company_id: str, credentials: Credentials):
        """
        Save credentials to file (encrypted in production)
        
        Args:
            company_id: Unique identifier for the company
            credentials: OAuth credentials
        """
        token_file = self.token_dir / f"{company_id}_token.pickle"
        
        with open(token_file, 'wb') as f:
            pickle.dump(credentials, f)
    
    def get_gmail_service(self, company_id: str):
        """
        Get authenticated Gmail service for a company
        
        Args:
            company_id: Unique identifier for the company
        
        Returns:
            Gmail API service object
        
        Raises:
            ValueError: If no credentials found
        """
        credentials = self.get_credentials(company_id)
        
        if not credentials:
            raise ValueError(f"No Gmail credentials found for company {company_id}. Please connect Gmail first.")
        
        return build('gmail', 'v1', credentials=credentials)
    
    def revoke_access(self, company_id: str) -> bool:
        """
        Revoke Gmail access and delete stored tokens
        
        Args:
            company_id: Unique identifier for the company
        
        Returns:
            True if successful
        """
        token_file = self.token_dir / f"{company_id}_token.pickle"
        
        if token_file.exists():
            # Get credentials
            credentials = self.get_credentials(company_id)
            
            # Revoke access (optional - tells Google to invalidate the token)
            if credentials:
                try:
                    credentials.revoke(Request())
                except:
                    pass  # Ignore errors during revocation
            
            # Delete local token
            token_file.unlink()
        
        return True
    
    def is_connected(self, company_id: str) -> bool:
        """
        Check if a company has connected Gmail
        
        Args:
            company_id: Unique identifier for the company
        
        Returns:
            True if connected and valid
        """
        try:
            credentials = self.get_credentials(company_id)
            return credentials is not None and credentials.valid
        except:
            return False


# Singleton instance
gmail_oauth_service = GmailOAuthService()
