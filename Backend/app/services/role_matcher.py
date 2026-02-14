"""
Role Matching Service - Semantic Similarity (Local Embeddings)
Matches resumes to job descriptions by role meaning using Sentence Transformers.
Zero API Cost. High Accuracy.
"""

import re
from typing import Optional, Dict
from langchain_huggingface import HuggingFaceEmbeddings
from sentence_transformers import CrossEncoder
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Initialize Local Embedding Models (Singletons)

# 1. Bi-Encoder (Vectors) - For fast retrieval / caching
_embedding_model = None

# 2. Cross-Encoder (Re-Ranking) - For accurate Role Matching
# This is much smarter than vectors for "Is X relevant to Y?"
_cross_encoder_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        logger.info("⏳ Loading Bi-Encoder Embedding Model (all-mpnet-base-v2)...")
        _embedding_model = HuggingFaceEmbeddings(model_name="all-mpnet-base-v2")
        logger.info("✅ Bi-Encoder Model Loaded.")
    return _embedding_model

def get_cross_encoder_model():
    global _cross_encoder_model
    if _cross_encoder_model is None:
        logger.info("⏳ Loading Cross-Encoder Model (ms-marco-MiniLM-L-6-v2)...")
        _cross_encoder_model = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')
        logger.info("✅ Cross-Encoder Model Loaded.")
    return _cross_encoder_model

def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def extract_text_segment(text: str, max_chars: int = 1000) -> str:
    """Helper to safely get start of text"""
    if not text: return ""
    return text[:max_chars].replace('\n', ' ').strip()


def get_text_embedding(text: str) -> Optional[np.ndarray]:
    """
    Get embedding vector for a single string. (Bi-Encoder)
    Returns numpy array or None.
    """
    if not text: return None
    try:
        model = get_embedding_model()
        clean_text = text.lower().strip()
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
    """Legacy Bi-Encoder Similarity (Kept for compatibility if needed elsewhere)"""
    try:
        vec1 = role1_embedding
        if vec1 is None and role1_text:
            vec1 = get_text_embedding(role1_text)
        vec2 = role2_embedding
        if vec2 is None and role2_text:
            vec2 = get_text_embedding(role2_text)   
        if vec1 is None or vec2 is None:
            return 0.0
        score = cosine_similarity(vec1, vec2)[0][0]
        return float(score)
    except:
        return 0.0


def extract_potential_role(text: str) -> Optional[str]:
    """Attempts to extract a role string from text"""
    if not text: return None
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    if not lines: return None
    return lines[0][:100]


def detect_and_match_role(
    jd_title: str,
    email_subject: str,
    email_body: str,
    resume_text: str,
    threshold: float = 0.45,
    jd_title_embedding: np.ndarray = None # Ignored in Cross-Encoder mode, kept for signature comp
) -> Dict[str, any]:
    """
    Role detection using CROSS-ENCODER (High Accuracy).
    Matches JD Title vs Email Subject & Top 15 Resume Lines.
    """
    # 1. Gather Candidates
    role_candidates = []
    
    # Priority 1: Email Subject (Cleaned)
    if email_subject:
        clean_subj = re.sub(r'(?i)(application|applying|resume|for|regarding|re:|ref:)', '', email_subject).strip()
        if clean_subj:
            role_candidates.append(("email_subject", clean_subj))
            
    # Priority 2: Resume Header Lines (Top 15)
    if resume_text:
        lines = [line.strip() for line in resume_text.split('\n') if len(line.strip()) > 3]
        for i, line in enumerate(lines[:15]):
            role_candidates.append((f"resume_line_{i+1}", line[:120])) # Slightly longer context for CrossEncoder

    logger.info(f"DEBUG: Candidates for '{jd_title}': {[c[1] for c in role_candidates]}")

    if not role_candidates:
         return {
            "detected_role": "Unknown",
            "source": None,
            "is_match": True, 
            "similarity": 0.0,
            "jd_title": jd_title
        }

    # 2. Batch Predict with Cross Encoder
    try:
        model = get_cross_encoder_model()
        
        # Prepare pairs: [[JD, Candidate1], [JD, Candidate2]...]
        pairs = [[jd_title, text] for _, text in role_candidates]
        
        # Predict (Returns Logits)
        logits = model.predict(pairs)
        
        # Apply Sigmoid -> Probability
        # If logits is a single float (1 pair), convert to list
        if isinstance(logits, float):
            logits = [logits]
            
        probs = [sigmoid(l) for l in logits]
        
        logger.info(f"DEBUG: Scores for '{jd_title}': {probs}")
        
        # Find Best
        best_idx = np.argmax(probs)
        best_score = float(probs[best_idx])
        best_source = role_candidates[best_idx][0]
        best_role_text = role_candidates[best_idx][1]
        
        # Logger debug
        # logger.info(f"   🔎 Best Match: '{best_role_text}' (Score: {best_score:.3f})")

        is_match = best_score >= threshold
        
        return {
            "detected_role": best_role_text,
            "source": best_source,
            "is_match": is_match,
            "similarity": round(best_score, 2),
            "jd_title": jd_title
        }
        
    except Exception as e:
        logger.error(f"Cross Encoder Error: {e}")
        # Fallback to permissive
        return {"detected_role": "Error", "source": "error", "is_match": True, "similarity": 0.0, "jd_title": jd_title}
