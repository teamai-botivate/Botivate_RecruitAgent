# 📘 Agentic Hiring Suite: Technical Manual (v4.0)

## 📌 1. System Philosophy
This system represents a shift from "Keyword Matching" to **"Agentic Reasoning"**. It employs a multi-agent architecture where strictly defined roles (JD Writer, Test Creator, Resume Screener) collaborate to automate the hiring lifecycle.

**Core Brain:** **OpenAI GPT-4o** is the central intelligence, chosen for superior instruction-following and reasoning.

---

## 📂 2. Module Breakdown

| Module | Directory | Function | AI Model |
| :--- | :--- | :--- | :--- |
| **JD Generator** | `JD_Generator/` | Drafts professional JDs with semantic richness. | `gpt-4o` |
| **Aptitude Gen** | `Aptitude_Generator/` | Creates structured JSON assessments (MCQ + Code). | `gpt-4o` |
| **Screener Core** | `Backend/` | The central orchestration API. | `gpt-4o` + `BART` |
| **Shared Services**| `Backend/app/services/` | Auth, DB, Parsing, and Vector logic. | N/A |

---

## 🤖 3. JD & Aptitude Intelligence (Pre-Screening)

### **3.1 Job Description (JD) Generator**
Instead of static JDs, we use an **Agentic Drafter** logic.
*   **The Input:** Basic Role Details (e.g., "Backend Dev, 5 LPA, Remote").
*   **The AI Process:**
    *   **Market Analysis:** Infers industry-standard tech stacks (e.g., "If Backend + Python -> Add FastAPI, PostgreSQL").
    *   **Keyword Injection:** Strategically places ATS-friendly keywords (hidden & visible) to attract better candidates.
    *   **Structure Enforcement:** Enforces a 9-point structure (Responsibilities, Tech Stack, Perks, etc.) that the *Screener* is trained to read perfectly.

### **3.2 Aptitude Assessment Generator**
Automated testing is generated *on-the-fly* based on the specific JD.
*   **Context Awareness:** If the JD lists "Kubernetes", the agent generates MCQ #12 specifically about K8s Pods.
*   **Structure:**
    *   **25 MCQs:** Covering Theory, Debugging, and System Design.
    *   **4 Coding Challenges:** Role-agnostic DSA problems (Easy -> Hard).
*   **Output:** A clean JSON object used to render the test portal for candidates.

---

## ⚙️ 4. The Resume Screening Pipeline ("The Master Flow")

The diagram below details every single logic gate, from reading the JD to sending the final rejection email.

