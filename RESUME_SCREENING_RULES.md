# 📘 Resurrection Screening Agent: The Ultimate Technical Manual (v3.2)

## 📌 1. System Philosophy & Architecture
This is an **Enterprise-Grade AI Hiring Assistant** designed to replace manual resume screening with a bias-free, data-driven "Fit Score" engine. It mimics a Senior Technical Recruiter's cognitive process using a **Hybrid AI Architecture**:

*   **Local Processing (The "Body"):** Handles file I/O, text extraction, cleaning, and vectorization securely via **FastAPI** backend.
*   **Cloud Reasoning (The "Brain"):** Uses **Groq (Llama 3.3 70B)** for high-level semantic understanding, detailed reasoning, and final decision making.

---

## 📂 2. Directory Structure & Component Logic

| File / Folder | Role | Technical Responsibility |
| :--- | :--- | :--- |
| `Frontend/index.html` | **Frontend** | Vanilla JS/CSS UI. Manages file uploads, drag-and-drop interactions, and dynamic dashboard rendering. |
| `Backend/app/main.py` | **Backend** | The core API controller. Handles `analyze/` endpoint, file parsing, and orchestrates the scoring pipeline. |
| `Backend/app/core/config.py` | **Control** | Centralized Configuration using Pydantic Settings. Manages API keys, model selection (`llama-3.3-70b-versatile`), and weights. |
| `Backend/app/services/gmail_service.py` | **Integration** | **Gmail API Handler**. Manages OAuth2 auth, fetches emails by date, and **recursively extracts PDFs** from nested `.eml` attachments. |
| `Reports/` | **Storage** | Organized output. Stores `All_Resumes`, `Shortlisted_Resumes`, `Not_Selected_Resumes`, and `Rejected_Resumes`. |
| `Backend/app/services/score_service.py` | **Logic** | The scoring engine. Implements the weighted formulas and rejection logic. |
| `Backend/app/models/schemas.py` | **Validation** | Pydantic models (`LLMOutput`, `candidate_score`) ensuring strict type safety for data exchange. |

---

## ⚙️ 3. Algorithmic Deep Dive (Function-Level)

### **3.1 The Ingestion Pipeline (`analyze_resumes`)**
1.  **Job Analysis:**
    *   *Input:* `jd_text` (Pasted) or `jd_file` (PDF/TXT).
    *   *Action:* NLP extraction of Skills, Required Experience, and Keywords using SpaCy.
    *   *Dynamic Config:* Adapts scoring weights based on role seniority detected in JD.
2.  **Resume Sourcing (Dual-Channel):**
    *   **Source A: Manual Upload:** Drag-and-drop PDFs/DOCXs.
    *   **Source B: Gmail Fetch:** 
        *   Authenticates via OAuth2.
        *   Searches emails with query `has:attachment (resume OR cv)`.
        *   **Deep Extraction:** Recursively parses `.eml` (forwarded email) attachments to find nested PDFs.
3.  **File Parsing (`pdf_service`):**
    *   *Logic:* Robust text extraction. Corrupted files trigger early validation errors.

### **3.2 The Anonymization Engine (`ai_service.anonymize`)**
*   **Goal:** Zero-Trust Bias Elimination.
*   **Logic:**
    *   The raw text is sent to Llama 3.3 with a strict prompt: *"Replace all PII (Name, Email, Phone, Address) with placeholders like [CANDIDATE_NAME]."*
    *   **Result:** The Scoring Engine evaluates skills, not demographics.

### **3.3 The Semantic Vector Engine (`vector_service`)**
*   **Goal:** Understand "Meaning" beyond keywords.
*   **Tool:** `ChromaDB` (Vector Store) + `HuggingFaceEmbeddings`.
*   **Process:**
    1.  Convert JD to Vector $V_{jd}$.
    2.  Convert Resume to Vector $V_{res}$.
    3.  Compute **Cosine Similarity**.
    4.  **Semantic Score** = Similarity scaled to 0-10 range.

