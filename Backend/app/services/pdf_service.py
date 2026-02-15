
import io
from pypdf import PdfReader

class PDFService:
    def extract_text(self, file_content: bytes) -> tuple[str, int]:
        """
        Extract text from PDF bytes.
        Prioritizes pdfplumber (layout-aware), falls back to pypdf.
        """
        text = ""
        page_count = 0
        
        # Method 1: Try pdfplumber (Superior Layout Handling)
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                page_count = len(pdf.pages)
                for page in pdf.pages:
                    # Extract text preserving layout (approximate)
                    page_text = page.extract_text(layout=True)
                    if page_text:
                        text += page_text + "\n"
            return self._clean_text(text), page_count
            
        except ImportError:
            # Fallback if library missing
            pass
        except Exception as e:
            # Fallback if pdfplumber fails on specific PDF
            print(f"pdfplumber failed: {e}. Falling back to pypdf.")
            pass

        # Method 2: pypdf (Fallback)
        try:
            pdf = PdfReader(io.BytesIO(file_content))
            page_count = len(pdf.pages)
            for page in pdf.pages:
                # Try normal extraction
                page_text = page.extract_text()
                if not page_text or len(page_text.strip()) < 5:
                    # Try layout mode if normal fails
                    try:
                        page_text = page.extract_text(extraction_mode="layout")
                    except: pass
                
                if page_text:
                    text += page_text + "\n"
            return self._clean_text(text), page_count
            
        except Exception as e:
            print(f"PDF Extraction Failed: {e}")
            return "", 0

    def _clean_text(self, text: str) -> str:
        if not text: return ""
        # Clean common encoding issues
        text = text.replace('\x00', '')
        # Fix multiple newlines
        import re
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def extract_emails_advanced(self, file_content: bytes) -> str:
        """
        Advanced Email Extraction using PyMuPDF (fitz).
        Extracts both visible text and hidden mailto: links.
        Returns the first valid email found, or empty string.
        """
        import fitz
        import re
        
        found_emails = [] # Use list to preserve order of appearance (usually better than set)
        email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        
        try:
            # fitz needs bytes stream
            with fitz.open(stream=file_content, filetype="pdf") as doc:
                for page in doc:
                    # 1. Visible Text
                    text = page.get_text("text")
                    text_emails = re.findall(email_pattern, text)
                    for email in text_emails:
                        if email not in found_emails:
                            found_emails.append(email)
                        
                    # 2. Hyperlinks (mailto: or raw email in URI)
                    links = page.get_links()
                    for link in links:
                        if "uri" in link:
                            uri = link["uri"].strip()
                            email = ""
                            
                            # Case A: mailto: prefix
                            if uri.startswith("mailto:"):
                                email = uri.replace("mailto:", "").strip()
                            # Case B: Raw email in URI (common in some PDF generators)
                            elif "@" in uri and "." in uri and not uri.startswith("http") and not uri.startswith("www"):
                                email = uri
                                
                            # Clean potential query params (?subject=...)
                            if "?" in email:
                                email = email.split("?")[0]
                                
                            if email and email not in found_emails:
                                found_emails.append(email)
                                
            # Filter out Placeholders
            valid_emails = []
            placeholders = ["[email]", "email@example.com", "name@email.com", "yourname@email.com", "user@domain.com", "email"]
            
            for email in found_emails:
                clean_email = email.lower().strip()
                if clean_email not in placeholders and "example.com" not in clean_email and "@" in email and "." in email:
                    valid_emails.append(email)
            
            # Return first VALID one found
            if valid_emails:
                return valid_emails[0]
            
            # If no valid email found, return empty
            return ""
            
        except Exception as e:
            print(f"Advanced Email Extraction Failed: {e}")
            return ""

pdf_service = PDFService()
