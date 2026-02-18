
from ..core.config import get_settings
from .utils import extract_years_of_experience, extract_education_level, extract_keywords
import re

settings = get_settings()

def calculate_score(resume_text: str, jd_data: dict, semantic_score: float, page_count: int = 1) -> dict:
    # --- 1. STRICT REJECTION RULES (User Defined) ---
    cand_years = extract_years_of_experience(resume_text)
    
    breakdown = {
        "is_rejected": False,
        "rejection_reason": "",
        "semantic_score": semantic_score, # 0.0-1.0
        "keyword_score": 0,
        "experience_score": 0,
        "struct_score": 0,
        "total": 0,
        "matched_keywords": [],
        "missing_keywords": [],
        "years": cand_years
    }
    
    if cand_years < 3:
        # Junior (< 3 Years) -> Max 1 Page
        if page_count > 1:
            breakdown["is_rejected"] = True
            breakdown["rejection_reason"] = f"REJECTED: Junior (<3y) must be 1 Page. Has {page_count}."
            return breakdown
    else:
        # Senior (>= 3 Years) -> Max 2 Pages
        if page_count > 2:
            breakdown["is_rejected"] = True
            breakdown["rejection_reason"] = f"REJECTED: Senior (>=3y) must be Max 2 Pages. Has {page_count}."
            return breakdown

    # --- 2. ATS SCORE CALCULATION (PURE SEMANTIC + EXPERIENCE) ---
    
    # A. Semantic Match (70 Points) - Context & Meaning
    score_semantic = semantic_score * 70
    
    # B. Keyword Analysis (0 Points) - Display Only (Smart Search)
    jd_kws = set([k.lower() for k in jd_data.get("keywords", set())])
    resume_lower = resume_text.lower()
    
    matched = []
    missing = []
    
    # Smart "Semantic-ish" Check
    # Instead of strict extraction, we check if the JD concept exists in the text.
    for kw in jd_kws:
        # 1. Direct Substring (Good for multi-word like "Machine Learning")
        if len(kw.split()) > 1:
            if kw in resume_lower:
                matched.append(kw)
            else:
                missing.append(kw)
        # 2. Token Check (Good for single words to avoid "Java" matching "Javascript")
        else:
            # We use a regex word boundary check for single words accuracy
            if re.search(rf'\b{re.escape(kw)}\b', resume_lower):
                matched.append(kw)
            else:
                missing.append(kw)
                
    # C. Experience Match (30 Points) - Seniority
    req_years = jd_data.get("required_years", 0)
    if req_years == 0: req_years = 2 # Default assumption
    
    exp_ratio = min(1.0, cand_years / req_years)
    score_experience = exp_ratio * 30
    
    # B. Keyword Analysis (30 Points) - Critical Skills
    # Calculate percentage of keywords present
    if len(jd_kws) > 0:
        match_ratio = len(matched) / len(jd_kws)
    else:
        match_ratio = 0
        
    score_keywords = match_ratio * 30 # Max 30 points
        
    breakdown["matched_keywords"] = matched
    breakdown["missing_keywords"] = missing
    
    # D. Structure (0 Points) - Ignored
    score_struct = 0
    resume_lower = resume_text.lower()
    
    # --- FINAL TOTAL ---
    # Unified Formula: Semantic (40) + Keywords (30) + Experience (30)
    # This prevents Data Analysts (High Semantic, Low Keywords) from beating Backend Devs.
    score_semantic = semantic_score * 40 # Reduced from 70
    
    total_score = score_semantic + score_keywords + score_experience
    total_score = max(0, min(100, total_score)) # Clamp 0-100
    
    breakdown["total"] = round(total_score, 1)
    breakdown["keyword_score"] = round(score_keywords, 1)
    breakdown["experience_score"] = round(score_experience, 1)
    breakdown["struct_score"] = score_struct
    breakdown["semantic_points"] = round(score_semantic, 1) # For debug/display
    
    # Add legacy fields for frontend compatibility if needed
    breakdown["visual_score"] = score_struct
    breakdown["format_score"] = score_keywords 
    
    return breakdown