```mermaid
graph TD
    %% ---------------------------------------------------------
    %% PHASE 1: INTELLIGENT PREPARATION (JD & PRE-WORK)
    %% ---------------------------------------------------------
    subgraph "Phase 1: Agentic Preparation"
        Recruiter([👤 Recruiter]) -->|1. Inputs Role Basics| JD_UI[💻 JD Generator UI]
        
        JD_UI -->|Trigger| JD_Agent[🤖 JD Agent (GPT-4o)]
        JD_Agent -->|Step A: Market Research| Market_Data[📊 Tech Stack Inference]
        JD_Agent -->|Step B: ATS Optimization| Keyword_Inject[🔑 Inject Hidden Keywords]
        
        Market_Data & Keyword_Inject -->|Generate| JD_Final[📄 Structured JD Output]
        
        JD_Final -->|2. Auto-Create Test| Apt_UI[⚙️ Assessment Agent]
        Apt_UI -->|Analyze JD Skills| Q_Gen[🧠 Question Generator]
        Q_Gen -->|Create 25 MCQs + 4 Code| Test_JSON[📝 Assessment JSON]
    end

    %% ---------------------------------------------------------
    %% PHASE 2: RESUME INGESTION & FILTERING
    %% ---------------------------------------------------------
    subgraph "Phase 2: Ingestion & Filtering"
        Recruiter -->|3. Upload Resumes| Manual[📂 Manual Upload]
        Gmail[📧 Gmail Inbox] -->|4. Auto-Fetch| G_Service[📨 Gmail Service]
        
        G_Service -->|Recursive Scan| EML_Parse[📦 Extract .eml Attachments]
        Manual & EML_Parse -->|Raw PDFs| OCR[👀 PDF Parser / OCR]
        
        OCR -->|Clean Text| Sanitizer[🧹 Text Cleaner & PII Masker]
        
        Sanitizer -->|Check Metadata| Page_Rule{⚠️ Page Count Rule}
        Page_Rule -->|Junior > 1 Pg| Reject_1[🔴 REJECT: Non-Compliant]
        
        Page_Rule -->|Pass| Role_Guard{🛡️ BART Zero-Shot}
        Role_Guard -->|Score < 0.45| Skip_1[❌ SKIP: Wrong Role]
    end

    %% ---------------------------------------------------------
    %% PHASE 3: HYBRID SCORING & ANALYSIS
    %% ---------------------------------------------------------
    subgraph "Phase 3: Deep Screening"
        Role_Guard -->|Pass| Vectorizers[🧬 Vector Embeddings]
        
        %% SCORING ENGINE
        Vectorizers -->|Cosine Sim| Score_Sem[📐 Semantic Score (15%)]
        Sanitizer -->|Extract Skills| Score_Key[🔑 Keyword Match (25%)]
        Sanitizer -->|Calc Experience| Score_Exp[⏳ Experience Score (20%)]
        Sanitizer -->|Check Degree| Score_Edu[🎓 Education Score (10%)]
        Sanitizer -->|Analyze Layout| Score_Vis[🎨 Visual Score (30%)]
        
        Score_Sem & Score_Key & Score_Exp & Score_Edu & Score_Vis -->|Sum| Total_Score[🧮 Hybrid Fit Score]
        
        Total_Score -->|Sort Descending| Ranking[📊 Candidate Ranking]
        
        Ranking -->|Top N + 5| AI_Deep[🧠 GPT-4o Deep Read]
        AI_Deep -->|Analyze Gaps & Red Flags| Reasoning[💡 AI Critique]
        
        Reasoning -->|Final Cutoff| Selection{🏆 Is Selected?}
    end

    %% ---------------------------------------------------------
    %% PHASE 4: AUTOMATED ACTION & EVALUATION
    %% ---------------------------------------------------------
    subgraph "Phase 4: Optimization & Outreach"
        Selection -->|No| Soft_Rej[🟡 Not Selected List]
        Soft_Rej -->|Trigger| Email_Rej[📧 Send Rejection Email]
        
        Selection -->|Yes| Shortlist[🟢 Shortlisted]
        Shortlist -->|Trigger| Email_Invite[📧 Send Test Invite]
        
        Email_Invite -->|Link Click| Candidate[👤 Candidate Portal]
        Test_JSON -.-> Candidate
        
        Candidate -->|Submit Test| Auto_Grader[🤖 AI Auto-Grader]
        Auto_Grader -->|Eval Code Complexity| Code_Score[💻 Code Score]
        Auto_Grader -->|Check Answer Key| MCQ_Score[📝 MCQ Score]
        
        Code_Score & MCQ_Score & Reasoning -->|Compile| Final_Report[🎖️ FINAL HIRING DOSSIER]
    end
```

### **4.1 Zero-Shot Role Guardrail (`role_matcher.py`)**
Before any expensive AI analysis happens, the system protects your credits using a local Small Language Model (SLM).
*   **Model:** `facebook/bart-large-mnli`
*   **Logic:** Compares the Resume's content against the JD Title.
*   **Threshold:** `0.45` (tuned for high recall).
*   **Outcome:** **SKIPPED / IGNORED**.

> **📝 Real-World Scenario:**
> *   **The Job:** "Senior Python Backend Developer"
> *   **Candidate A (Raj):** Resume clearly states "Data Entry Operator" with skills like Excel, Typing.
> *   **System Action:** `Score: 0.12`. **SKIPPED**. Raj's resume never touches the expensive GPT-4o API. He is silently ignored to save costs.
> *   **Candidate B (Sarah):** Resume states "Django Developer".
> *   **System Action:** `Score: 0.88`. **PASSED**. Sarah moves to the next stage for deep analysis.

### **4.2 The Semantic Vector Engine (`vector_service`)**
*   **Database:** `ChromaDB` (Persistent)
*   **Process:**
    1.  **Ingest:** Resume text -> 384-d Vector (`all-MiniLM-L6-v2`).
    2.  **Query:** JD text -> Vector.
    3.  **Match:** Cosine Similarity search.
*   **Why?** Allows the system to know that "ReactNG" is similar to "Angular" even if keywords don't match exactly.

### **4.3 The Hybrid Scoring Formula**
Final Score (0-100) is calculated as:

