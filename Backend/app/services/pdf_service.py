
import io
from pypdf import PdfReader

class PDFService:
    def extract_text(self, file_content: bytes) -> tuple[str, int]:
        pdf = PdfReader(io.BytesIO(file_content))
        text = ""
        text = ""
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
        
        # Clean common encoding issues
        text = text.replace('\x00', '')
        
        return text, len(pdf.pages)

pdf_service = PDFService()
