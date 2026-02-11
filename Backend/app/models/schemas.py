
from pydantic import BaseModel
from typing import List, Dict, Optional, Any

class JDRequest(BaseModel):
    text: str
    
class AnalysisResponse(BaseModel):
    filename: str
    rank: int
    total_score: float
    breakdown: Dict[str, float]  # Keyword, Experience, Education, etc.
    ai_reasoning: Optional[str]
    content_preview: Optional[str]

class ConfigUpdate(BaseModel):
    keyword_weight: Optional[int]
    experience_weight: Optional[int]
    education_weight: Optional[int]
    location_weight: Optional[int]
    visual_weight: Optional[int]

class ProcessingStatus(BaseModel):
    total_files: int
    processed_count: int
    status: str

# LLM Analysis Models
class CandidateAnalysis(BaseModel):
    filename: str
    candidate_name: str
    status: str # "Recommended", "Potential", or "Rejected"
    reasoning: str
    strengths: List[str]
    weaknesses: List[str]
    hobbies_and_achievements: Optional[List[str]] = []

class LLMOutput(BaseModel):
    candidates: List[CandidateAnalysis]
