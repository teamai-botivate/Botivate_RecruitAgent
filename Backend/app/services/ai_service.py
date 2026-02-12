import os
import json
from groq import Groq
from ..core.config import get_settings

settings = get_settings()

class AIService:
    def __init__(self):
        # Fallback to OpenAI if Groq is missing, but prefer Groq
        if settings.groq_api_key:
            self.client = Groq(api_key=settings.groq_api_key)
            self.provider = "groq"
        else:
            from openai import OpenAI
            self.client = OpenAI(api_key=settings.openai_api_key)
            self.provider = "openai"
            
        self.model = settings.llm_model # "llama-3.3-70b-versatile"

    def query(self, prompt: str, temperature: float = 0.3, json_mode: bool = False) -> str:
        try:
            kwargs = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a helpful HR assistant designed to analyze resumes. " + ("You MUST output valid JSON." if json_mode else "")},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature,
                "max_tokens": 2000,
            }
            
            if json_mode:
                if self.provider == "groq":
                    kwargs["response_format"] = {"type": "json_object"}
                else:
                    kwargs["response_format"] = {"type": "json_object"}

            completion = self.client.chat.completions.create(**kwargs)
            return completion.choices[0].message.content.strip()
        except Exception as e:
            print(f"AI API Error ({self.provider}): {e}")
            return ""

    def anonymize(self, text: str) -> str:
        prompt = f"""
        Task: Anonymize the following resume text.
        Instructions:
        1. Replace the Candidate Name with [CANDIDATE_NAME].
        2. Replace Email Address with [EMAIL].
        3. Replace Phone Number with [PHONE].
        4. Replace Address/Location with [LOCATION] (unless it's just a city/country).
        5. Replace University Names (e.g. 'Harvard University') with [UNIVERSITY].
        6. DO NOT remove Skills, Experience, Projects, or Job Titles.
        7. Return ONLY the anonymized text. Do not add any preamble.
        
        Resume Text:
        {text[:2500]}
        """
        return self.query(prompt, temperature=0.1)

    def extract_location(self, text: str) -> str:
        prompt = f"""
        Extract the target Job Location (City/Country/Remote) from this Job Description.
        If Remote, return 'Remote'.
        If multiple locations, return the primary one.
        Return ONLY the location string.
        
        Job Description:
        {text[:1000]}
        """
        return self.query(prompt, temperature=0.1).strip()

ai_service = AIService()
