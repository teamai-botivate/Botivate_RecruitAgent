
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
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text.strip()

pdf_service = PDFService()