$$ Score = (K \times 0.25) + (E \times 0.20) + (Edu \times 0.10) + (V \times 0.30) + (Sem \times 0.15) $$

> **📝 Scoring Deep Dive (Candidate: Sarah):**
> *   **Keywords (25 pts):** JD asks for `Python`, `Docker`, `AWS`. Sarah has Python & Docker but misses AWS. **Score: 20/25**.
> *   **Experience (20 pts):** JD needs 5 years. Sarah has 4 years. Formula: `(4/5) * 20` = **16 pts**.
> *   **Education (10 pts):** B.Tech from Tier-1 College (IIT). **Score: 10/10** (Full Bonus).
> *   **Visuals (30 pts):** Clean layout, good whitespace. **Score: 28/30**.
> *   **Semantic (15 pts):** High relevance. **Score: 14/15**.
> *   **TOTAL SCORE:** **88/100** (Strong Candidate)

### **4.4 The Buffer Strategy (Top N + 5)**
The system intentionally over-selects candidates.
*   **User Request:** "Top 5"
*   **System Action:** Selects **Top 10** for AI Analysis.
*   **Reason:** If #1 is rejected by AI for red flags, #6 takes their place, ensuring you always get your requested 5 candidates.

### **4.5 The AI Analyst (GPT-4o)**
Top candidates undergo a "Deep Read" where GPT-4o mimics a human recruiter.
*   **Instruction:** "Find gaps. Don't just summarize. Look for short tenures, vague project descriptions, and skill mismatches."
*   **Output:** Generates the "Reasoning" paragraph for the report.

---

## 🚫 5. Rejection & Filtering Protocols

### **Tier 1: Hard Rules ("REJECTED")**
*   **Junior (`<2y`):** Rejected if > 1 page.
*   **Senior (`>=2y`):** Rejected if > 2 pages.
*   **Example:** John (Fresh grad) submits a 3-page resume. **Result:** REJECTED.

### **Tier 2: Role Mismatch ("SKIPPED")**
*   **Logic:** BERT Entailment < 0.45.
*   **Example:** "Uber Driver" applying for "Marketing Manager". **Result:** SKIPPED (API cost saved).

### **Tier 3: Soft Rejection ("NOT SELECTED")**
*   **Logic:** Valid candidate but low Hybrid Score.
*   **Result:** Stored in "Not Selected" folder for potential future matching.

---

## 📧 6. Post-Screening Automations (Outreach & Evaluation)

Once the analysis is complete, the system automates communication:

### **6.1 The Rejection Email (For "Not Selected")**
*   **Trigger:** Candidate falls into Tier 3 (Soft Rejection).
*   **Content:** Personalized, polite rejection.
*   **Template:**
    > "Dear [Name], while your skills in [Skill_A] are impressive, we are looking for more experience in [Missing_Skill_B] at this time..."
*   **Goal:** Maintain employer brand reputation.

### **6.2 The Shortlist Email (For "Selected")**
*   **Trigger:** Candidate is in the Final Top N list.
*   **Content:** Congratulations + Call to Action.
*   **Action:** Includes a unique link to the **Aptitude Assessment Portal**.

### **6.3 Assessment & Evaluation**
The loop closes when the candidate interacts with the system:
1.  **Candidate Action:** Clicks link from email -> Logins to Portal -> Takes the AI-generated Assessment (See Sec 3.2).
2.  **Auto-Grading Engine:**
    *   **MCQs:** Instant grading via answer key.
    *   **Code Challenges:** AI evaluates complexity (Big O), correctness, and edge-case handling.
3.  **Final Report:** Recruiter receives a "Candidate Dossier" combining:
    *   Resume Fit Score (88/100)
    *   Aptitude Score (92/100)
    *   **Combined Hireability Index**.

---

## 🔧 7. Configuration Defaults

| Parameter | Default | Business Logic |
| :--- | :--- | :--- |
| `llm_model` | **gpt-4o** | High-reasoning model. |
| `keyword_weight` | **0.25** | Hard skills validation. |
| `visual_weight` | **0.30** | Quality of presentation. |
| `top_n` | **5** | Number of candidates to shortlist. |

---

## 🛡️ 8. Data Privacy
*   **PII Masking:** Names/Emails are masked before Vector DB storage.
*   **Ephemeral:** No data stored externally. Local processing first.
