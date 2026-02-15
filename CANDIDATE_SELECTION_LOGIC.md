# Candidate Selection Logic & Email Process

This document details the exact logic used to filter, rank, and select candidates, as well as how emails are handled for "Selected" (Assessment) and "Not Selected" (Rejection) candidates.

## 1. Initial Filtering (The Gatekeepers)

Before any AI analysis, candidates must pass two strict filters.

### **Filter 1: Page Count Rule (Hard Rejection)**
*   **Junior Candidates (< 3 Years Experience):**
    *   Resume must be **Max 1 Page**.
    *   If > 1 Page: **REJECTED IMMEDIATELY**.
*   **Senior Candidates (>= 3 Years Experience):**
    *   Resume must be **Max 2 Pages**.
    *   If > 2 Pages: **REJECTED IMMEDIATELY**.
*   **Outcome:** These candidates are marked as `Rejected` and do NOT proceed to semantic analysis.

### **Filter 2: Role Match (Zero-Shot Classification)**
*   **Logic:** The system compares the candidate's resume content against the Job Title.
*   **Method:** Zero-shot classification (AI Model).
*   **Rule:** If the match probability is **< 60%**, the candidate is deemed irrelevant.
*   **Outcome:** These candidates are **SKIPPED**. They are not part of the valid candidate pool for this role.

---

## 2. Ranking & Selection Strategy

Let's assume we start with **100 candidates** and apply the filters:

1.  **Total:** 100 Candidates.
2.  **After Page Rule:** 30 Rejected (70 remaining).
3.  **After Role Match:** 30 Skipped (40 Valid Candidates remaining).

### **The Valid Pool (40 Candidates)**
These 40 candidates are now ranked based on **Vector Similarity** to the Job Description (JD).
*   **Score:** 0-100% based on keyword overlap and semantic meaning.
*   **Ranking:** Sorted from Rank 1 to Rank 40.

### **The "Top N" Cutoff (User Input)**
*   **Scenario:** The recruiter wants the **Top 5** candidates.
*   **System Action:** It selects a slightly larger group for deep AI analysis to find the *true* best.
*   **Selection:** Top 5 + Buffer (e.g., 5) = **Top 10 Candidates**.

---

## 3. The Final Verdict (AI vs Similarity)

### **Group A: AI Analyzed (Top 10)**
*   **Who:** Rank 1 to 10 from the similarity list.
*   **Process:** AI reads their full resume, analyzes strengths/weaknesses, and assigns a final specific score.
*   **Outcome:**
    *   **Top 5 (Best of the 10):** Marked as **SELECTED**.
        *   ✅ **Action:** Receive Assessment Link.
    *   **Next 5 (Rank 6-10):** Marked as **NOT SELECTED** (Good, but not best).
        *   ❌ **Action:** Receive Rejection Email.

### **Group B: Similarity Only (Rank 11-40)**
*   **Who:** The remaining 30 valid candidates.
*   **Process:** They are not analyzed by deep AI to save costs/time. Their score is based purely on keyword matching.
*   **Outcome:** Marked as **NOT SELECTED**.
    *   ❌ **Action:** Receive Rejection Email.

---

## 4. Email Handling Summary

| Category | Count (Example) | Status | Action |
| :--- | :--- | :--- | :--- |
| **Selected (Top 5)** | 5 | ✅ Selected | **Send Assessment Link** |
| **AI Rejected (Rank 6-10)** | 5 | ❌ Not Selected | **Send Rejection Email** |
| **Similarity Rejected (Rank 11-40)** | 30 | ❌ Not Selected | **Send Rejection Email** |
| **Hard Rejected (Page/Role)** | 60 | ❌ Rejected/Skipped | **Send Rejection Email** (Optional) |

This logic ensures:
1.  **Efficiency:** Only high-potential candidates get expensive AI analysis.
2.  **Fairness:** Every valid candidate gets a similarity score.
3.  **Closure:** All non-selected candidates can receive a polite rejection email.
