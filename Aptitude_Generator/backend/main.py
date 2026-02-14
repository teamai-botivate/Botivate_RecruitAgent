import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from agent import generate_aptitude_questions

import json
import time
import uuid

# Load environment variables (reaching out to root .env)
basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, "../../.env"))

# Database file at root level
DB_FILE = os.path.abspath(os.path.join(basedir, "../../assessments_db.json"))
BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:5500") # Default for local

def init_db():
    try:
        if not os.path.exists(DB_FILE):
            print(f"DEBUG: Creating new database at {DB_FILE}")
            with open(DB_FILE, "w") as f:
                json.dump({"assessments": [], "submissions": []}, f)
        else:
            print(f"DEBUG: Database found at {DB_FILE}")
    except Exception as e:
        print(f"CRITICAL: Failed to initialize DB: {e}")

def get_db():
    init_db()
    with open(DB_FILE, "r") as f:
        return json.load(f)

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)
    print(f"DEBUG: Database saved successfully to {DB_FILE}")

app = FastAPI(title="Aptitude Generator API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class JDRequest(BaseModel):
    jd_text: str

class EmailRequest(BaseModel):
    emails: list[str]
    job_title: str
    mcq_count: int
    coding_count: int
    assessment_link: str
    mcqs: list[dict]
    coding_questions: list[dict]

@app.post("/generate-aptitude")
async def generate_aptitude(request: JDRequest):
    print(f"\n--- 🤖 REQUEST: Generate Aptitude & Coding ---")
    if not request.jd_text.strip():
        raise HTTPException(status_code=400, detail="Job Description text is empty")
    
    try:
        result = generate_aptitude_questions(request.jd_text)
        return result # returns {"mcqs": [...], "coding_questions": [...]}
    except Exception as e:
        print(f"Error generating content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/send-assessment")
async def send_assessment(request: EmailRequest, background_tasks: BackgroundTasks):
    print(f"\n--- 📧 REQUEST: Send Assessment to {len(request.emails)} candidates ---")
    
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not all([smtp_user, smtp_password]):
        raise HTTPException(status_code=500, detail="SMTP credentials not configured.")

    def update_db_task():
        try:
            token = request.assessment_link.split("token=")[-1]
            db = get_db()
            db["assessments"].append({
                "id": str(uuid.uuid4()),
                "token": token,
                "job_title": request.job_title,
                "emails": request.emails,
                "mcqs": request.mcqs,
                "coding_questions": request.coding_questions,
                "timestamp": time.time(),
                "status": "Sent"
            })
            save_db(db)
        except Exception as e:
            print(f"⚠️ DB Warning: {e}")

    background_tasks.add_task(update_db_task)

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)

        format_info = ""
        if request.mcq_count > 0: format_info += f"<li><strong>Aptitude:</strong> {request.mcq_count} MCQs</li>"
        if request.coding_count > 0: format_info += f"<li><strong>Coding:</strong> {request.coding_count} DSA Questions</li>"

        for email in request.emails:
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = email
            msg['Subject'] = f"Career Opportunity | {request.job_title} Technical Evaluation"

            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #6366f1;">Congratulations!</h2>
                <p>Dear Candidate,</p>
                <p>Your profile for the <strong>{request.job_title}</strong> role has been shortlisted. Please complete the following technical assessment.</p>
                
                <div style="background: #f4f4f9; padding: 20px; border-radius: 10px; border-left: 5px solid #6366f1; margin: 20px 0;">
                    <p><strong>Assessment Details:</strong></p>
                    <ul>
                        {format_info}
                        <li><strong>Environment:</strong> Online IDE (Multiple Languages Supported)</li>
                        <li><strong>Estimated Time:</strong> 1 Hour</li>
                    </ul>

                    <div style="background: #fff5f5; border: 1px solid #feb2b2; padding: 15px; border-radius: 8px; margin-top: 15px;">
                        <p style="color: #c53030; margin-top: 0;"><strong>⚠️ PROCTORING RULES:</strong></p>
                        <p style="font-size: 0.9rem; margin-bottom: 0;">Camera must stay ON. Tab switching and head movement are strictly monitored by AI.</p>
                    </div>

                    <p style="text-align: center; margin-top: 25px;">
                        <a href="{request.assessment_link}" style="background: #6366f1; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; font-weight: bold;">Enter Test Environment</a>
                    </p>
                </div>
                <p>Best Regards,<br><strong>Talent Acquisition Team</strong><br>RecruitAI</p>
            </body>
            </html>
            """
            msg.attach(MIMEText(body, 'html'))
            server.send_message(msg)
        
        server.quit()
        return {"status": "success"}
    except Exception as e:
        print(f"❌ SMTP Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

class RejectionRequest(BaseModel):
    emails: list[str]
    job_title: str

@app.post("/send-rejection")
async def send_rejection(request: RejectionRequest):
    print(f"\n--- 📧 REQUEST: Send Rejection to {len(request.emails)} candidates ---")
    
    smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not all([smtp_user, smtp_password]):
        raise HTTPException(status_code=500, detail="SMTP credentials not configured.")

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_password)

        for email in request.emails:
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = email
            msg['Subject'] = f"Update on your application for {request.job_title}"
            
            body = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <p>Dear Candidate,</p>
                <p>Thank you for giving us the opportunity to consider your application for the <strong>{request.job_title}</strong> position.</p>
                <p>We have reviewed your profile, and while we were impressed with your qualifications, we have decided to proceed with other candidates who more closely align with our current requirements.</p>
                <p>We will keep your resume in our database and may contact you if a suitable opening arises in the future.</p>
                <p>We wish you the best in your job search.</p>
                <br>
                <p>Best Regards,<br><strong>Talent Acquisition Team</strong><br>RecruitAI</p>
            </body>
            </html>
            """
            msg.attach(MIMEText(body, 'html'))
            server.send_message(msg)
        
        server.quit()
        return {"status": "success", "message": f"Sent rejection to {len(request.emails)} candidates"}
    except Exception as e:
        print(f"❌ SMTP Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-assessment/{token}")
async def get_assessment(token: str):
    db = get_db()
    assessment = next((a for a in db["assessments"] if a["token"] == token), None)
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    return {
        "mcqs": assessment.get("mcqs", []), 
        "coding": assessment.get("coding_questions", []), 
        "job_title": assessment["job_title"]
    }

@app.post("/submit-assessment")
async def submit_assessment(data: dict):
    # data: { token, email, mcq_score, mcq_total, coding_score, coding_total, suspicious }
    print(f"\n--- 📝 REQUEST: Candidate Submission ({data.get('email')}) ---")
    try:
        db = get_db()
        db["submissions"].append({
            "token": data["token"],
            "email": data["email"],
            "mcq_score": data.get("mcq_score", 0),
            "mcq_total": data.get("mcq_total", 0),
            "coding_score": data.get("coding_score", 0),
            "coding_total": data.get("coding_total", 0),
            "timestamp": time.time(),
            "suspicious": data.get("suspicious", "Normal")
        })
        save_db(db)
        return {"status": "success"}
    except Exception as e:
        print(f"❌ Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/get-analytics")
async def get_analytics():
    db = get_db()
    return db

@app.delete("/delete-assessment/{token}")
async def delete_assessment(token: str):
    db = get_db()
    db["assessments"] = [a for a in db["assessments"] if a["token"] != token]
    db["submissions"] = [s for s in db["submissions"] if s["token"] != token]
    save_db(db)
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)
