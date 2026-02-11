import os
import base64
import email
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Setup Logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def get_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if os.path.exists('credentials.json'):
                flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            else:
                print("No credentials.json found.")
                return None
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('gmail', 'v1', credentials=creds)

def debug_gmail_fetch():
    service = get_service()
    if not service:
        return

    # Define test range (Default: Today)
    from datetime import datetime, timedelta
    
    # You can change these manually for testing
    target_start = "2026-02-11"
    target_end = "2026-02-11"
    
    # Logic: Start-1, End+1 for inclusion
    s_dt = datetime.strptime(target_start, "%Y-%m-%d")
    # Logic: Start (Inclusive), End+1 (Exclusive)
    s_dt = datetime.strptime(target_start, "%Y-%m-%d")
    e_dt = datetime.strptime(target_end, "%Y-%m-%d")
    
    q_after = s_dt.strftime("%Y/%m/%d")
    q_before = (e_dt + timedelta(days=1)).strftime("%Y/%m/%d")

    query = f"after:{q_after} before:{q_before}"
    
    print(f"\n🔍 Searching emails from {target_start} to {target_end}...")
    print(f"👉 Actual Gmail Query: '{query}'")
    
    try:
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])
        
        print(f"📬 Found {len(messages)} total emails in this period.\n")
        
        stats = {
            "emails_scanned": len(messages),
            "direct_pdfs": 0,
            "nested_pdfs": 0,
            "eml_attachments": 0,
            "unique_count": 0
        }
        
        unique_resumes = set()

        for msg in messages:
            msg_id = msg['id']
            try:
                message = service.users().messages().get(userId='me', id=msg_id).execute()
                payload = message.get('payload', {})
                headers = payload.get('headers', [])
                
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
                sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown Sender")
                date_sent = next((h['value'] for h in headers if h['name'] == 'Date'), "Unknown Date")
                
                print(f"--------------------------------------------------")
                print(f"📧 ID: {msg_id} | Sent: {date_sent}")
                print(f"   From: {sender}")
                print(f"   Subject: {subject}")
                
                parts = payload.get('parts', [])
                
                # Helper to check parts recursively
                def check_parts(parts_list, indent=3):
                    if not parts_list: return
                    
                    for part in parts_list:
                        fname = part.get('filename')
                        mime = part.get('mimeType')
                        
                        if fname:
                            print(f"{' '*indent}📎 Attachment: {fname} ({mime})")
                            
                            # Direct PDF Check
                            if fname.lower().endswith('.pdf'):
                                if fname in unique_resumes:
                                    print(f"{' '*indent}   ⚠️ DUPLICATE DETECTED (Skipping)")
                                else:
                                    print(f"{' '*indent}   ✅ DIRECT RESUME (PDF)")
                                    stats["direct_pdfs"] += 1
                                    stats["unique_count"] += 1
                                    unique_resumes.add(fname)
                            
                            # EML Check (Logic from main app)
                            elif fname.lower().endswith('.eml') or mime == 'message/rfc822':
                                print(f"{' '*indent}   📦 ATTACHED EMAIL (.eml) - Checking inside...")
                                stats["eml_attachments"] += 1
                                
                                # Fetch and Parse EML content for validation
                                if 'body' in part and 'attachmentId' in part['body']:
                                    try:
                                        att_id = part['body']['attachmentId']
                                        att = service.users().messages().attachments().get(userId='me', messageId=msg_id, id=att_id).execute()
                                        data = att['data']
                                        padded_data = data + '=' * (4 - len(data) % 4) if len(data) % 4 else data
                                        eml_bytes = base64.urlsafe_b64decode(padded_data.encode('UTF-8'))
                                        
                                        msg_obj = email.message_from_bytes(eml_bytes)
                                        for sub_part in msg_obj.walk():
                                            sub_fname = sub_part.get_filename()
                                            if sub_fname and sub_fname.lower().endswith('.pdf'):
                                                if sub_fname in unique_resumes:
                                                    print(f"{' '*indent}      ⚠️ DUPLICATE NESTED RESUME (Skipping): {sub_fname}")
                                                else:
                                                    print(f"{' '*indent}      ✅ NESTED RESUME FOUND: {sub_fname}")
                                                    stats["nested_pdfs"] += 1
                                                    stats["unique_count"] += 1
                                                    unique_resumes.add(sub_fname)
                                    except Exception as e:
                                        print(f"{' '*indent}      ❌ Could not parse .eml: {e}")

                        # Recurse
                        if part.get('parts'):
                            check_parts(part.get('parts'), indent + 3)

                check_parts(parts)

            except Exception as e:
                print(f"Error reading message {msg_id}: {e}")
            
        # Summary Report
        print("\n" + "="*40)
        print("📊 VALIDATION SUMMARY REPORT")
        print("="*40)
        print(f"Total Emails Scanned:       {stats['emails_scanned']}")
        print(f"Direct PDF Attachments:     {stats['direct_pdfs']}")
        print(f"Nested PDFs (inside .eml):  {stats['nested_pdfs']}")
        print("-" * 40)
        print(f"🧠 UNIQUE RESUMES EXPECTED: {stats['unique_count']}")
        print("="*40 + "\n")
                
    except Exception as e:
        print(f"Search failed: {e}")

if __name__ == "__main__":
    debug_gmail_fetch()
