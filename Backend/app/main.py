
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
from .services import pdf_service, vector_service, ai_service, utils, gmail_service
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
async def _run_async_analysis(job_id: str, jd_text: str, source_dir: str, top_n: int, jd_source_name: str):
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
        
        # 2. FILE INGESTION (Stream from Disk)
        # Scan the temp directory for files
        all_files = [f for f in os.listdir(source_dir) if os.path.isfile(os.path.join(source_dir, f))]
        total_files = len(all_files)
        
        if total_files == 0:
            fail_job(job_id, "No files found to process.")
            return

        resume_texts = {}
        resume_pages = {}
        processed_candidates = []
        
        # Batch Process to prevent Memory Spikes
        update_job_progress(job_id, 15, f"Parsing {total_files} Resumes...")
        
        for idx, fname in enumerate(all_files):
            file_path = os.path.join(source_dir, fname)
            try:
                if fname.lower().endswith(".pdf"):
                    with open(file_path, "rb") as f:
                        text, pages = pdf_service.pdf_service.extract_text(f.read())
                else:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        text = f.read()
                        pages = 1
                
                clean_text = utils.clean_text(text)
                resume_texts[fname] = clean_text
                resume_pages[fname] = pages
                
                # IMMEDIATE SCORING (Pass 1 - The Fast Scan)
                # Calculate raw score WITHOUT semantic embedding first
                score_data = calculate_score(clean_text, jd_data, semantic_score=0.0, page_count=pages)
                
                logger.info(f"   📄 Parsed: {fname} ({len(clean_text)} chars) | Pages: {pages}")

                if score_data.get("is_rejected"):
                     reason = score_data.get("rejection_reason", "Unknown")
                     logger.warning(f"   ❌ REJECTED (Hard Rule): {fname} | Reason: {reason}")
                     processed_candidates.append({
                         "filename": fname,
                         "name": utils.extract_name(clean_text, fname),
                         "score": score_data, # Rejected details inside
                         "status": "Rejected"
                     })
                else:
                    logger.info(f"   🧮 Raw Score: {fname} | Total: {score_data['total']:.1f} (Key: {score_data['keyword_score']:.1f}, Exp: {score_data['experience_score']:.1f})")
                    logger.info(f"      ✅ Found: {', '.join(score_data.get('matched_keywords', []))}")
                    logger.info(f"      ❌ Missing: {', '.join(score_data.get('missing_keywords', []))}")
                    
                    processed_candidates.append({
                        "filename": fname,
                         "name": utils.extract_name(clean_text, fname),
                         "score": score_data,
                         "text": clean_text,
                         "status": "Pending"
                    })

            except Exception as e:
                logger.error(f"Error reading {fname}: {e}")
            
            # Progress Update (15% to 50%)
            if idx % 5 == 0:
                prog = 15 + int((idx / total_files) * 35) 
                update_job_progress(job_id, prog, f"Parsed {idx+1}/{total_files} Resumes")



        # 3. VECTOR ANALYSIS (PURE SEMANTIC - ALL VALID CANDIDATES)
        # Filter strictly those who passed the Page Check
        valid_candidates = [c for c in processed_candidates if not c['score'].get('is_rejected', False)]
        rejected_candidates = [c for c in processed_candidates if c['score'].get('is_rejected', False)]
        
        # Log Pass 1 Results
        logger.info(f"   🛑 Pass 1 (Page Filter) Complete: {len(processed_candidates)} Processed. (Valid: {len(valid_candidates)} | Rejected: {len(rejected_candidates)})")

        update_job_progress(job_id, 30, "Semantic Analysis (Whole JD vs Resumes)...")
        
        vector_candidates = valid_candidates 
        
        if not vector_candidates:
             logger.warning("No candidates passed the Page Count Filter.")
        else:
            logger.info(f"   🧠 Running Pure Semantic Match on {len(vector_candidates)} candidates...")
            
            # Reset & Add Texts
            try:
                # We assume vector_service is available globally or imported
                # If using Chroma ephemeral, we might need a fresh client or reset
                # For this MVP, we just add new texts. Ideally we clears old ones but checks are ephemeral.
                docs = [c['text'] for c in vector_candidates]
                metas = [{"filename": c['filename']} for c in vector_candidates]
                
                # Check for reset method or just re-instantiate if needed, assuming add_texts works
                # (Ignoring exact implementation details of vector_service wrapper, focusing on flow)
                
                # 1. Reset DB to ensure fresh start for this job
                # Note: vector_service is the module, vector_service.vector_service is the instance
                vector_service.vector_service.reset()
                
                # 2. Add Texts
                vector_service.vector_service.add_texts(docs, metas)
                
                # 3. Search
                results = vector_service.vector_service.search(jd_clean, k=len(vector_candidates))
                
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

                for c in vector_candidates:
                    fname = c['filename']
                    
                    # 1. Document-Level Semantic Score
                    final_sem_score = sem_map.get(fname, 0.0)
                    if final_sem_score == 0.0:
                        logger.warning(f"   ⚠️ Semantic Score 0.0 for {fname}. Dist > 2.2?")

                    # 2. Skill-Level Semantic Check (Slower but Precise)
                    full_text = resume_texts.get(fname, "")
                    
                    try:
                        found_skills, missing_skills = vector_service.vector_service.check_semantic_skills(
                            full_text, 
                            jd_data['keywords'], 
                            threshold=0.45
                        )
                    except Exception as e:
                        logger.error(f"   ⚠️ Skill Check Error for {fname}: {e}")
                        found_skills, missing_skills = [], jd_data['keywords']
                    
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
        valid_candidates.sort(key=lambda x: x['score']['total'], reverse=True)
        top_candidates = valid_candidates[:top_n]
        remaining = valid_candidates[top_n:]

        update_job_progress(job_id, 75, f"Identified Top {len(top_candidates)} Candidates. Running AI Analysis...")

        # 4. AI ANALYSIS (Pass 3 - The Deep Dive)
        # Only analyze the Top N (Max 20 to save tokens/time)
        ai_target = top_candidates[:20] 
        logger.info(f"   🎯 Pass 3: Selecting Top {len(ai_target)} for AI Analysis (Requested Top {top_n}).")
        
        candidates_text = ""
        for c in ai_target:
             anon_text = ai_service.ai_service.anonymize(c['text'])
             candidates_text += f"\n--- Candidate ---\nFilename: {c['filename']}\nScore: {c['score']['total']}\nContent:\n{anon_text[:2500]}\n"

        img_analysis = []
        if candidates_text:
            prompt = f"""
            You are a Senior Technical Recruiter. Analyze these candidates for the Job Description below.
            
            JD Summary: {jd_clean[:1500]}
            
            CANDIDATES:
            {candidates_text}
            
            INSTRUCTIONS:
            1. Evaluate relevance to the JD (Skills, Experience, Role Fit).
            2. EXTRACT DETAILS (CRITICAL):
               - "years_of_experience": Calculate from work history dates. (e.g. "2021-Present" ~ 3 years). Do NOT return 0 if work history exists.
               - "extracted_skills": List of technical skills actually found.
               - "email" and "phone": Extract EXACT text found. Do NOT redact. Do NOT use placeholders like "[EMAIL]". If not found, return "Not Found".
            3. LOOK FOR HIDDEN GEMS: Check for Hackathons, Open Source (GitHub), Awards, Publications, or Complex Side Projects.
            4. *CRITICAL*: Assign an 'achievement_bonus' (0-20 points) based on these hidden gems.
               - 0: None
               - 5-10: Good projects/certs
               - 15-20: Hackathon winner, major open source contribution.
            5. Classify status as "High Potential" or "Review Required".

            OUTPUT FORMAT (Strict JSON):
            {{
              "candidates": [
                {{
                  "filename": "exact_filename.pdf",
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
                  "hobbies_and_achievements": ["Hackathon Winner 2024", "..."]
                }}
              ]
            }}
            Ensure the JSON is valid.
            """
            try:
                llm_response = ai_service.ai_service.query(prompt, json_mode=True)
                logger.info(f"   🤖 AI Raw Output (Truncated):\n{llm_response[:500]}...")
                
                # Quick Parse Logic
                json_str = llm_response
                match = re.search(r"```json(.*?)```", llm_response, re.DOTALL)
                if match: json_str = match.group(1).strip()
                elif "{" in llm_response:
                    s = llm_response.find("{")
                    e = llm_response.rfind("}")
                    json_str = llm_response[s:e+1]
                
                parsed = LLMOutput.model_validate_json(json_str)
                img_analysis = [c.model_dump() for c in parsed.candidates]
            except Exception as e:
                logger.error(f"AI Parse Error: {e}") 
                import traceback
                logger.error(traceback.format_exc())

        # 4b. Apply AI Results & Bonus
        if img_analysis:
            for ai_res in img_analysis:
                # Find original candidate object
                # We need to search in the main job list
                target_cand = next((c for c in jobs[job_id].get("candidates", []) if c["filename"] == ai_res.get("filename")), None)
                
                if target_cand:
                    # Update Fields
                    target_cand["status"] = ai_res.get("status", "Review Required")
                    target_cand["reasoning"] = ai_res.get("reasoning", "")
                    target_cand["email"] = ai_res.get("email", "Not Found")
                    target_cand["phone"] = ai_res.get("phone", "Not Found")
                    
                    # FIX: Update Score Data from AI Findings (Overwriting Regex zeroes)
                    ai_exp = ai_res.get("years_of_experience", 0)
                    ai_skills = ai_res.get("extracted_skills", [])
                    
                    # Update the internal score object so UI reflects it
                    target_cand["score"]["years"] = ai_exp
                    target_cand["score"]["matched_keywords"] = ai_skills
                    # Recalculate experience score roughly (30 points max)
                    # We assume 4 years is max for full points roughly in this context or use regex method
                    # But simpler is better for display:
                    req_years = jd_data.get("required_years", 2)
                    new_exp_score = min(30, (ai_exp / req_years) * 30) if req_years else 0
                    target_cand["score"]["experience_score"] = round(new_exp_score, 1)
                    target_cand["score"]["keyword_score"] = len(ai_skills) # Just count for display
                    
                    # Apply Bonus
                    bonus = ai_res.get("achievement_bonus", 0)
                    if bonus > 0:
                        old_total = target_cand["score"]["total"]
                        new_total = min(100, old_total + bonus)
                        target_cand["score"]["total"] = new_total
                        
                        target_cand["score"]["ai_bonus"] = bonus
                        target_cand["score"]["total_with_bonus"] = new_total
                        
                        logger.info(f"   🚀 {target_cand['filename']} Bonus: +{bonus} (New: {new_total})")
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

        # Rejected (Hard)
        if rejected_candidates:
             os.makedirs(f"{report_dir}/Rejected_Resumes", exist_ok=True)
             for c in rejected_candidates:
                 try:
                    shutil.copy2(os.path.join(source_dir, c['filename']), f"{report_dir}/Rejected_Resumes/{c['filename']}")
                 except: pass

        # Prepare Final Result Payload
        # We need to merge AI analysis back into the top candidates AND Re-Rank based on AI opinion!
        
        # Robust Logic: File names might differ slightly (e.g. "[Email]" prefix)
        # Create a map that handles both raw and clean filenames
        ai_map = {}
        # Ensure img_analysis exists
        if 'img_analysis' not in locals(): img_analysis = []
            
        for item in img_analysis:
            raw_name = item.get('filename', '')
            if raw_name:
                clean_name = raw_name.replace('[Email] ', '').strip()
                ai_map[raw_name] = item
                ai_map[clean_name] = item 
        
        updated_top_candidates = []
        for c in top_candidates:
            # Try to match filename
            fname = c['filename']
            fname_clean = fname.replace('[Email] ', '').strip()
            
            ai_data = ai_map.get(fname) or ai_map.get(fname_clean)
            
            if ai_data: # If AI analyzed this candidate
                status = ai_data.get('status', 'Review Required')
                
                # Dynamic Bonus from AI (1-15)
                # LLM should return integer. If missing, default to 0.
                bonus = ai_data.get('achievement_bonus', 0)
                
                # Validation: Ensure bonus is somewhat reasonable (-20 to +20)
                try: 
                    bonus = int(bonus)
                except: 
                    bonus = 0

                # Update Total Score
                old_score = c['score']['total']
                new_score = round(min(100, max(0, old_score + bonus)), 1)
                
                c['score']['total'] = new_score
                c['score']['ai_adjustment'] = bonus
                c['score']['original_score'] = old_score
                
                # Merge qualitative data (reasoning, strengths)
                # Merge qualitative data (reasoning, strengths)
                c.update(ai_data)

                # FALLBACK: If AI returned empty skills, use Keyword Match
                if not c.get('extracted_skills'):
                    c['extracted_skills'] = c['score'].get('matched_keywords', [])

                # FALLBACK: If AI returned 0 exp, try to use Regex Exp (if stored) or keep 0
                # We don't have regex exp explicitly in 'score' dict usually, but let's check
                if not c.get('years_of_experience') or c.get('years_of_experience') == 0:
                     # If we had regex exp in score, use it. But usually we don't store it separate from score calc.
                     # Let's AT LEAST ensure it's not None
                     c['years_of_experience'] = 0.0
                
                logger.info(f"   🤖 Re-Ranked {fname}: {old_score} -> {new_score} (Bonus: {bonus})")
                
                # Detailed breakdown for Frontend "View Details"
                # Providing object for structured view, and text for simple view
                c['score']['breakdown'] = {
                    "Base Score": old_score,
                    "AI Bonus": bonus,
                    "Final Score": new_score,
                    "Status": status
                }
                c['score']['breakdown_text'] = f"Base: {old_score} | Bonus: {bonus:+d} | Final: {new_score}"
                
            else:
                 # No AI Analysis
                 c['score']['breakdown'] = { "Base Score": c['score']['total'], "AI Bonus": 0, "Final": c['score']['total'] }
                 c['score']['breakdown_text'] = f"Base: {c['score']['total']} (No AI Analysis)"
                
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
                
        # Merge lists (Top Rated First + Others)
        final_list = updated_top_candidates + remaining
        
        # FINAL GLOBAL SORT: Ensure strict descending order regardless of bonus/no-bonus groups
        final_list.sort(key=lambda x: x['score']['total'], reverse=True)
        
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
        
        # Source A: Manual
        if resume_files:
            for file in resume_files:
                file_path = os.path.join(temp_dir, file.filename)
                with open(file_path, "wb") as f:
                    shutil.copyfileobj(file.file, f) # Efficient stream copy
            files_found = True
        
        # Source B: Gmail
        if start_date and end_date:
            update_job_progress(job_id, 2, "Fetching Gmail Resumes...")
            try:
                gmail_resumes = gmail_service.gmail_service.fetch_resumes(start_date, end_date)
                if gmail_resumes:
                    for item in gmail_resumes:
                        fpath = os.path.join(temp_dir, f"[Email] {item['filename']}")
                        with open(fpath, "wb") as f:
                            f.write(item["content"])
                    files_found = True
            except Exception as e:
                logger.error(f"Gmail Fetch Error: {e}")
        
        if not files_found:
             raise HTTPException(status_code=400, detail="No resumes provided. Please upload files or select a valid date range for Gmail.")

        # 5. Spawn Background Task
        # (job_id: str, jd_text: str, source_dir: str, top_n: int, jd_source_name: str)
        background_tasks.add_task(_run_async_analysis, job_id, jd_text, temp_dir, top_n, jd_source)

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
