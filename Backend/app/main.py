
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict, Optional
import shutil
import os
import uuid
import json
import logging
import asyncio
import warnings
import re
from datetime import datetime
warnings.filterwarnings("ignore", category=DeprecationWarning)

from .core.config import get_settings
from .services import pdf_service, vector_service, ai_service, utils
from .services.gmail_fetch_service import gmail_fetch_service
from .services.jd_extractor import jd_extractor
from .services.score_service import calculate_score
from .models.schemas import LLMOutput, JobStatusResponse

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("backend.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("ResumeAgent")

from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Resume Screening Agent API (Async)", version="3.3")

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Reports for Static Access
os.makedirs("Reports", exist_ok=True)
app.mount("/reports", StaticFiles(directory="Reports"), name="reports")

settings = get_settings()

# --- JOB MANAGER (In-Memory for MVP) ---
# In production, use Redis.
jobs: Dict[str, Dict] = {}

def update_job_progress(job_id: str, progress: int, step: str):
    if job_id in jobs:
        jobs[job_id]["progress"] = progress
        jobs[job_id]["current_step"] = step
        logger.info(f"[Job {job_id}] {progress}% - {step}")

def fail_job(job_id: str, error: str):
    if job_id in jobs:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = error
        logger.error(f"[Job {job_id}] FAILED: {error}")

def complete_job(job_id: str, result: dict):
    if job_id in jobs:
        jobs[job_id]["status"] = "completed"
        jobs[job_id]["progress"] = 100
        jobs[job_id]["current_step"] = "Analysis Complete"
        jobs[job_id]["result"] = result
        logger.info(f"[Job {job_id}] COMPLETED Successfully.")

# --- CORE PIPELINE (Async Worker) ---
async def _run_async_analysis(job_id: str, jd_text: str, source_dir: str, top_n: int, jd_source_name: str, gmail_metadata: Dict = {}):
    try:
        update_job_progress(job_id, 5, "Initializing Pipeline...")
        
        # 2. PROCESS JOB DESCRIPTION (LLM Extraction)
        update_job_progress(job_id, 10, "Extracting Requirements from JD (LLM)...")
        # Use LLM to get structured data
        jd_struct = await jd_extractor.extract_structured_jd(jd_text)
        
        # Use the LLM's clean summary for vector search (High Signal)
        jd_clean = jd_struct.summary_for_vector_search
        
        jd_data = {
            "title": jd_struct.job_title,
            "text": jd_clean,
            "keywords": jd_struct.technical_skills, # Clean List!
            "required_years": jd_struct.required_years_experience,
            "education": jd_struct.education_level
        }
        
        logger.info(f"✅ JD Processed: {jd_data['title']} | Exp: {jd_data['required_years']}y | Skills: {len(jd_data['keywords'])}")
        
        # 2. FILE INGESTION (Parallel Stream)
        import hashlib
        import concurrent.futures

        # Scan the temp directory for files
        all_files = [f for f in os.listdir(source_dir) if os.path.isfile(os.path.join(source_dir, f))]
        total_files = len(all_files)
        
        if total_files == 0:
            fail_job(job_id, "No files found to process.")
            return

        resume_texts = {}
        resume_pages = {}
        processed_candidates = []
        file_hashes = {}  # Store {filename: md5_hash}
        
        # Batch Process to prevent Memory Spikes
        update_job_progress(job_id, 15, f"Parsing {total_files} Resumes (Parallel)...")
        
        def process_single_file(fname):
            """Worker function for parallel processing"""
            file_path = os.path.join(source_dir, fname)
            try:
                # Read Content
                if fname.lower().endswith(".pdf"):
                    with open(file_path, "rb") as f:
                        file_bytes = f.read()
                        text, pages = pdf_service.pdf_service.extract_text(file_bytes)
                else:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        file_bytes = f.read().encode('utf-8')
                        text = f.read()
                        pages = 1
                
                # Calculate Hash
                file_hash = hashlib.md5(file_bytes).hexdigest()
                
                # Extract Email (Advanced + Regex Fallback)
                extracted_email = ""
                if fname.lower().endswith(".pdf"):
                    try:
                         extracted_email = pdf_service.pdf_service.extract_emails_advanced(file_bytes)
                    except Exception as e:
                        print(f"Advanced Email Extraction Error for {fname}: {e}")

                if not extracted_email:
                    # Fallback to Regex on text
                    email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
                    extracted_email = email_match.group(0) if email_match else ""
                
                # DEBUG LOG
                print(f"   🕵️ DEBUG: Extracted Email for {fname}: '{extracted_email}'")
                
                clean_text = utils.clean_text(text)
                
                # IMMEDIATE SCORING (Pass 1 - The Fast Scan)
                score_data = calculate_score(clean_text, jd_data, semantic_score=0.0, page_count=pages)
                
                return {
                    "status": "success",
                    "fname": fname,
                    "text": clean_text,
                    "pages": pages,
                    "hash": file_hash,
                    "score_data": score_data,
                    "email": extracted_email
                }
            except Exception as e:
                return {"status": "error", "fname": fname, "error": str(e)}

        # Run Parallel
        processed_filenames = set()
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            future_to_file = {executor.submit(process_single_file, f): f for f in all_files}
            
            for idx, future in enumerate(concurrent.futures.as_completed(future_to_file)):
                result = future.result()
                fname = result['fname']
                
                if result['status'] == 'error':
                    logger.error(f"Error reading {fname}: {result['error']}")
                    continue
                
                # Success
                text = result['text']
                pages = result['pages']
                score_data = result['score_data']
                file_hashes[fname] = result['hash']
                
                resume_texts[fname] = text
                resume_pages[fname] = pages
                
                logger.info(f"   📄 Parsed: {fname} ({len(text)} chars) | Pages: {pages}")

                # STRICT EMAIL LOGIC: Only from PDF Content
                final_email = result['email']
                
                # if not final_email and gmail_metadata... REMOVED AS REQUESTED

                # Prevent Duplicates
                if fname in processed_filenames:
                    continue
                processed_filenames.add(fname)

                if score_data.get("is_rejected"):
                     reason = score_data.get("rejection_reason", "Unknown")
                     logger.warning(f"   ❌ REJECTED (Hard Rule): {fname} | Reason: {reason}")
                     processed_candidates.append({
                         "filename": fname,
                         "name": utils.extract_name(text, fname),
                         "score": score_data, 
                         "status": "Rejected",
                         "file_hash": result['hash'],
                         "email": final_email
                     })
                else:
                    processed_candidates.append({
                        "filename": fname,
                         "name": utils.extract_name(text, fname),
                         "score": score_data,
                         "text": text,
                         "status": "Pending",
                         "extracted_skills": score_data.get('matched_keywords', []),
                         "years_of_experience": 0.0,
                        "file_hash": result['hash'],
                         "email_subject": gmail_metadata.get(fname, {}).get("email_subject", ""),
                         "email_body": gmail_metadata.get(fname, {}).get("email_body", ""),
                         "email": final_email
                    })
                
                # Progress Update
                if idx % 5 == 0:
                    prog = 15 + int((idx / total_files) * 35) 
                    update_job_progress(job_id, prog, f"Parsed {idx+1}/{total_files} Resumes")


        # 3. VECTOR ANALYSIS (PURE SEMANTIC - ALL VALID CANDIDATES)
        # Ensure Update Job Store with Initial Parse Results (CRITICAL FIX)
        jobs[job_id]["candidates"] = processed_candidates

        # Filter strictly those who passed the Page Check
        valid_candidates = [c for c in processed_candidates if not c['score'].get('is_rejected', False)]
        rejected_candidates = [c for c in processed_candidates if c['score'].get('is_rejected', False)]
        
        logger.info(f"   🛑 Pass 1 (Page Filter) Complete: {len(processed_candidates)} Processed. (Valid: {len(valid_candidates)})")
        if rejected_candidates:
             logger.info(f"      ❌ Rejected (Page Filter): {[c['filename'] for c in rejected_candidates]}")

        # 3. PASS 2: ROLE FILTERING (Semantic - Zero Cost)
        # Filter resumes by job title match BEFORE expensive AI analysis
        from .services.role_matcher import detect_and_match_role, get_text_embedding
        
        # Use LLM extracted title directly
        jd_title = jd_data.get("title", "Unknown Role")
        
        logger.info(f"   🎯 Pass 2: Filtering resumes for role '{jd_title}'...")
        
        # OPTIMIZATION: Embed JD Title ONCE to save time
        jd_title_vector = get_text_embedding(jd_title)

        role_matched = []
        role_skipped = []
        role_unclear = []
        
        for candidate in valid_candidates:
            # Detect role from email + resume
            try:
                match_result = detect_and_match_role(
                    jd_title=jd_title,
                    email_subject=candidate.get('email_subject', ''),
                    email_body=candidate.get('email_body', ''),
                    resume_text=candidate['text'],
                    threshold=0.6,  # Zero-shot classification threshold (higher = stricter)
                    jd_title_embedding=jd_title_vector # PASS PRE-COMPUTED VECTOR
                )
            except Exception as e:
                logger.error(f"Role Match Error for {candidate['filename']}: {e}")
                match_result = {"is_match": True, "detected_role": "Error", "similarity": 0.0}
            
            # Store detection metadata
            candidate['applied_for'] = match_result.get('detected_role') or "Unknown"
            candidate['role_match'] = match_result
            
            # Categorize
            if match_result['is_match']:
                role_matched.append(candidate)
            elif match_result['detected_role']:
                role_skipped.append(candidate)
                candidate['score']['is_rejected'] = True
                candidate['score']['rejection_reason'] = f"ROLE MISMATCH: Applied for '{match_result['detected_role']}' but JD is for '{jd_title}'"
            else:
                # If we can't detect role, give them a chance (process as normal)
                role_unclear.append(candidate)
        
        logger.info(f"   📊 Role Filter: ✅ {len(role_matched)} matched | ❌ {len(role_skipped)} skipped (wrong role) | ⚠️ {len(role_unclear)} unclear")
        if role_matched:
             logger.info(f"      ✅ Matched: {[c['filename'] for c in role_matched]}")
        if role_skipped:
             logger.info(f"      ❌ Skipped: {[c['filename'] for c in role_skipped]}")
        if role_unclear:
             logger.info(f"      ⚠️ Unclear: {[c['filename'] for c in role_unclear]}")
        
        # Combine matched + unclear for further processing
        vector_candidates = role_matched + role_unclear

        update_job_progress(job_id, 30, "Semantic Analysis (Whole JD vs Resumes)...")
        
        if not vector_candidates:
             logger.warning("No candidates passed the Role Filter.")
        else:
            logger.info(f"   🧠 Running Pure Semantic Match on {len(vector_candidates)} candidates...")
            
            try:
                # 1. Identify which files need embedding (New Hashes)
                candidate_hashes = [c['file_hash'] for c in vector_candidates]
                existing_hashes = vector_service.vector_service.check_existing_hashes(candidate_hashes)
                
                new_docs = []
                new_metas = []
                
                for c in vector_candidates:
                    if c['file_hash'] not in existing_hashes:
                        new_docs.append(c['text'])
                        new_metas.append({
                            "filename": c['filename'], 
                            "file_hash": c['file_hash']
                        })
                
                # 2. Add ONLY new texts
                if new_docs:
                    logger.info(f"   📥 Embedding {len(new_docs)} new resumes into Vector DB...")
                    vector_service.vector_service.add_texts(new_docs, new_metas)
                else:
                    logger.info("   ⏩ All resumes already in Vector DB. Skipping embedding.")
                
                # 3. Search matched results (SCOPED to current candidates)
                candidate_filenames = [c['filename'] for c in vector_candidates]
                
                # Create Filter to ignore global DB noise
                if len(candidate_filenames) == 1:
                    search_filter = {"filename": candidate_filenames[0]}
                else:
                    search_filter = {"filename": {"$in": candidate_filenames}}
                
                results = vector_service.vector_service.search(
                    jd_clean, 
                    k=len(vector_candidates),
                    filter=search_filter
                )
                
                # Debug: Log raw distances
                debug_raw_scores = [(doc.metadata['filename'], score) for doc, score in results]
                logger.info(f"   📊 Raw Vector Distances: {debug_raw_scores}")
                
                # Map Results {filename: distance}
                # Chroma Cosine Distance: 0 to 2. 
                # 0 = Identical, 1 = Orthogonal, 2 = Opposite.
                # Formula: Similarity = 1 - (distance / 2) -> Maps 0..2 to 1..0
                sem_map = {}
                for doc, dist in results:
                    sim = max(0.0, 1.0 - (dist / 2))
                    sem_map[doc.metadata['filename']] = sim

                # OPTIMIZATION: Pre-compute Skill Vectors ONCE
                jd_keywords = jd_data.get('keywords', [])
                skill_vectors_cache = {}
                if jd_keywords:
                    try:
                        logger.info(f"   ⚡ Pre-computing vectors for {len(jd_keywords)} skills...")
                        # Batch embed all skills
                        _vecs = vector_service.vector_service.embeddings.embed_documents(jd_keywords)
                        # Create Map {skill: vector}
                        skill_vectors_cache = {k: v for k, v in zip(jd_keywords, _vecs)}
                    except Exception as e:
                        logger.error(f"Skill Vector Pre-compute Failed: {e}")

                for c in vector_candidates:
                    fname = c['filename']
                    
                    # 1. Document-Level Semantic Score
                    final_sem_score = sem_map.get(fname, 0.0)
                    if final_sem_score == 0.0:
                        logger.warning(f"   ⚠️ Semantic Score 0.0 for {fname}. Dist > 2.2?")

                    # 2. Skill-Level Semantic Check (Slower but Precise)
                    full_text = resume_texts.get(fname, "")
                    
                    try:
                        # Pass the pre-computed cache
                        found_skills, missing_skills = vector_service.vector_service.check_semantic_skills(
                            full_text, 
                            jd_keywords, 
                            threshold=0.45,
                            precomputed_skill_vectors=skill_vectors_cache
                        )
                    except Exception as e:
                        logger.error(f"   ⚠️ Skill Check Error for {fname}: {e}")
                        found_skills, missing_skills = [], jd_keywords
                    
                    # 3. Update Scoring Data
                    c['score']['matched_keywords'] = found_skills
                    c['score']['missing_keywords'] = missing_skills
                    
                    c['score']['semantic_score'] = final_sem_score
                    c['score']['semantic_points'] = round(final_sem_score * 70, 1)
                    
                    # 4. Final Total Calculation (70 Sem + 30 Exp)
                    # Note: Key/Struct scores are 0 by default now.
                    exp_score = c['score'].get('experience_score', 0)
                    
                    new_total = c['score']['semantic_points'] + exp_score
                    c['score']['total'] = round(min(100, new_total), 1)
                    
                    logger.info(f"   🧠 {fname} | Final: {c['score']['total']} (Sem: {final_sem_score:.2f}, Exp: {exp_score})")
                    if found_skills:
                        logger.info(f"      ✅ Semantic Found: {len(found_skills)}/{len(jd_data['keywords'])} ({', '.join(found_skills[:5])}...)")
                    else:
                        logger.info("      ❌ No Skills Found Semantically.")

            except Exception as e:
                logger.error(f"Vector Analysis Failed: {str(e)}")
                # Fallback
                for c in vector_candidates:
                    c['score']['total'] = 0

        # Re-Sort Final List
        # Re-Sort Final List (Using Filtered Role Match Candidates Only)
        vector_candidates.sort(key=lambda x: x['score']['total'], reverse=True)
        top_candidates = vector_candidates[:top_n]
        remaining = vector_candidates[top_n:]

        update_job_progress(job_id, 75, f"Identified Top {len(top_candidates)} Candidates. Running AI Analysis...")

        # 4. AI ANALYSIS (Pass 3 - The Deep Dive)
        # Smart Selection: Analyze Top N + 2 candidates (Conservative to avoid Rate Limits)
        analysis_limit = min(15, top_n + 5) 
        if len(vector_candidates) < analysis_limit:
            ai_target = vector_candidates
            not_analyzed = []
        else:
            ai_target = vector_candidates[:analysis_limit]
            not_analyzed = vector_candidates[analysis_limit:]
        
        # Mark candidates with analysis flags
        for candidate in ai_target:
            candidate['ai_analyzed'] = True
            candidate['analysis_method'] = 'full_ai'
        
        for candidate in not_analyzed:
            candidate['ai_analyzed'] = False
            candidate['analysis_method'] = 'similarity_only'
            # Keep basic data but no AI reasoning
            if 'reasoning' not in candidate:
                candidate['reasoning'] = None

        logger.info(f"   🎯 Pass 3: Selecting Top {len(ai_target)} for AI Analysis (Buffer: {analysis_limit} vs Request: {top_n}).")
        if not_analyzed:
            logger.info(f"   📊 Skipping AI for {len(not_analyzed)} candidates (ranked by similarity only)")
        
        img_analysis = []
        
        # INDIVIDUAL PROCESSING (1 Resume = 1 AI Call)
        BATCH_SIZE = 1
        import time 

        for i in range(0, len(ai_target), BATCH_SIZE):
            batch = ai_target[i : i+BATCH_SIZE]
            c = batch[0] # Single candidate
            logger.info(f"   🤖 Processing AI for: {c['filename']}...")
            
            # TOKEN SAVING: Truncate very long resumes to ~6000 chars (approx 1500 tokens)
            source_text = c['text']
            if len(source_text) > 8000:
                logger.warning(f"   ⚠️ Resume too long ({len(source_text)} chars). Truncating to 8000.")
                source_text = source_text[:8000] + "\n[...Truncated...]"

            anon_text = ai_service.ai_service.anonymize(source_text) 
            
            # LOG EXTRACTED TEXT PREVIEW (With Exp Info)
            raw_exp = c['score'].get('years_of_experience', 0)
            logger.info(f"   📄 [DEBUG] {c['filename']} | Base Exp: {raw_exp}y | Full Text Len: {len(anon_text)}")
            
            prompt = f"""
            You are a Senior Technical Recruiter. Analyze this candidate for the Job Description below.
            
            JD Summary: {jd_clean[:1500]}
            
            CANDIDATE:
            Filename: {c['filename']}
            Score: {c['score']['total']}
            Content:
            {anon_text}
            
            INSTRUCTIONS:
            1. Evaluate relevance to the JD (Skills, Experience, Role Fit).
            2. EXTRACT DETAILS (CRITICAL):
               - "years_of_experience": Calculate ONLY from professional work history dates.
                 * DO NOT count University/College duration as work experience.
                 * Count Internships if labeled clearly.
               - "extracted_skills": List of technical skills actually found.
               - "email" and "phone": Extract EXACT text found. If not found, return "Not Found".
             3. LOOK FOR HIDDEN GEMS: Check for Hackathons, Open Source (GitHub), Awards, Publications.
             4. Assign "achievement_bonus" (0-20 points) for exceptional achievements.
             5. "hobbies_and_achievements": A list of hobbies or key achievements. Return [] if none found.
             6. "reasoning": A 1-line explanation of why this candidate was selected or rejected.

            OUTPUT FORMAT (Strict JSON):
            {{
              "candidates": [
                {{
                  "filename": "{c['filename']}", 
                  "candidate_name": "Name",
                  "email": "email@example.com",
                  "phone": "+91...",
                  "years_of_experience": 3.5,
                  "extracted_skills": ["Python", "AWS", ...],
                  "status": "High Potential",
                  "achievement_bonus": 15,
                  "reasoning": "...",
                  "strengths": ["..."],
                  "weaknesses": ["..."],
                  "hobbies_and_achievements": []
                }}
              ]
            }}
            Ensure the JSON is valid.
            """
            
            max_retries = 2
            success = False
            
            for attempt in range(max_retries):
                try:
                    # Call LLM (Strict Mode: temp=0)
                    llm_response = ai_service.ai_service.query(prompt, json_mode=True, temperature=0.0)
                    
                    # LOG RAW RESPONSE
                    # logger.info(f"   🤖 [DEBUG] AI Raw JSON Response:\n{llm_response}\n")
                    
                    # Parse Result
                    json_str = llm_response
                    match = re.search(r"```json(.*?)```", llm_response, re.DOTALL)
                    if match: json_str = match.group(1).strip()
                    elif "{" in llm_response:
                        s = llm_response.find("{")
                        e = llm_response.rfind("}")
                        json_str = llm_response[s:e+1]
                    
                    parsed = LLMOutput.model_validate_json(json_str)
                    
                    # Ensure filename match (AI sometimes forgets)
                    if parsed.candidates:
                        parsed.candidates[0].filename = c['filename']
                        batch_results = [parsed.candidates[0].model_dump()]
                        img_analysis.extend(batch_results)
                        logger.info(f"      ✅ Analyzed: {c['filename']}")
                    
                    success = True
                    break 

                except Exception as e:
                    error_msg = str(e)
                    if "429" in error_msg or "Rate limit" in error_msg:
                        wait = 20 * (attempt + 1)
                        logger.warning(f"   ⚠️ Rate Limit Hit (429). Retrying in {wait}s... (Attempt {attempt+1}/{max_retries})")
                        time.sleep(wait)
                    else:
                        logger.error(f"AI Parse Error ({c['filename']}): {e}") 
                        break # Don't retry on non-rate-limit errors
            
            if not success:
               logger.warning(f"   ⚠️ Skipping AI analysis for {c['filename']} due to repeated errors. Using Base Score.")

            # Rate Limit Prevention Check
            time.sleep(1.0) # Sleep 1s between requests

        # 4b. Apply AI Results & Bonus
        if img_analysis:
            for ai_res in img_analysis:
                # Find original candidate object
                # SEARCH IN vector_candidates to ensure we update the main list directly
                target_cand = next((c for c in vector_candidates if c["filename"] == ai_res.get("filename")), None)
                
                if target_cand:
                    # SAFEGUARD: Capture Original Email
                    original_email = target_cand.get('email', '')

                    # Update Fields
                    new_name = ai_res.get('candidate_name')
                    if new_name and "CANDIDATE" not in new_name.upper() and "NAME" not in new_name.upper() and "[" not in new_name:
                         target_cand['candidate_name'] = new_name
                    
                    # ---------------------------------------------------------
                    # EMAIL LOGIC: WE DO NOT UPDATE EMAIL FROM AI
                    # PyMuPDF/Regex is authoritative. AI often returns placeholders.
                    # ---------------------------------------------------------
                    logger.info(f"      🕵️ DEBUG: AI found email '{ai_res.get('email')}' for {target_cand['filename']} but ignoring it. Keeping: '{target_cand.get('email')}'")
                    
                    target_cand['phone'] = ai_res.get('phone', target_cand.get('phone'))
                    target_cand['extracted_skills'] = ai_res.get('extracted_skills', [])
                    target_cand['status'] = ai_res.get('status', 'Review Required')
                    target_cand['reasoning'] = ai_res.get('reasoning', '')
                    target_cand['strengths'] = ai_res.get('strengths', [])
                    target_cand['weaknesses'] = ai_res.get('weaknesses', [])
                    target_cand['hobbies_and_achievements'] = ai_res.get('hobbies_and_achievements', [])

                    # Apply Achievement Bonus from AI
                    bonus = ai_res.get('achievement_bonus', 0)
                    target_cand['achievement_bonus'] = bonus
                    
                    # Update Final Score
                    current_total = target_cand['score']['total']
                    new_total = min(100, current_total + bonus)
                    target_cand['score']['total'] = round(new_total, 1)
                    
                    # Update score details for display
                    ai_exp = ai_res.get("years_of_experience", 0)
                    ai_skills = ai_res.get("extracted_skills", [])
                    
                    target_cand["score"]["years"] = ai_exp
                    target_cand["score"]["matched_keywords"] = ai_skills
                    req_years = jd_data.get("required_years", 2)
                    new_exp_score = min(30, (ai_exp / req_years) * 30) if req_years else 0
                    target_cand["score"]["experience_score"] = round(new_exp_score, 1)
                    target_cand["score"]["keyword_score"] = len(ai_skills) # Just count for display
                    
                    # FINAL RESTORE: Force Email Back
                    target_cand['email'] = original_email
                    
                    logger.info(f"   🤖 Re-Ranked {target_cand['filename']}: {current_total} -> {new_total} (Bonus: +{bonus}) | Email Kept: '{original_email}'")
        update_job_progress(job_id, 90, "Generating Final Reports...")

        # 5. GENERATE REPORTS
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        report_dir = f"Reports/Campaign_{timestamp}"
        
        # Copy files from temp to report dir (Organized)
        os.makedirs(f"{report_dir}/All_Resumes", exist_ok=True)
        # We need to copy from source_dir
        for f in all_files:
            try:
                shutil.copy2(os.path.join(source_dir, f), f"{report_dir}/All_Resumes/{f}")
            except: pass

        # Shortlisted
        os.makedirs(f"{report_dir}/Shortlisted_Resumes", exist_ok=True)
        for c in top_candidates:
            try:
                shutil.copy2(os.path.join(source_dir, c['filename']), f"{report_dir}/Shortlisted_Resumes/{c['filename']}")
            except: pass
            
        # Not Selected
        os.makedirs(f"{report_dir}/Not_Selected_Resumes", exist_ok=True)
        for c in remaining:
             try:
                shutil.copy2(os.path.join(source_dir, c['filename']), f"{report_dir}/Not_Selected_Resumes/{c['filename']}")
             except: pass



        # Prepare Final Result Payload
        # 5b. PREPARE FINAL RESULT PAYLOAD (Display Logic Only)
        # The scores and data were already updated in the AI loop above (Pass 4b).
        # This block ensures UI fields (breakdown, etc.) are populated without double-counting.
        
        updated_top_candidates = []
        for c in top_candidates:
            # Check if AI result exists for this candidate
            # We can check 'achievement_bonus' key which is set in AI loop
            is_analyzed = c.get('ai_analyzed', False)
            
            current_total = c['score']['total']
            bonus = c.get('achievement_bonus', 0)
            base_score = max(0, current_total - bonus) # Reverse calc for display
            
            if is_analyzed:
                status = c.get('status', 'Review Required')
                
                # Detailed breakdown for Frontend "View Details"
                c['score']['breakdown'] = {
                    "Base Score": round(base_score, 1),
                    "AI Bonus": bonus,
                    "Final Score": current_total,
                    "Status": status
                }
                c['score']['breakdown_text'] = f"Base: {base_score:.1f} | Bonus: {bonus:+d} | Final: {current_total:.1f}"
                
                # FALLBACK: Ensure skills are present
                if not c.get('extracted_skills'):
                    c['extracted_skills'] = c['score'].get('matched_keywords', [])

            else:
                 # No AI Analysis
                 c['score']['breakdown'] = { 
                     "Base Score": current_total, 
                     "AI Bonus": 0, 
                     "Final": current_total,
                     "Status": "Pending"
                 }
                 c['score']['breakdown_text'] = f"Base: {current_total} (No AI Analysis)"
                
            updated_top_candidates.append(c)
            
        # Re-Sort Top Candidates after AI Adjustment
        updated_top_candidates.sort(key=lambda x: x['score']['total'], reverse=True)
        
        # Sort Remaining Candidates (who didn't get AI analyzed)
        remaining.sort(key=lambda x: x['score']['total'], reverse=True)
        
        # Add basic breakdown for remaining
        for r in remaining:
             if 'breakdown' not in r['score']: 
                 r['score']['breakdown'] = { "Base Score": r['score']['total'], "AI Bonus": 0, "Final": r['score']['total'] }
                 r['score']['breakdown_text'] = f"Base: {r['score']['total']} (No AI Analysis)"
                
        # Merge lists: AI-analyzed + Not-analyzed-but-valid
        # Add not-analyzed candidates to remaining
        for na_candidate in not_analyzed:
            # Ensure they have basic score structure
            if 'breakdown' not in na_candidate['score']:
                na_candidate['score']['breakdown'] = {
                    "Base Score": na_candidate['score']['total'],
                    "AI Bonus": 0,
                    "Final": na_candidate['score']['total']
                }
                na_candidate['score']['breakdown_text'] = f"Similarity: {na_candidate.get('vector_score', 0):.2f} (Not AI analyzed)"
            remaining.append(na_candidate)
        
        # Merge lists (AI-analyzed candidates + Remaining including not-analyzed)
        final_list = updated_top_candidates + remaining
        
        # FINAL GLOBAL SORT: AI-analyzed first (by score), then not-analyzed (by vector_score)
        final_list.sort(
            key=lambda x: (
                x.get('ai_analyzed', False),  # True before False
                x['score']['total'],  # AI score
                x.get('vector_score', 0)  # Vector score as tiebreaker
            ),
            reverse=True
        )
        
        
        # --- EXPORT DATA FOR APTITUDE SYSTEM & REJECTION ---
        cutoff = int(top_n)
        true_selected = final_list[:cutoff] # Rank 1 to N
        true_rejected = final_list[cutoff:] # Rank N+1 to End

        selected_export = []
        logger.info(f"\n--- 🟢 SELECTED CANDIDATES (Top {cutoff}) ---")
        for c in true_selected:
             email = c.get("email", "")
             logger.info(f"   ✅ {c['filename']} -> Email: {email} (Score: {c['score']['total']})")
             selected_export.append({
                 "name": c.get("candidate_name", c["name"]),
                 "email": email, 
                 "role": jd_data['title'],
                 "resume": os.path.abspath(f"{report_dir}/Shortlisted_Resumes/{c['filename']}") if c.get('ai_analyzed') else ""
             })
        
        rejected_export = []
        logger.info(f"\n--- 🔴 NOT SELECTED CANDIDATES (Rank {cutoff+1}+) ---")
        for c in true_rejected:
             c['status'] = "Not Selected" # FORCE STATUS for Frontend
             email = c.get("email", "")
             logger.info(f"   ❌ {c['filename']} -> Email: {email} (Score: {c['score']['total']})")
             rejected_export.append({
                 "name": c.get("candidate_name", c["name"]),
                 "email": email,
                 "role": jd_data['title'],
                 "reason": "Not Selected (Low Score)"
             })
             
        # Save JSONs
        with open(f"{report_dir}/selected_candidates.json", "w") as f:
            json.dump(selected_export, f, indent=4)
        
        with open(f"{report_dir}/not_selected_candidates.json", "w") as f:
            json.dump(rejected_export, f, indent=4)
            
        logger.info(f"✅ Generated Handoff Files: selected_candidates.json ({len(selected_export)}) & not_selected_candidates.json ({len(rejected_export)})")
        
        # Rejections
        final_rejected = []
        for c in rejected_candidates:
            final_rejected.append({
                "filename": c['filename'],
                "name": c['name'],
                "reason": c['score'].get('rejection_reason'),
                "score": 0
            })

        result_payload = {
            "status": "success",
            "candidates": final_list,
            "rejected_count": len(final_rejected),
            "rejected_candidates": final_rejected,
            "ai_analysis": img_analysis,
            "report_path": os.path.abspath(report_dir),
            "campaign_folder": os.path.basename(report_dir)
        }

        complete_job(job_id, result_payload)
        
        # Cleanup Temp
        try:
            shutil.rmtree(source_dir)
        except: pass

    except Exception as e:
        logger.error(f"FATAL PIPELINE ERROR: {e}")
        fail_job(job_id, str(e))

# --- ENDPOINTS ---

@app.get("/")
def root():
    return {"message": "Resume Screening Agent API (Async Mode) is running."}

@app.post("/analyze")
async def start_analysis(
    background_tasks: BackgroundTasks,
    jd_file: UploadFile = File(None),
    jd_text_input: str = Form(None),
    resume_files: List[UploadFile] = File(None),
    start_date: str = Form(None),
    end_date: str = Form(None),
    top_n: int = Form(5)
):
    job_id = str(uuid.uuid4())
    logger.info(f"Starting Analysis Job: {job_id}")

    # 1. Create Job State
    jobs[job_id] = {
        "status": "processing",
        "progress": 0,
        "current_step": "Uploading Files...",
        "result": None,
        "error": None
    }

    try:
        # 2. Setup Temp Directory
        temp_dir = f"temp/analysis_{job_id}"
        os.makedirs(temp_dir, exist_ok=True)

        # 3. Handle JD
        jd_text = ""
        jd_source = ""
        
        if jd_file:
            content = await jd_file.read()
            if jd_file.filename.endswith(".pdf"):
                jd_text, _ = pdf_service.pdf_service.extract_text(content)
            else:
                jd_text = content.decode("utf-8")
            jd_source = jd_file.filename
        elif jd_text_input:
            jd_text = jd_text_input
            jd_source = "Pasted Text"
        else:
            raise HTTPException(status_code=400, detail="JD Required")

        # 4. Handle Files (Stream to Disk immediately)
        files_found = False
        gmail_metadata = {} # Initialize to avoid UnboundLocalError
        
        # Source A: Manual
        if resume_files:
            for file in resume_files:
                file_path = os.path.join(temp_dir, file.filename)
                with open(file_path, "wb") as f:
                    shutil.copyfileobj(file.file, f) # Efficient stream copy
            files_found = True
        
        # Source B: Gmail (OAuth)
        if start_date and end_date:
            update_job_progress(job_id, 2, "Checking Gmail Connection...")
            
            # Check if Gmail is connected
            if not gmail_fetch_service.is_connected():
                logger.warning("Gmail not connected. Skipping Gmail fetch.")
                raise HTTPException(
                    status_code=400,
                    detail="Gmail not connected. Please connect your Gmail account first by clicking 'Connect Gmail' button."
                )
            
            try:
                update_job_progress(job_id, 3, "Fetching Resumes from Gmail...")
                gmail_resumes = gmail_fetch_service.fetch_resumes(start_date, end_date)
                
                if gmail_resumes:
                    logger.info(f"✅ Fetched {len(gmail_resumes)} resumes from Gmail")
                    
                    # Create Metadata Map {filename: {subject, body}}
                    # gmail_metadata is already dict
                    
                    for item in gmail_resumes:
                        # Save with [Gmail] prefix to distinguish source
                        safe_fname = f"[Gmail] {item['filename']}"
                        fpath = os.path.join(temp_dir, safe_fname)
                        
                        gmail_metadata[safe_fname] = {
                            "email_subject": item["email_subject"],
                            "email_body": item["email_body"],
                            "sender_email": item.get('sender', '')
                        }
                        
                        with open(fpath, "wb") as f:
                            f.write(item["content"])
                        
                        # Store email metadata for role matching (done in pipeline)
                        # We'll pass this through somehow - for now just log
                        logger.info(f"  📧 From: '{item['email_subject']}'")
                        
                else: 
                     logger.info("No resumes found in Gmail range.")
                     
                if gmail_resumes:
                    files_found = True
            
            except ValueError as e:
                # Gmail not connected error
                logger.error(f"Gmail connection error: {e}")
                raise HTTPException(status_code=400, detail=str(e))
            except Exception as e:
                logger.error(f"Gmail Fetch Error: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to fetch emails from Gmail: {str(e)}"
                )
        
        if not files_found:
             raise HTTPException(status_code=400, detail="No resumes provided. Please upload files or select a valid date range for Gmail.")

        # 5. Spawn Background Task
        # (job_id: str, jd_text: str, source_dir: str, top_n: int, jd_source_name: str, gmail_metadata: dict)
        background_tasks.add_task(_run_async_analysis, job_id, jd_text, temp_dir, top_n, jd_source, gmail_metadata)

        return {"job_id": job_id, "status": "processing"}

    except Exception as e:
        fail_job(job_id, str(e))
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{job_id}", response_model=JobStatusResponse)
def get_status(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = jobs[job_id]
    return JobStatusResponse(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        current_step=job["current_step"],
        result=job["result"],
        error=job["error"]
    )

@app.post("/open_report")
def open_report(path: str = Form(...)):
    try:
        if os.path.exists(path):
            os.startfile(path)
            return {"status": "success"}
        return {"status": "error", "message": "Path not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
