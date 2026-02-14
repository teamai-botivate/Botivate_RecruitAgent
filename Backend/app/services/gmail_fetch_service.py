"""
Gmail Fetch Service using OAuth 2.0
Fetches resume attachments from Gmail using OAuth credentials
"""

import base64
import email
import logging
from datetime import datetime, timedelta
from typing import List, Dict
from googleapiclient.discovery import build

from .gmail_oauth import gmail_oauth_service

logger = logging.getLogger("GmailFetchService")


class GmailFetchService:
    """
    Fetches resumes from Gmail using OAuth 2.0 authentication
    """
    
    COMPANY_ID = "default_company"  # Single-tenant mode
    
    def is_connected(self) -> bool:
        """
        Check if Gmail is connected for the default company
        
        Returns:
            bool: True if Gmail is connected
        """
        return gmail_oauth_service.is_connected(self.COMPANY_ID)
    
    def fetch_resumes(self, start_date: str, end_date: str) -> List[Dict]:
        """
        Fetch resume attachments from Gmail
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
        
        Returns:
            List of dicts with keys: filename, content, email_subject, email_body
        
        Raises:
            ValueError: If Gmail is not connected
        """
        if not self.is_connected():
            raise ValueError(
                "Gmail not connected. Please connect your Gmail account first at "
                "http://localhost:8000/auth/gmail/start?company_id=default_company"
            )
        
        try:
            # Get authenticated Gmail service
            service = gmail_oauth_service.get_gmail_service(self.COMPANY_ID)
            
            # CRITICAL FIX: Increment end_date by 1 day because Gmail 'before:' is exclusive.
            # If start=2026-02-14 and end=2026-02-14, query 'after:..14 before:..14' returns nothing.
            # We want 'after:..14 before:..15' to cover the 14th.
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                end_dt_inc = end_dt + timedelta(days=1)
                effective_end_date = end_dt_inc.strftime("%Y-%m-%d")
            except ValueError:
                # Fallback if date format is weird, though it should be YYYY-MM-DD
                logger.warning(f"Date format warning: {end_date}. Using original.")
                effective_end_date = end_date

            # Build search query
            # Search for emails with attachments in date range
            query = f'has:attachment after:{start_date} before:{effective_end_date}'
            
            logger.info(f"Searching Gmail with query: {query}")
            
            # Search messages
            results = service.users().messages().list(
                userId='me',
                q=query,
                maxResults=100  # Limit to prevent overwhelming
            ).execute()
            
            messages = results.get('messages', [])
            logger.info(f"Found {len(messages)} emails with attachments")
            
            if not messages:
                logger.warning("No emails found in the specified date range")
                return []
            
            resumes = []
            
            # Process each message
            for msg_info in messages:
                try:
                    msg_id = msg_info['id']
                    
                    # Get full message
                    message = service.users().messages().get(
                        userId='me',
                        id=msg_id,
                        format='full'
                    ).execute()
                    
                    # Extract subject
                    headers = message['payload'].get('headers', [])
                    subject = next(
                        (h['value'] for h in headers if h['name'].lower() == 'subject'),
                        'No Subject'
                    )
                    
                    # Extract body (simplified - just get first text part)
                    body = self._extract_body(message['payload'])
                    
                    # Process attachments
                    parts = message['payload'].get('parts', [])
                    attachments_in_email = []
                    extracted_count = 0
                    skipped_count = 0
                    
                    for part in parts:
                        if part.get('filename'):
                            filename = part['filename']
                            mime_type = part.get('mimeType', '')
                            attachments_in_email.append(filename)
                            
                            # Case 1: Direct Resume Files (PDF, TXT, DOC, DOCX)
                            is_resume = (filename.lower().endswith('.pdf') or 
                                       filename.lower().endswith('.txt') or
                                       filename.lower().endswith('.doc') or
                                       filename.lower().endswith('.docx'))
                            
                            # Case 2: Email Attachments (.eml) - May contain resumes inside
                            is_email_attachment = (filename.lower().endswith('.eml') or 
                                                 mime_type == 'message/rfc822')
                            
                            if is_resume:
                                # Direct resume file
                                if 'attachmentId' in part['body']:
                                    attachment_id = part['body']['attachmentId']
                                    attachment = service.users().messages().attachments().get(
                                        userId='me',
                                        messageId=msg_id,
                                        id=attachment_id
                                    ).execute()
                                    
                                    data = attachment['data']
                                    file_data = base64.urlsafe_b64decode(data)
                                    
                                    resumes.append({
                                        'filename': filename,
                                        'content': file_data,
                                        'email_subject': subject,
                                        'email_body': body
                                    })
                                    
                                    logger.info(f"  ✅ Extracted: {filename} from '{subject}'")
                                    extracted_count += 1
                            
                            elif is_email_attachment:
                                # .eml file - Recursively extract resumes from inside
                                logger.info(f"  📧 Found .eml attachment: {filename}. Parsing for nested resumes...")
                                
                                if 'attachmentId' in part['body']:
                                    attachment_id = part['body']['attachmentId']
                                    attachment = service.users().messages().attachments().get(
                                        userId='me',
                                        messageId=msg_id,
                                        id=attachment_id
                                    ).execute()
                                    
                                    data = attachment['data']
                                    eml_content = base64.urlsafe_b64decode(data)
                                    
                                    # Parse the .eml file
                                    try:
                                        msg_obj = email.message_from_bytes(eml_content)
                                        
                                        # Walk through the email to find resume attachments
                                        for sub_part in msg_obj.walk():
                                            sub_fname = sub_part.get_filename()
                                            if sub_fname:
                                                is_nested_resume = (sub_fname.lower().endswith('.pdf') or 
                                                                  sub_fname.lower().endswith('.txt') or
                                                                  sub_fname.lower().endswith('.doc') or
                                                                  sub_fname.lower().endswith('.docx'))
                                                
                                                if is_nested_resume:
                                                    sub_content = sub_part.get_payload(decode=True)
                                                    if sub_content:
                                                        resumes.append({
                                                            'filename': f"[Forwarded] {sub_fname}",
                                                            'content': sub_content,
                                                            'email_subject': subject,
                                                            'email_body': body
                                                        })
                                                        
                                                        logger.info(f"    ✅ Extracted from .eml: {sub_fname}")
                                                        extracted_count += 1
                                    
                                    except Exception as e:
                                        logger.error(f"    ❌ Failed to parse .eml {filename}: {e}")
                                        skipped_count += 1
                            
                            else:
                                # Unsupported format
                                logger.warning(f"  ⚠️ Skipped: {filename} (unsupported format) from '{subject}'")
                                skipped_count += 1
                    
                    # Log summary for this email
                    if len(attachments_in_email) > 0:
                        logger.info(f"  📧 Email '{subject}': {extracted_count} extracted, {skipped_count} skipped (Total: {len(attachments_in_email)} attachments)")
                
                except Exception as e:
                    logger.error(f"Error processing message {msg_info.get('id')}: {e}")
                    continue
            
            logger.info(f"Successfully extracted {len(resumes)} resume files from Gmail")
            return resumes
        
        except Exception as e:
            logger.error(f"Gmail fetch failed: {e}")
            raise
    
    def _extract_body(self, payload: dict) -> str:
        """
        Extract email body from message payload
        
        Args:
            payload: Message payload from Gmail API
        
        Returns:
            Email body text
        """
        try:
            # Try to get body from 'data' field
            if 'body' in payload and 'data' in payload['body']:
                data = payload['body']['data']
                text = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                return text
            
            # Look in parts
            if 'parts' in payload:
                for part in payload['parts']:
                    if part.get('mimeType') == 'text/plain':
                        if 'data' in part.get('body', {}):
                            data = part['body']['data']
                            text = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                            return text
            
            return ""
        
        except Exception as e:
            logger.warning(f"Could not extract email body: {e}")
            return ""


# Singleton instance
gmail_fetch_service = GmailFetchService()
