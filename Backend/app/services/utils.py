
import re
import spacy
from typing import Set, Tuple
import subprocess

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Downloading Spacy Model 'en_core_web_sm'...")
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")

def clean_text(text: str) -> str:
    """Sanitize resume text."""
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Fix broken OCR spacing (e.g. "h e l l o   w o r l d")
    # Heuristic: If > 40% of "words" are single characters, assume it's spaced-out text
    tokens = text.split()
    if len(tokens) > 10:
        single_char_count = sum(1 for t in tokens if len(t) == 1)
        if (single_char_count / len(tokens)) > 0.4:
            # Smart Fix: Only collapse spaces between single characters to reconstruct words
            # e.g. "s q l" -> "sql"
            text = re.sub(r'(?<=\b\w)\s+(?=\w\b)', '', text)

            
    return text.lower()

def extract_keywords(text: str) -> Set[str]:
    """Extract prominent Nouns and Proper Nouns (Skills/Tech)."""
    doc = nlp(text.lower())
    keywords = set()
    
    # Generic terms to IGNORE (Corporate Fluff)
    GENERIC_TERMS = {
        "experience", "skills", "year", "years", "work", "team", "growth", "companies",
        "project", "projects", "role", "candidate", "ability", "time", "date",
        "knowledge", "understanding", "opportunity", "environment", "system", "systems",
        "application", "applications", "client", "clients", "solution", "solutions",
        "framework", "frameworks", "technologies", "technology", "requirement", "requirements",
        "responsibility", "responsibilities", "description", "summary", "profile",
        "details", "contact", "email", "phone", "address", "location", "salary",
        "month", "months", "industry", "company", "service", "services",
        "tool", "tools", "database", "databases", "methodology", "methodologies",
        "development", "design", "testing", "implementation", "support", "maintenance",
        "performance", "quality", "standard", "standards", "practice", "practices",
        "career", "goal", "goals", "objective", "objectives", "education", "university",
        "degree", "bachelor", "master", "phd", "diploma", "certification", "certificate",
        "title", "job", "employment", "history", "organization", "institute", "school",
        "analyst", "manager", "management", "business", "operations", "expert", "expertise"
    }

    # 1. Single Tokens (Strong technical terms often appear alone)
    for token in doc:
        # Allow specific short tech terms
        if token.text in ["c", "r", "go", "net", "qt", "ui", "ux", "ai", "ml"]:
            keywords.add(token.text)
            continue
            
        if token.pos_ in ["PROPN", "NOUN"] and not token.is_stop and len(token.text) > 2:
            if token.text not in GENERIC_TERMS and not token.is_digit:
                keywords.add(token.text)

    # 2. Noun Chunks (Phrases like "Machine Learning", "REST API")
    for chunk in doc.noun_chunks:
        clean_chunk = chunk.text.strip()
        # Filter Logic: Must be <= 3 words
        if len(clean_chunk.split()) <= 3 and len(clean_chunk) > 2:
            # Check if chunk contains any generic terms
            has_generic = any(word in GENERIC_TERMS for word in clean_chunk.split())
            if not has_generic:
                keywords.add(clean_chunk)
            
    return keywords

def extract_years_of_experience(text: str) -> float:
    """Extract experience using robust regex patterns."""
    # Look for "X years", "X.Y years", "X+ yrs", "X exp"
    patterns = [
        r'(\d+(?:\.\d+)?)\+?\s*(?:years?|yrs?)',
        r'experience\s*:\s*(\d+(?:\.\d+)?)',
        r'(\d+(?:\.\d+)?)\s*year'
    ]
    
    found_years = []
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for m in matches:
            try:
                val = float(m)
                # Sanity check: Experience between 0 and 40 years
                if 0 < val < 40:
                    found_years.append(val)
            except:
                pass
                
    if found_years:
        # Return the maximum year mentioned (assumes "Total Experience: 5" > "Job: 2")
        return max(found_years)
        
    return 0.0

def extract_education_level(text: str) -> int:
    """Determine education weight (0-10) based on keywords."""
    text_lower = text.lower()
    if any(k in text_lower for k in ["phd", "doctorate"]):
        return 10
    if any(k in text_lower for k in ["master", "m.tech", "ms", "mba"]):
        return 8
    if any(k in text_lower for k in ["bachelor", "b.tech", "bs", "be", "btech"]):
        return 6
    if "diploma" in text_lower:
        return 4
    return 2

def extract_name(text: str, filename: str = "") -> str:
    """Extract candidate name with robust filtering."""
    
    # Common False Positives (Job Titles, Headers)
    IGNORE_NAMES = {
        "resume", "curriculum", "vitae", "cv", "summary", "profile", "skills", 
        "experience", "education", "project", "work", "developer", "engineer",
        "manager", "analyst", "consultant", "intern", "fresher", "date", "place",
        "mobile", "phone", "email", "address", "linkedin", "github", "portfolio",
        "declarations", "objective", "name", "javascript", "java", "python", "sql",
        "html", "css", "react", "node", "aws", "docker", "git", "linux", "windows",
        "da", "experienced", "yrs", "year", "years"
    }

    # 1. Spacy NLP (Best)
    try:
        # Limit to top 500 chars (Header usually contains name)
        doc = nlp(text[:500]) 
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                clean_name = ent.text.strip()
                # Validation: 
                # - Must be 2+ words (First Last)
                # - Must not contain numbers
                # - Must not be a reserved keyword
                if len(clean_name.split()) >= 2 and not any(char.isdigit() for char in clean_name):
                    # Check against ignore list
                    is_valid = True
                    for part in clean_name.lower().split():
                        if part in IGNORE_NAMES or len(part) < 2:
                            is_valid = False
                            break
                    
                    if is_valid:
                        return clean_name.title()
    except:
        pass

    # 2. Filename Cleanup (Reliable fallback)
    if filename:
        # Remove extension
        clean = filename.rsplit('.', 1)[0]
        
        # Remove brackets [Email] [Extracted] or (4)
        clean = re.sub(r'\[.*?\]', '', clean)
        clean = re.sub(r'\(.*?\)', '', clean) # Remove (4) or (copy)
        
        # Replace separators
        clean = clean.replace("_", " ").replace("-", " ").replace("+", " ").replace(",", " ")
        
        # Remove noise words and digits
        clean = re.sub(r'\b(resume|cv|file|copy|new|updated|final|draft|exp|experienced|da|yrs|years|\d+)\b', '', clean, flags=re.IGNORECASE)
        
        # Collapse spaces
        clean = re.sub(r'\s+', ' ', clean).strip()
        
        if len(clean) > 2:
            return clean.title()

    return "Unknown Candidate"
