
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from ..core.config import get_settings
import os
import shutil

settings = get_settings()

class VectorService:
    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(model_name=settings.embedding_model)
        self.persist_directory = settings.db_persist_dir
        
        # Ensure directory exists or create fresh instance
        if not os.path.exists(self.persist_directory):
            os.makedirs(self.persist_directory)
            
        self.db = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=self.embeddings
        )

    def add_texts(self, texts, metadatas):
        """Add documents to the vector store."""
        return self.db.add_texts(texts=texts, metadatas=metadatas)

    def search(self, query: str, k: int = 5):
        """Perform semantic search."""
        return self.db.similarity_search_with_score(query, k=k)

    def check_semantic_skills(self, resume_text: str, skills: list[str], threshold: float = 0.38) -> tuple[list, list]:
        """
        Hybrid Check:
        1. Exact Substring Match (Fast & 100% accurate for explicit skills)
        2. Vector Semantic Match (Backup for implied skills)
        """
        if not skills:
            return [], []
            
        import re
        import numpy as np
        
        found = set()
        missing_candidates = []
        resume_lower = resume_text.lower()
        
        # 1. Fast Text Match
        for skill in skills:
            # Check if skill exists solely as a substring (simple but effective for tech skills)
            # Use strict word boundary for short skills (<4 chars) like "Go", "C", "R"
            if len(skill) < 4:
                if re.search(rf'\b{re.escape(skill.lower())}\b', resume_lower):
                    found.add(skill)
                else:
                    missing_candidates.append(skill)
            else:
                if skill.lower() in resume_lower:
                    found.add(skill)
                else:
                    missing_candidates.append(skill)
        
        # If everything found, return early
        if not missing_candidates:
            return skills, []
            
        # 2. Semantic Backup (Vector Search) for tricky/implied skills
        # Smart Splitter: Handle Bullets, Newlines, Pipes
        # Standard period split misses list items.
        raw_chunks = re.split(r'[.\n•●▪➢|]', resume_text)
        sentences = [s.strip() for s in raw_chunks if len(s.strip()) > 15]
        
        if not sentences:
             return list(found), missing_candidates
             
        try:
            sent_vecs = self.embeddings.embed_documents(sentences)
            skill_vecs = self.embeddings.embed_documents(missing_candidates)
            
            # Convert to numpy
            sent_matrix = np.array(sent_vecs)
            sent_norms = np.linalg.norm(sent_matrix, axis=1, keepdims=True)
            sent_matrix = sent_matrix / (sent_norms + 1e-9)
            
            for i, skill in enumerate(missing_candidates):
                skill_vec = np.array(skill_vecs[i])
                skill_norm = np.linalg.norm(skill_vec)
                skill_vec = skill_vec / (skill_norm + 1e-9)
                
                # Check against ALL sentences
                similarities = np.dot(skill_vec, sent_matrix.T)
                best_match_score = np.max(similarities)
                
                if best_match_score >= threshold:
                    found.add(skill)
                    
        except Exception as e:
            print(f"Semantic Check Error: {e}")
            # Fallback to just text match results
            
        # Calculate final missing based on original set
        final_found = list(found)
        final_missing = [s for s in skills if s not in found]
        
        return final_found, final_missing

    def reset(self):
        """Clear the vector database completely."""
        try:
            # Delete collection content
            if self.db:
                try:
                    self.db.delete_collection()
                except Exception as e:
                    pass # Collection might not exist, ignore
            
            self.db = None
            
            # Re-initialize clean
            self.db = Chroma(
                persist_directory=self.persist_directory,
                embedding_function=self.embeddings
            )
        except Exception as e:
            print(f"Vector DB Reset Error: {e}")

vector_service = VectorService()
