
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Dict
import shutil
import os
import json
import logging
import warnings
import re
from datetime import datetime
warnings.filterwarnings("ignore", category=DeprecationWarning)

from .core.config import get_settings
from .services import pdf_service, vector_service, ai_service, utils, gmail_service
from .services.score_service import calculate_score
from .models.schemas import LLMOutput

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Print to console
        logging.FileHandler("backend.log", encoding="utf-8")  # Save to file
    ]
)
logger = logging.getLogger("ResumeAgent")

app = FastAPI(title="Resume Screening Agent API", version="2.2")

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

settings = get_settings()

@app.get("/")
def root():
    return {"message": "Resume Screening Agent API is running."}

@app.post("/open_report")
def open_report(path: str = Form(...)):
    try:
        if os.path.exists(path):
            os.startfile(path)
            return {"status": "success"}
        return {"status": "error", "message": "Path not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def _run_analysis_pipeline(jd_text: str, file_buffers: Dict[str, bytes], top_n: int, jd_source_name: str):
    """
    Core Logic: Processing -> Scoring -> AI Analysis -> Reporting
    """
    try:
        # 1. Process JD
        jd_clean = utils.clean_text(jd_text)
        logger.info(f"   JD Length: {len(jd_clean)} chars")
        
        # Extract JD Metadata
        jd_keywords = utils.extract_keywords(jd_clean)
        jd_years = utils.extract_years_of_experience(jd_clean)
        logger.info(f"   Extracted {len(jd_keywords)} Keywords | Required Exp: {jd_years} Years")
        
        jd_data = {
            "keywords": jd_keywords,
            "required_years": jd_years,
            "location": "Remote" if "remote" in jd_clean.lower() else "" 
        }

        # 2. Process Resumes & Vectorize
        logger.info("Step 2: Vectorizing Resumes...")
        vector_service.vector_service.reset()
        resume_texts = {}
        resume_docs = []
        resume_metas = []
        resume_pages = {}
        
        for fname, content in file_buffers.items():
            if fname.lower().endswith(".pdf"):
                text, pages = pdf_service.pdf_service.extract_text(content)
            else:
                text = content.decode("utf-8", errors="ignore")
                pages = 1
            
            clean = utils.clean_text(text)
            resume_texts[fname] = clean
            resume_pages[fname] = pages
            resume_docs.append(clean)
            resume_metas.append({"filename": fname})

        # Add to Vector DB
        logger.info(f"   Creating Vector Embeddings for {len(resume_docs)} documents...")
        vector_service.vector_service.add_texts(resume_docs, resume_metas)
        
        # 3. Calculate Semantic Similarity
        logger.info("Step 3: Calculating Semantic Similarity with JD...")
        results = vector_service.vector_service.search(jd_clean, k=len(file_buffers))
        
        semantic_scores = {}
        for doc, score in results:
            sim = max(0.0, 1.0 - (score / 1.5))
            fname = doc.metadata.get("filename")
            semantic_scores[fname] = sim
            
        # 4. Calculate Final Scores
        logger.info("Step 4: Running Hybrid Scoring Engine...")
        final_results = []
        rejected_candidates = []
        
        for fname, r_text in resume_texts.items():
            sem_score = semantic_scores.get(fname, 0.0)
            page_cnt = resume_pages.get(fname, 1)
            score_data = calculate_score(r_text, jd_data, sem_score, page_count=page_cnt)
            cand_name = utils.extract_name(r_text, filename=fname)
            
            if score_data.get("is_rejected", False):
                reason = score_data.get("rejection_reason", "Unknown Reason")
                logger.warning(f"   ❌ REJECTED: {fname} | Reason: {reason}")
                rejected_candidates.append({
                    "filename": fname,
                    "name": cand_name,
                    "reason": reason,
                    "score": 0
                })
                continue
            
            logger.info(f"   ➡️ Candidate: {fname} ({cand_name}) | Hybrid Score: {score_data['total']:.2f}")
            
            final_results.append({
                "filename": fname,
                "name": cand_name,
                "score": score_data,
                "semantic_score": sem_score
            })
            
        # 5. Rank & Filter
        final_results.sort(key=lambda x: x["score"]["total"], reverse=True)
        top_candidates = final_results[:top_n]
        remaining_candidates = final_results[top_n:]
        logger.info(f"Step 5: Generated Shortlist (Top {top_n}). Remaining: {len(remaining_candidates)}")
        
        # 6. AI Reasoner
        logger.info("Step 6: Sending Candidates to Llama 3.3 for structured analysis...")
        candidates_text = ""
        
        # Add Shortlisted (Top N)
        for i, cand in enumerate(top_candidates):
            anon_text = ai_service.ai_service.anonymize(resume_texts[cand["filename"]])
            candidates_text += f"\n--- Candidate (SHORTLISTED - TOP RANK) ---\nFilename: {cand['filename']}\nScore: {cand['score']['total']}\nContent:\n{anon_text[:3000]}\n"
        
        # Add Not Selected (Valid but Low Score) - Limit 10
        for i, cand in enumerate(remaining_candidates[:10]):
            anon_text = ai_service.ai_service.anonymize(resume_texts[cand["filename"]])
            candidates_text += f"\n--- Candidate (NOT SELECTED - LOWER SCORE) ---\nFilename: {cand['filename']}\nScore: {cand['score']['total']}\nContent:\n{anon_text[:2000]}\n"

        # Note: Hard Rejected candidates are EXCLUDED from AI analysis
        
        if not top_candidates and not remaining_candidates:
             logger.warning("No valid candidates to analyze.")
             img_analysis = []
        else:
            prompt = f"""
            You are a Senior Technical Recruiter. Analyze these candidates for the Job Description below.
            
            JD Summary: {jd_clean[:1500]}
            
            Candidates:
            {candidates_text}
            
            TASK:
            Return a JSON OBJECT with a key "candidates" containing a list of objects.
            
            For SHORTLISTED candidates: Status = "Recommended" or "Potential".
            For NOT SELECTED candidates: Status = "Rejected". Explain why they were not selected.
            
            Each object must have:
            - "filename": exact filename from input
            - "candidate_name": extracted name
            - "status": "Recommended", "Potential", or "Rejected"
            - "reasoning": Detailed specific feedback comparing the candidate strictly against the JD constraints.
            - "strengths": List of strings.
            - "weaknesses": List of strings.
            - "hobbies_and_achievements": List of strings (Extract any Hobbies, Hackathons, Awards, Certifications, or Volunteering).
            
            Ensure the JSON is valid.
            """
            llm_response = ai_service.ai_service.query(prompt, json_mode=True)
            
            # Pydantic Parsing
            img_analysis = []
            try:
                json_str = llm_response
                match = re.search(r"```json(.*?)```", llm_response, re.DOTALL)
                if match:
                    json_str = match.group(1).strip()
                if not match:
                    start = llm_response.find("{")
                    end = llm_response.rfind("}")
                    if start != -1 and end != -1:
                        json_str = llm_response[start:end+1]
                
                parsed_obj = LLMOutput.model_validate_json(json_str)
                if hasattr(parsed_obj, 'model_dump'):
                    img_analysis = [c.model_dump() for c in parsed_obj.candidates]
                else:
                    img_analysis = [c.dict() for c in parsed_obj.candidates]
            except Exception as e:
                logger.warning(f"Failed to parse LLM JSON: {e}")
                img_analysis = [{"candidate_name": "AI Parsing Error", "reasoning": "Could not parse AI response.", "filename": "report", "strengths": [], "weaknesses": [], "status": "Report"}]

        logger.info("✅ ANALYSIS COMPLETE. Generating Report Packet...")

        # 7. Generate Campaign Report Packet
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        report_dir = f"Reports/Campaign_{timestamp}"
        os.makedirs(f"{report_dir}/All_Resumes", exist_ok=True)
        os.makedirs(f"{report_dir}/Shortlisted_Resumes", exist_ok=True)
        
        # Save All Resumes
        for fname, content in file_buffers.items():
            with open(f"{report_dir}/All_Resumes/{fname}", "wb") as f:
                f.write(content)
                
        # Save Selected Resumes
        top_filenames = [c['filename'] for c in top_candidates]
        for fname, content in file_buffers.items():
            if fname in top_filenames:
                 with open(f"{report_dir}/Shortlisted_Resumes/{fname}", "wb") as f:
                    f.write(content)

        # Save Rejected Resumes
        if rejected_candidates:
            os.makedirs(f"{report_dir}/Rejected_Resumes", exist_ok=True)
            rej_filenames = [c['filename'] for c in rejected_candidates]
            for fname, content in file_buffers.items():
                    with open(f"{report_dir}/Rejected_Resumes/{fname}", "wb") as f:
                        f.write(content)

        # Save NOT Selected (But Valid) Resumes
        if remaining_candidates:
             os.makedirs(f"{report_dir}/Not_Selected_Resumes", exist_ok=True)
             rem_filenames = [c['filename'] for c in remaining_candidates]
             for fname, content in file_buffers.items():
                 if fname in rem_filenames:
                     with open(f"{report_dir}/Not_Selected_Resumes/{fname}", "wb") as f:
                         f.write(content)
        
        # Generate Markdown
        executive_summary = ""
        for item in img_analysis:
            if item.get("filename") == "report": 
                 executive_summary += f"{item.get('reasoning')}\n\n"
            else:
                executive_summary += f"### 👤 {item.get('candidate_name', 'Unnamed')} ({item.get('status', 'Analyzed')})\n"
                executive_summary += f"**Reasoning:** {item.get('reasoning')}\n\n"
                if item.get("strengths"):
                    executive_summary += "**✅ Strengths:**\n" + "\n".join([f"- {s}" for s in item.get("strengths")]) + "\n\n"
                if item.get("weaknesses"):
                    executive_summary += "**⚠️ Weaknesses:**\n" + "\n".join([f"- {w}" for w in item.get("weaknesses")]) + "\n\n"
                if item.get("hobbies_and_achievements"):
                    executive_summary += "**🏆 Activities & Achievements:**\n" + "\n".join([f"- {h}" for h in item.get("hobbies_and_achievements")]) + "\n\n"
                executive_summary += "---\n"
        
        md_content = f"""# 🧬 RecruitAI Screening Report
**Date:** {timestamp}
**Job Description:** {jd_source_name}

## 🎯 Executive Summary
{executive_summary}

## 📊 Shortlisted Candidates (Top {len(top_candidates)})
| Rank | Candidate | Match Score | Semantic Fit | Experience |
|---|---|---|---|---|
"""
        for i, cand in enumerate(top_candidates):
            c_name = cand.get("name", "Unknown")
            md_content += f"| {i+1} | **{c_name}**<br>_{cand['filename']}_ | **{cand['score']['total']:.1f}** | {cand['semantic_score']:.2f} | {cand['score']['experience_score']:.1f} |\n"
            
        if rejected_candidates:
            md_content += "\n## 🚫 Rejected Candidates\n"
            md_content += "| Candidate | Reason |\n|---|---|\n"
            for rej in rejected_candidates:
                md_content += f"| **{rej['name']}**<br>_{rej['filename']}_ | ⚠️ {rej['reason']} |\n"

        md_content += "\n## 🔍 Detailed Analysis Log\n"
        
        with open(f"{report_dir}/Analysis_Report.md", "w", encoding="utf-8") as f:
            f.write(md_content)
            
        return {
            "status": "success",
            "candidates": final_results, 
            "rejected_count": len(rejected_candidates),
            "rejected_candidates": rejected_candidates,
            "ai_analysis": img_analysis, 
            "top_candidates": top_candidates,
            "report_path": os.path.abspath(report_dir)
        }

    except Exception as e:
        logger.error(f"❌ PIPELINE ERROR: {str(e)}")
        raise e

@app.post("/analyze")
async def analyze_resumes(
    jd_file: UploadFile = File(None),
    jd_text_input: str = Form(None),
    resume_files: List[UploadFile] = File(None),
    start_date: str = Form(None),
    end_date: str = Form(None),
    top_n: int = Form(5)
):
    try:
        # 1. Prepare JD
        if jd_file:
            logger.info(f"Processing JD File: {jd_file.filename}")
            jd_bytes = await jd_file.read()
            if jd_file.filename.endswith(".pdf"):
                jd_text, _ = pdf_service.pdf_service.extract_text(jd_bytes)
            else:
                jd_text = jd_bytes.decode("utf-8")
            jd_name = jd_file.filename
        elif jd_text_input:
            logger.info("Processing JD Text Input")
            jd_text = jd_text_input
            jd_name = "Pasted Text"
        else:
             raise HTTPException(status_code=400, detail="Job Description (File or Text) is required.")

        file_buffers = {}

        # 2. Source A: Manual Uploads
        if resume_files:
            logger.info(f"📥 Processing {len(resume_files)} Manual Uploads...")
            for file in resume_files:
                content = await file.read()
                file_buffers[file.filename] = content

        # 3. Source B: Gmail Fetch
        if start_date and end_date:
            logger.info(f"📧 Fetching Emails from {start_date} to {end_date}...")
            gmail_resumes = gmail_service.gmail_service.fetch_resumes(start_date, end_date)
            if gmail_resumes:
                logger.info(f"   found {len(gmail_resumes)} resumes in Gmail.")
                for item in gmail_resumes:
                    # Avoid overwriting if same filename exists (append suffix if needed, but simple overwrite for now)
                    file_buffers[f"[Email] {item['filename']}"] = item["content"]
            else:
                logger.warning("   No resumes found in Gmail for this range.")

        # 4. Validation
        if not file_buffers:
             raise HTTPException(status_code=400, detail="No resumes provided! Upload files OR select a Date Range for Gmail.")
            
        logger.info(f"🚀 STARTING ANALYSIS: Total {len(file_buffers)} Resumes.")

        # 5. Run Pipeline
        return await _run_analysis_pipeline(jd_text, file_buffers, top_n, jd_name)

    except Exception as e:
        logger.error(f"Error in analyze: {str(e)}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
