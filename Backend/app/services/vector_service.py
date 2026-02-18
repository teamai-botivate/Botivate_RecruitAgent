
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

    def search(self, query: str, k: int = 5, filter: dict = None):
        """Perform semantic search."""
        return self.db.similarity_search_with_score(query, k=k, filter=filter)

    def check_semantic_skills(
        self, 
        resume_text: str, 
        skills: list[str], 
        threshold: float = 0.38,
        precomputed_skill_vectors: dict = None
    ) -> tuple[list, list]:
        """
        Hybrid Check:
        1. Exact Substring Match (Fast & 100% accurate for explicit skills)
        2. Vector Semantic Match (Backup for implied skills)
        
        Args:
            precomputed_skill_vectors: Dict {skill_name: numpy_vector} (Optional Optimization)
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
            return list(found), []
            
        # 2. Semantic Backup (Vector Search) for tricky/implied skills
        # Smart Splitter: Handle Bullets, Newlines, Pipes
        # Standard period split misses list items.
        raw_chunks = re.split(r'[.\n•●▪➢|]', resume_text)
        sentences = [s.strip() for s in raw_chunks if len(s.strip()) > 15]
        
        if not sentences:
             return list(found), missing_candidates
             
        try:
            # Embed Resume Sentences (Unavoidable per candidate)
            sent_vecs = self.embeddings.embed_documents(sentences)
            
            # Prepare Skill Vectors
            # Use Pre-Computed if available, else Compute
            skill_vecs = []
            
            if precomputed_skill_vectors:
                # Optimized Path
                for skill in missing_candidates:
                    vec = precomputed_skill_vectors.get(skill)
                    if vec is None:
                        # Fallback compute if missing from cache
                        vec = self.embeddings.embed_query(skill)
                    skill_vecs.append(vec)
            else:
                # Slow Path (Re-Compute every time)
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
                # Optimization: Matrix Multiplication (Dot Product)
                similarities = np.dot(sent_matrix, skill_vec)
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

    def check_existing_hashes(self, hashes: list[str]) -> set:
        """
        Check which of the provided hashes already exist in the vector store.
        Returns a set of existing hashes.
        """
        if not self.db or not hashes:
            return set()
            
        try:
            # Efficiently query metadata for these hashes
            # Chroma 'get' supports filtering
            result = self.db.get(
                where={"file_hash": {"$in": hashes}},
                include=["metadatas"]
            )
            
            existing = set()
            for meta in result['metadatas']:
                if meta and 'file_hash' in meta:
                    existing.add(meta['file_hash'])
            return existing
            
        except Exception as e:
            # If DB is empty or error, assume nothing exists
            return set()

    def reset(self):
        """
        Deprecated: Do NOT clear the DB anymore. 
        We use persistent updates now.
        Just log a warning if called.
        """
        pass

vector_service = VectorService()
