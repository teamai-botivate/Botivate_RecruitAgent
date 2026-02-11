import os
import base64
import email
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import logging

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

logger = logging.getLogger(__name__)

class GmailService:
    def __init__(self):
        self.creds = None
        # Verify credentials existence
        if os.path.exists('token.json'):
            self.creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        
        # If no valid credentials available, we need user login flow (Interactive)
        # Note: This requires a browser interaction on first run.
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                try:
                    self.creds.refresh(Request())
                except Exception as e:
                    logger.error(f"Token refresh failed: {e}")
                    self.creds = None
            
            if not self.creds:
                if os.path.exists('credentials.json'):
                    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                    # Run logic typically requires local server, might be tricky in headless/agent env.
                    # For local desktop user, run_local_server() works.
                    # self.creds = flow.run_local_server(port=0)
                    # Save the credentials for the next run
                    # with open('token.json', 'w') as token:
                    #     token.write(self.creds.to_json())
                    pass # Placeholder: handled by explicit auth method if needed
                else:
                    logger.warning("No credentials.json found. Gmail Service disabled.")

    def authenticate_interactive(self):
        """Must be called manually to generate token.json if missing."""
        if not os.path.exists('credentials.json'):
             raise FileNotFoundError("Please place 'credentials.json' in the root directory.")
             
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        self.creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(self.creds.to_json())
        return self.creds

    def fetch_resumes(self, start_date: str, end_date: str):
        """
        Fetches PDFs from Gmail within date range (YYYY/MM/DD).
        Handles direct PDF attachments and nested PDFs within .eml attachments.
        Adjusts dates to be inclusive (Start - 1 day, End + 1 day) for Gmail API.
        """
        if not self.creds:
            try:
                self.authenticate_interactive()
            except Exception as e:
                logger.error(f"Authentication failed: {e}")
                return []

        # Adjust Dates for Inclusive Query
        try:
            from datetime import datetime, timedelta
            # Handle potential formats YYYY-MM-DD or YYYY/MM/DD
            fmt = "%Y-%m-%d" if "-" in start_date else "%Y/%m/%d"
            start_dt = datetime.strptime(start_date, fmt)
            end_dt = datetime.strptime(end_date, fmt)
            
            # Gmail 'after' IS inclusive (Start Date 00:00)
            # Gmail 'before' IS exclusive (End Date + 1 00:00)
            query_after = start_dt.strftime("%Y/%m/%d")
            query_before = (end_dt + timedelta(days=1)).strftime("%Y/%m/%d")
        except Exception as e:
            # Fallback if format is wrong
            logger.warning(f"Date format mismatch: {e}. Using raw strings: {start_date} to {end_date}")
            query_after = start_date.replace("-", "/")
            query_before = end_date.replace("-", "/")

        service = build('gmail', 'v1', credentials=self.creds)
        
        # Query: has attachment, filename pdf/docx, after start_date, before end_date
        query = f'has:attachment (resume OR cv OR hiring OR job) after:{query_after} before:{query_before}'
        logger.info(f"Searching Gmail with query: {query}")
        
        try:
            results = service.users().messages().list(userId='me', q=query).execute()
            messages = results.get('messages', [])
            
            logger.info(f"Found {len(messages)} matching emails.")
            resume_files = [] # List of (filename, bytes)
            
            for msg in messages:
                msg_id = msg['id']
                try:
                    message = service.users().messages().get(userId='me', id=msg_id).execute()
                    payload = message.get('payload', {})
                    parts = payload.get('parts', [])
                    
                    if not parts:
                        logger.info(f"Email {msg_id} has no parts. Skipping.")
                        continue

                    found_attachment = False
                    for part in parts:
                        filename = part.get('filename', '')
                        mime_type = part.get('mimeType', '')
                        
                        # Case 1: Direct PDF Attachment
                        if filename and filename.lower().endswith('.pdf'):
                            content = self._download_attachment(service, 'me', msg_id, part)
                            if content:
                                resume_files.append({
                                    "filename": filename,
                                    "content": content,
                                    "email_id": msg_id
                                })
                                logger.info(f"   ✅ Downloaded PDF: {filename}")
                                found_attachment = True
                        
                        # Case 2: Attached Email (.eml) - Recursive Search
                        elif (filename and filename.lower().endswith('.eml')) or mime_type == 'message/rfc822':
                            logger.info(f"   [Email {msg_id}] Found .eml attachment: {filename}. Parsing...")
                            eml_content = self._download_attachment(service, 'me', msg_id, part)
                            if eml_content:
                                # Parse the EML content
                                try:
                                    msg_obj = email.message_from_bytes(eml_content)
                                    # Walk through the EML to find PDF attachments
                                    for sub_part in msg_obj.walk():
                                        sub_fname = sub_part.get_filename()
                                        if sub_fname and sub_fname.lower().endswith('.pdf'):
                                            sub_content = sub_part.get_payload(decode=True)
                                            if sub_content:
                                                resume_files.append({
                                                    "filename": f"[Extracted] {sub_fname}",
                                                    "content": sub_content,
                                                    "email_id": msg_id
                                                })
                                                logger.info(f"      ✅ Extracted PDF from EML: {sub_fname}")
                                                found_attachment = True
                                except Exception as e:
                                    logger.error(f"      ❌ Failed to parse .eml {filename}: {e}")

                    if not found_attachment:
                        logger.info(f"   No valid PDF or .eml attachments found in email {msg_id}")

                except Exception as e:
                    logger.error(f"Error processing message {msg_id}: {e}")
            
            return resume_files

        except Exception as e:
            logger.error(f"Gmail Fetch Error: {e}")
            return []

    def _download_attachment(self, service, user_id, msg_id, part):
        """Helper to download and decode attachment data."""
        try:
            if 'body' in part and 'attachmentId' in part['body']:
                att_id = part['body']['attachmentId']
                att = service.users().messages().attachments().get(userId=user_id, messageId=msg_id, id=att_id).execute()
                data = att['data']
                # Fix padding
                padded_data = data + '=' * (4 - len(data) % 4) if len(data) % 4 else data
                return base64.urlsafe_b64decode(padded_data.encode('UTF-8'))
        except Exception as e:
            logger.error(f"Download Attachment Error: {e}")
        return None

gmail_service = GmailService()
