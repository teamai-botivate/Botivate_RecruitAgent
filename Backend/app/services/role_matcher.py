"""
Role Matching Service - Semantic Similarity (Local Embeddings)
Matches resumes to job descriptions by role meaning using Sentence Transformers.
Zero API Cost. High Accuracy.
"""

import re
from typing import Optional, Dict
from langchain_huggingface import HuggingFaceEmbeddings
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Initialize Local Embedding Model (Singleton)
# all-MiniLM-L6-v2 is fast and effective for short text similarity
_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        logger.info("⏳ Loading Role Matcher Embedding Model (all-MiniLM-L6-v2)...")
        _embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        logger.info("✅ Role Matcher Model Loaded.")
    return _embedding_model


def extract_text_segment(text: str, max_chars: int = 1000) -> str:
    """Helper to safely get start of text"""
    if not text: return ""
    return text[:max_chars].replace('\n', ' ').strip()


def get_text_embedding(text: str) -> Optional[np.ndarray]:
    """
    Get embedding vector for a single string.
    Returns numpy array or None.
    """
    if not text: return None
    try:
        model = get_embedding_model()
        # Clean
        clean_text = text.lower().strip()
        # Embed
        embedding = model.embed_documents([clean_text])[0]
        return np.array([embedding])
    except Exception as e:
        logger.error(f"Embedding Error: {e}")
        return None


def calculate_semantic_similarity(
    role1_text: str = None, 
    role2_text: str = None,
    role1_embedding: np.ndarray = None,
    role2_embedding: np.ndarray = None
) -> float:
    """
    Calculate semantic similarity using embeddings.
    Can pass either raw text (will be embedded) or pre-computed embeddings.
    
    Args:
        role1_text: Text for first role (optional if embedding provided)
        role2_text: Text for second role (optional if embedding provided)
        role1_embedding: Pre-computed vector for role1
        role2_embedding: Pre-computed vector for role2
        
    Returns:
        Similarity score (0.0 to 1.0)
    """
    try:
        # Resolve Input 1
        vec1 = role1_embedding
        if vec1 is None and role1_text:
            vec1 = get_text_embedding(role1_text)
            
        # Resolve Input 2
        vec2 = role2_embedding
        if vec2 is None and role2_text:
            vec2 = get_text_embedding(role2_text)
            
        if vec1 is None or vec2 is None:
            return 0.0
        
        # Calculate Cosine Similarity
        score = cosine_similarity(vec1, vec2)[0][0]
        return float(score)
        
    except Exception as e:
        logger.error(f"Semantic Role Match Error: {e}")
        return 0.0


def extract_potential_role(text: str) -> Optional[str]:
    """
    Attempts to extract a role string from text (Subject/Header)
    Very basic heuristic to limit text length for embedding.
    """
    if not text: return None
    
    # Just take the first meaningful chunk (e.g. email subject)
    # or the first line of a resume
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines: return None
    
    # Return first line, truncated to 100 chars max (Role titles aren't huge)
    return lines[0][:100]





def detect_and_match_role(
    jd_title: str,
    email_subject: str,
    email_body: str,
    resume_text: str,
    threshold: float = 0.45,
    jd_title_embedding: np.ndarray = None  # Optimization: Pass pre-computed JD vector
) -> Dict[str, any]:
    """
    Complete role detection and matching pipeline (Semantic)
    
    Returns:
        Match details dict
    """
    # 1. Identify Candidate Role Candidates
    # We'll try to match against Email Subject first (High Confidence)
    role_candidates = []
    
    if email_subject:
        # cleanup subject: remove "Applying for", "Resume:", etc.
        clean_subj = re.sub(r'(?i)(application|applying|resume|for|regarding|re:|ref:)', '', email_subject).strip()
        if clean_subj:
            role_candidates.append(("email_subject", clean_subj))
            
    # Try Resume Header Lines (Top 15 Lines) - DEEP SCAN
    # Often line 1 is Name, Line 2 is Phone, Line 3 is "Data Analyst"
    if resume_text:
        lines = [line.strip() for line in resume_text.split('\n') if len(line.strip()) > 3] # Skip empty/tiny lines
        # Check top 15 lines
        for i, line in enumerate(lines[:15]):
            # Truncate line to avoid massive noise
            clean_line = line[:100] 
            role_candidates.append((f"resume_line_{i+1}", clean_line))

    # 2. Check Match
    best_score = 0.0
    best_source = None
    best_role_text = None
    
    # If no candidates found (unlikely), we can't match.
    if not role_candidates:
         return {
            "detected_role": "Unknown",
            "source": None,
            "is_match": True, # Default to True (Safe Mode) if we can't tell
            "similarity": 0.0,
            "jd_title": jd_title
        }

    # Compare JD Title vs Candidates
    for source, text in role_candidates:
        # Use pre-computed JD embedding if available
        score = calculate_semantic_similarity(
            role1_text=jd_title,
            role2_text=text,
            role1_embedding=jd_title_embedding
        )
        
        # logger.debug(f"   🔎 Checking '{text}' vs '{jd_title}': {score:.2f}")
        
        if score > best_score:
            best_score = score
            best_source = source
            best_role_text = text
            
    is_match = best_score >= threshold
    
    return {
        "detected_role": best_role_text,
        "source": best_source,
        "is_match": is_match,
        "similarity": round(best_score, 2),
        "jd_title": jd_title
    }
