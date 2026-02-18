from pydantic_settings import BaseSettings
from functools import lru_cache
import os
import configparser
from dotenv import load_dotenv

# Explicitly load .env from parent directory if not found in current
# Run from Backend/ -> .env is in ../.env
# config.py is in Backend/app/core/config.py
# 1. dirname -> Backend/app/core
# 2. dirname -> Backend/app
# 3. dirname -> Backend
# 4. dirname -> Root (Resume-Screening-Agent)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "config.ini")


class Settings(BaseSettings):
    # App Settings
    app_name: str = "Resume Ranking Agent API"
    version: str = "2.2"
    
    # Models
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    llm_model: str = "gpt-4o"
    
    # Scoring Weights (Default - Can be updated dynamically)
    keyword_weight: int = 25
    experience_weight: int = 20
    education_weight: int = 10
    location_weight: int = 10
    text_format_weight: int = 5
    visual_weight: int = 30
    
    # Thresholds
    visual_threshold: float = 40.0
    text_max_score: int = 70
    
    # Features
    enable_anonymization: bool = True
    enable_visual_analysis: bool = True
    enable_semantic_search: bool = True
    enable_skill_exp: bool = True
    enable_project_complexity: bool = True
    
    # Paths (Flexible)
    data_dir: str = "data"
    resume_dir: str = "data/resumes"
    db_persist_dir: str = "chroma_db"
    
    # API Keys
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    huggingface_api_token: str = os.getenv("HUGGINGFACE_API_TOKEN", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

    # Models (override default)
    llm_model: str = "gpt-4o"


    class Config:
        env_file = ".env"
        extra = "ignore"

    def load_from_ini(self, ini_path: str = "config.ini"):
        """Load settings from an INI file to override defaults."""
        if not os.path.exists(ini_path):
            return
            
        config = configparser.ConfigParser()
        config.read(ini_path, encoding='utf-8')
        
        if 'scoring' in config:
            self.keyword_weight = config.getint('scoring', 'keyword_match_weight', fallback=self.keyword_weight)
            self.experience_weight = config.getint('scoring', 'experience_weight', fallback=self.experience_weight)
            self.education_weight = config.getint('scoring', 'education_weight', fallback=self.education_weight)
            self.text_format_weight = config.getint('scoring', 'text_format_weight', fallback=self.text_format_weight)
            self.visual_weight = config.getint('scoring', 'visual_analysis_weight', fallback=self.visual_weight)
            self.location_weight = config.getint('scoring', 'location_weight', fallback=self.location_weight)
            
        if 'advanced' in config:
            self.enable_anonymization = config.getboolean('advanced', 'enable_anonymization', fallback=self.enable_anonymization)

@lru_cache()
def get_settings():
    settings = Settings()
    # Try loading from parent dir config.ini if exists
    if os.path.exists("../config.ini"):
        settings.load_from_ini("../config.ini")
    elif os.path.exists("config.ini"):
        settings.load_from_ini("config.ini")
    return settings
