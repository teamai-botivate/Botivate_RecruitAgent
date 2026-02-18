"""
Role Matching Service - Zero-Shot Classification
Matches resumes to job descriptions using facebook/bart-large-mnli
More accurate than semantic similarity for role detection.
"""

import re
from typing import Optional, Dict
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Initialize Zero-Shot Classification Pipeline (Singleton)
_zero_shot_classifier = None

def get_zero_shot_classifier():
    """Load Zero-Shot Classification model (BART-large-MNLI)"""
    global _zero_shot_classifier
    if _zero_shot_classifier is None:
        try:
            from transformers import pipeline
            import torch
            
            logger.info("⏳ Loading Zero-Shot Classifier (facebook/bart-large-mnli)...")
            
            # Use GPU if available
            device = 0 if torch.cuda.is_available() else -1
            
            _zero_shot_classifier = pipeline(
                "zero-shot-classification",
                model="facebook/bart-large-mnli",
                device=device
            )
            
            logger.info("✅ Zero-Shot Classifier Loaded Successfully.")
        except Exception as e:
            logger.error(f"Failed to load Zero-Shot Classifier: {e}")
            raise
    
    return _zero_shot_classifier


def extract_text_segment(text: str, max_chars: int = 1000) -> str:
    """Helper to safely get start of text"""
    if not text: return ""
    return text[:max_chars].replace('\n', ' ').strip()


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
    threshold: float = 0.6,  # Zero-shot typically needs higher threshold (0.6-0.7)
    jd_title_embedding: np.ndarray = None  # Kept for backward compatibility
) -> Dict[str, any]:
    """
    Role detection using Zero-Shot Classification (High Accuracy).
    
    Args:
        jd_title: Target role from job description (e.g., "Backend Developer")
        email_subject: Subject line of application email
        email_body: Body of application email
        resume_text: Full resume text
        threshold: Minimum confidence score (0.0-1.0, default 0.6)
    
    Returns:
        Dict with detected_role, is_match, similarity score, etc.
    """
    
    # Construct combined text from email + resume header
    combined_text_parts = []
    
    # Priority 1: Email Subject (Cleaned)
    if email_subject:
        clean_subj = re.sub(
            r'(?i)(application|applying|resume|for|regarding|re:|ref:)', 
            '', 
            email_subject
        ).strip()
        if clean_subj:
            combined_text_parts.append(clean_subj)
    
    # Priority 2: Email Body Preview
    if email_body:
        body_preview = extract_text_segment(email_body, max_chars=300)
        if body_preview:
            combined_text_parts.append(body_preview)
    
    # Priority 3: Resume Header (Top 500 chars - contains role, skills, summary)
    if resume_text:
        resume_header = extract_text_segment(resume_text, max_chars=500)
        if resume_header:
            combined_text_parts.append(resume_header)
    
    # Combine all parts
    combined_text = ". ".join(combined_text_parts)
    
    if not combined_text:
        logger.warning(f"No text available for role matching")
        return {
            "detected_role": "Unknown",
            "source": None,
            "is_match": True,  # Give benefit of doubt
            "similarity": 0.0,
            "jd_title": jd_title
        }
    
    logger.info(f"DEBUG: Candidates for '{jd_title}': ['{combined_text[:100]}...']")
    
    # Run Zero-Shot Classification
    try:
        classifier = get_zero_shot_classifier()
        
        # Classify: Does this text match the target role?
        result = classifier(
            combined_text,
            candidate_labels=[jd_title],
            multi_label=True
        )
        
        # Extract score
        relevance_score = result["scores"][0] if result["scores"] else 0.0
        
        logger.info(f"DEBUG: Scores for '{jd_title}': [{relevance_score:.4f}]")
        
        # Determine if it's a match
        is_match = relevance_score >= threshold
        
        # Extract detected role (use email subject as best guess if available)
        detected_role_text = clean_subj if email_subject else extract_potential_role(resume_text)
        if not detected_role_text:
            detected_role_text = jd_title  # Fallback to JD title
        
        return {
            "detected_role": detected_role_text,
            "source": "zero_shot_classification",
            "is_match": is_match,
            "similarity": round(relevance_score, 2),
            "jd_title": jd_title
        }
        
    except Exception as e:
        logger.error(f"Zero-Shot Classification Error: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback: Give benefit of doubt
        return {
            "detected_role": "Error", 
            "source": "error", 
            "is_match": True, 
            "similarity": 0.0, 
            "jd_title": jd_title
        }


# Legacy function kept for backward compatibility (not used anymore)
def get_text_embedding(text: str) -> Optional[np.ndarray]:
    """Deprecated: Kept for backward compatibility"""
    return None


def calculate_semantic_similarity(
    role1_text: str = None, 
    role2_text: str = None,
    role1_embedding: np.ndarray = None,
    role2_embedding: np.ndarray = None
) -> float:
    """Deprecated: Kept for backward compatibility"""
    return 0.0