### **3.4 The Scoring Calculator (`score_service.calculate_score`)**
Calculates the **Total Fit Score** using a weighted formula:

#### **A. Keyword Match (25 pts)**
*   **Logic:**
    *   Extracts hard skills (e.g., "Python", "Docker") from JD.
    *   Matches against Resume Entities.
    *   **Formula:** `(Matches / Total_JD_Keywords) * 25`.

#### **B. Experience Validation (20 pts)**
*   **Logic:**
    *   NLP extracts "Total Years Experience" from Resume.
    *   Compares against "Required Years" from JD.
    *   **Formula:** `min(Candidate_Exp / Required_Exp, 1.0) * 20`.

#### **C. Education & Location (20 pts)**
*   **Education (10 pts):** Bonus for Tier-1 degrees or Advanced Degrees (PhD/Masters).
*   **Location (10 pts):** Matches Candidate City vs JD Location. Full points for "Remote" roles or exact matches.

#### **D. Visual Presentation (30 pts)**
*   **Logic:** Analyzes formatting complexity, whitespace usage, and section headers. Penalizes cluttered or plain-text dumps.

---

## 👁️ 4. Visual Analysis Logic (Max 30 Points)
*Implemented in `score_service.py` via heuristic checks.*

| Metric | Max Pts | Criteria |
| :--- | :--- | :--- |
| **Structure** | 10 | Presence of clear sections (Skills, Experience, Education). |
| **Readability** | 10 | Sentence length, bullet point usage, and density. |
| **Formatting** | 10 | Proper use of capitalization and consistency. |

---

## 🚫 5. Rejection & Filtering Protocols

The system employs a strict "Funnel" strategy.

### **Tier 1: Hard Rules (The Gatekeeper)**
*   **Page Limit Rule:**
    *   **Junior (<2y exp):** Automatically **REJECTED** if > 1 Page.
    *   **Senior (>=2y exp):** Automatically **REJECTED** if > 2 Pages.
*   **Outcome:** Candidate marked as `is_rejected=True`. Saved to `Reports/Rejected_Resumes`. No AI Analysis.

### **Tier 2: "Soft" Rejection (Low Score)**
*   **Low Fit:** Total Score falls below competitive threshold.
*   **Outcome:** Labeled as **"Not Selected"** (Yellow Badge).
*   **Storage:** Saved to `Reports/Not_Selected_Resumes` for future reference.
*   **Analysis:** Sent to Llama 3.3 for *brief* feedback ("Why they didn't make the cut").

### **Tier 3: The "Top N" Cutoff (The Shortlist)**
*   **Usage:** User selects `Top N` (Default 5).
*   **Action:**
    *   System ranks valid candidates by Total Score.
    *   **Top N:** Labeled **"Recommended"** or **"Potential"**.
    *   **Storage:** Saved to `Reports/Shortlisted_Resumes`.
    *   **UI:** Displayed in the "Shortlisted Candidates" view with full breakdown.

---

## 🔧 6. Configuration & Tuning (`config.ini`)

| Section | Parameter | Default | Business Logic |
| :--- | :--- | :--- | :--- |
| **LLM** | `model` | **llama-3.3-70b** | High-reasoning model for complex analysis. |
| **Scoring** | `keyword_weight` | **0.25** | Hard skills validation. |
|  | `experience_weight` | **0.20** | Seniority requirement. |
|  | `education_weight` | **0.10** | Academic background. |
|  | `visual_weight` | **0.30** | Quality of presentation. |
| **Output** | `top_n` | **5** | Number of candidates to shortlist. |

---

## 🛡️ 7. Data Privacy & Compliance
*   **Zero Retention:** `data/` directory is ephemeral; reports are local to user's machine.
*   **PII Masking:** AI Anonymization layer runs *before* detailed analysis.
*   **Structured Output:** LLM assumes **JSON Mode** enforcement to prevent data leakage or hallucinations.
