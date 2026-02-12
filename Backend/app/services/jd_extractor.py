
import json
import logging
import re
from typing import List, Optional
from pydantic import BaseModel
from .ai_service import ai_service # Use existing singleton instance

# Define Pydantic Models for Output Validation
class ExtractedJD(BaseModel):
    job_title: str
    technical_skills: List[str] # Crucial: Clean List
    soft_skills: List[str]
    required_years_experience: int
    education_level: str
    responsibilities: List[str]
    summary_for_vector_search: str

class JDExtractor:
    def __init__(self):
        # We use the imported singleton instance
        self.ai_service = ai_service
        self.logger = logging.getLogger(__name__)

    async def extract_structured_jd(self, jd_text: str) -> ExtractedJD:
        """
        Extract structured data from raw JD using LLM (One-Time Cost).
        """
        self.logger.info("🧠 Extracting structured JD data via LLM...")
        
        prompt = f"""
        You are an expert Technical Recruiter. Extract key requirements from this Job Description.
        
        JOB DESCRIPTION:
        {jd_text[:3000]}
        
        TASK:
        Return a Strict JSON object with the following fields:
        1. "job_title": The role title.
        2. "technical_skills": A clean list of HARD skills only (e.g., "Python", "React", "AWS", "SQL"). DO NOT include generic words like "proficiency" or "strong".
        3. "soft_skills": A list of soft skills (e.g., "Communication", "Leadership").
        4. "required_years_experience": An integer representing the MINIMUM years required. If not mentioned, return 0. (e.g., "3+ years" -> 3).
        5. "education_level": "Bachelors", "Masters", "PhD", or "Any".
        6. "responsibilities": Top 3-5 key responsibilities.
        7. "summary_for_vector_search": A concise paragraph combining Title, Technical Skills, and Responsibilities. This will be used to generate the embedding for semantic search.
        
        OUTPUT JSON:
        {{
            "job_title": "...",
            "technical_skills": ["..."],
            "soft_skills": ["..."],
            "required_years_experience": 2,
            "education_level": "...",
            "responsibilities": ["..."],
            "summary_for_vector_search": "..."
        }}
        """
        
        try:
            # Call AI Service with JSON Mode
            response_json_str = self.ai_service.query(prompt, temperature=0.1, json_mode=True)
            
            # Groq JSON Mode returns clean JSON string
            data = json.loads(response_json_str)
            
            # Validate with Pydantic
            extracted = ExtractedJD(**data)
            self.logger.info(f"✅ Extracted JD: {extracted.job_title} | Skills: {len(extracted.technical_skills)}")
            return extracted
            
        except Exception as e:
            self.logger.error(f"Failed to extract JD structure: {e}")
            # Fallback
            return ExtractedJD(
                job_title="Unknown Role",
                technical_skills=[],
                soft_skills=[],
                required_years_experience=0,
                education_level="Any",
                responsibilities=[],
                summary_for_vector_search=jd_text[:500]
            )

# Create Singleton
jd_extractor = JDExtractor()
