
const analyzeBtn = document.getElementById('analyze-btn');
const topNInput = document.getElementById('top-n-input');
const jdDrop = document.getElementById('jd-drop');
const resumeDrop = document.getElementById('resume-drop');

let jdFile = null;
let resumeFiles = [];
let lastAnalysisData = null;
let currentReportPath = "";

// --- Initialization & Stepper Logic ---
document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
});

function updateStepper(stepNumber) {
    document.querySelectorAll('.workflow-stepper .step').forEach(step => {
        const stepVal = parseInt(step.dataset.step);
        if (stepVal <= stepNumber) {
            step.classList.add('active');
        } else {
            step.classList.remove('active');
        }
    });
}

// --- Drag & Drop Handlers ---
function setupDrop(dropArea, callback) {
    const originalBorder = "rgba(0, 0, 0, 0.05)";
    const hoverBorder = "var(--primary)";

    dropArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropArea.style.borderColor = hoverBorder;
        dropArea.style.background = "rgba(99, 102, 241, 0.05)";
    });

    dropArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropArea.style.borderColor = originalBorder;
        dropArea.style.background = "rgba(0, 0, 0, 0.02)";
    });

    dropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        dropArea.style.borderColor = originalBorder;
        dropArea.style.background = "rgba(0, 0, 0, 0.02)";
        callback(e.dataTransfer.files);
    });

    dropArea.addEventListener('click', (e) => {
        if (['TEXTAREA', 'LABEL', 'INPUT'].includes(e.target.tagName)) return;
        dropArea.querySelector('input[type="file"]').click();
    });

    const fileInput = dropArea.querySelector('input[type="file"]');
    if (fileInput) {
        fileInput.addEventListener('change', (e) => {
            callback(e.target.files);
        });
    }
}

setupDrop(jdDrop, (files) => {
    if (files.length > 0) {
        jdFile = files[0];
        document.getElementById('jd-name').innerHTML = `<i data-lucide="check-circle-2" style="width:14px; height:14px; vertical-align:middle; margin-right:5px; color:var(--success)"></i> ${jdFile.name}`;
        document.getElementById('jd-name').classList.add('animate-fade-in');
        lucide.createIcons();
        updateStepper(2); // Progress to JD Generate
    }
});

setupDrop(resumeDrop, (files) => {
    resumeFiles = Array.from(files);
    document.getElementById('resume-count').innerHTML = `<i data-lucide="check-circle-2" style="width:14px; height:14px; vertical-align:middle; margin-right:5px; color:var(--success)"></i> ${resumeFiles.length} profiles synced`;
    document.getElementById('resume-count').classList.add('animate-fade-in');
    lucide.createIcons();
    // Step 3/4 removed from UI
});

// Detect JD text input
document.getElementById('jd-text').addEventListener('input', (e) => {
    if (e.target.value.trim().length > 10) updateStepper(2);
});

// Gmail Toggle
const gmailCheckbox = document.getElementById('gmail-checkbox');
const gmailInputs = document.getElementById('gmail-inputs');

if (gmailCheckbox) {
    gmailCheckbox.addEventListener('change', () => {
        if (gmailCheckbox.checked) {
            gmailInputs.classList.remove('hidden');
        } else {
            gmailInputs.classList.add('hidden');
        }
    });
}

// --- Analysis Engine ---
analyzeBtn.addEventListener('click', async () => {
    const jdText = document.getElementById('jd-text').value.trim();
    const startDate = document.getElementById('start-date').value;
    const endDate = document.getElementById('end-date').value;
    const useGmail = gmailCheckbox ? gmailCheckbox.checked : false;

    if (!jdFile && !jdText) {
        showNotification("Expertise mismatch: Job Description required.", "error");
        return;
    }

    if (resumeFiles.length === 0 && !useGmail) {
        showNotification("Pipeline empty: Please provide candidates.", "error");
        return;
    }

    if (useGmail && (!startDate || !endDate)) {
        showNotification("Sync parameters missing: Check date range.", "error");
        return;
    }

    // Start UI Transition
    document.getElementById('loader').classList.remove('hidden');
    document.getElementById('results-area').classList.add('hidden');
    analyzeBtn.disabled = true;

    // Reset Loader Text
    document.querySelector('#loader h3').textContent = "Initializing Neural Link...";
    document.querySelector('#loader p').textContent = "Preparing analysis protocols...";

    const formData = new FormData();
    if (jdFile) formData.append('jd_file', jdFile);
    else formData.append('jd_text_input', jdText);

    formData.append('top_n', topNInput.value);
    resumeFiles.forEach(file => formData.append('resume_files', file));

    if (useGmail) {
        formData.append('start_date', startDate);
        formData.append('end_date', endDate);
    }

    try {
        // 1. Initiate Job
        const response = await fetch('http://localhost:8000/analyze', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || "Neural Link Failure: Server error.");
        }

        const data = await response.json();
        const jobId = data.job_id;

        // 2. Poll for Updates
        await pollJob(jobId);

    } catch (error) {
        showNotification(error.message, "error");
        document.getElementById('loader').classList.add('hidden');
        analyzeBtn.disabled = false;
    }
});

async function pollJob(jobId) {
    const loaderTitle = document.querySelector('#loader h3');
    const loaderDesc = document.querySelector('#loader p');

    const pollInterval = setInterval(async () => {
        try {
            const res = await fetch(`http://localhost:8000/status/${jobId}`);
            if (!res.ok) throw new Error("Status check failed");

            const statusData = await res.json();

            // Update UI
            if (loaderTitle) loaderTitle.textContent = `Analyzing... ${statusData.progress}%`;
            if (loaderDesc) loaderDesc.textContent = statusData.current_step || "Processing...";

            if (statusData.status === "completed") {
                clearInterval(pollInterval);
                document.getElementById('loader').classList.add('hidden');
                analyzeBtn.disabled = false;

                if (statusData.result) {
                    renderResults(statusData.result);
                } else {
                    showNotification("Analysis completed but no results found.", "error");
                }
            } else if (statusData.status === "error") {
                clearInterval(pollInterval);
                throw new Error(statusData.error || "Unknown analysis error");
            }

        } catch (e) {
            clearInterval(pollInterval);
            document.getElementById('loader').classList.add('hidden');
            analyzeBtn.disabled = false;
            showNotification(e.message, "error");
        }
    }, 2000);
}

// --- Tab Switching & Filtering ---
window.switchTab = function (tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(content => content.classList.remove('active'));

    const clickedBtn = document.querySelector(`.tab-btn[onclick="switchTab('${tabName}')"]`);
    if (clickedBtn) clickedBtn.classList.add('active');

    document.getElementById(`${tabName}-view`).classList.add('active');
}

window.switchAnalysisFilter = function (filter) {
    document.querySelectorAll('.filter-pill').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`filter-${filter}`).classList.add('active');
    renderAnalysisContent(filter);
}

// --- Rendering Logic ---
function renderResults(data) {
    lastAnalysisData = data;
    currentReportPath = data.report_path;
    document.getElementById('results-area').classList.remove('hidden');

    // Default filter
    switchAnalysisFilter('shortlist');
    lucide.createIcons();

    // Render Leaderboard
    const tbody = document.getElementById('results-body');
    tbody.innerHTML = '';

    // Only show top N as requested
    const topN = parseInt(topNInput.value) || 5;
    const candidates = data.candidates.slice(0, topN);

    candidates.forEach((cand, index) => {
        const tr = document.createElement('tr');
        tr.className = 'animate-fade-in';
        tr.style.animationDelay = `${index * 0.1}s`;

        // Construct PDF URL
        const pdfUrl = `http://localhost:8000/reports/${lastAnalysisData.campaign_folder}/All_Resumes/${cand.filename}`;

        let badgeClass = 'score-pill';
        if (cand.score.total >= 80) badgeClass += ' high-score';
        else if (cand.score.total >= 60) badgeClass += ' medium-score';
        else badgeClass += ' low-score';

        tr.innerHTML = `
            <td>
                <div class="candidate-info">
                    <strong>${cand.name || "Anonymous Expert"}</strong>
                    <small>
                        <a href="${pdfUrl}" target="_blank" style="color: #6366F1; text-decoration: none;">📄 ${cand.filename}</a>
                    </small>
                </div>
            </td>
            <td>
                <div class="${badgeClass}">${cand.score.total.toFixed(0)}%</div>
            </td>
            <td>
                ${(cand.extracted_skills && cand.extracted_skills.length > 0)
                ? `<span class="badge bg-blue-100 text-blue-800">+${cand.extracted_skills.length} Found</span>`
                : '<span class="text-gray-400">---</span>'}
            </td>
            <td>
                ${(cand.years_of_experience > 0)
                ? `<span class="font-medium">${cand.years_of_experience} yrs</span>`
                : '<span class="text-gray-400">---</span>'}
            </td>
            <td>
                <button class="btn btn-secondary btn-sm" onclick="showScoreDetail(${index})">Insight</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function renderAnalysisContent(filter) {
    const container = document.getElementById('analysis-dynamic-content');
    container.innerHTML = '';
    const analysis = lastAnalysisData.ai_analysis;
    const rejectedList = lastAnalysisData.rejected_candidates || [];
    const rejectedFiles = new Set(rejectedList.map(r => r.filename));

    if (filter === 'shortlist') {
        const shortlisted = Array.isArray(analysis) ? analysis.filter(item => {
            const s = (item.status || "").toLowerCase();
            return !rejectedFiles.has(item.filename) && !s.includes('reject');
        }) : [];

        shortlisted.forEach((item, idx) => {
            renderCandidateCard(item, container, idx);
        });
    } else {
        const rejected = Array.isArray(analysis) ? analysis.filter(item => {
            const s = (item.status || "").toLowerCase();
            return rejectedFiles.has(item.filename) || s.includes('reject');
        }) : [];

        rejected.forEach((item, idx) => {
            renderCandidateCard(item, container, idx, true);
        });

        // Add Rule rejections
        const ruleRejections = rejectedList.filter(r => !analysis.some(a => a.filename === r.filename));
        if (ruleRejections.length > 0) {
            const ruleHeader = document.createElement('h3');
            ruleHeader.textContent = "Logic Level Rejections";
            ruleHeader.style.margin = "40px 0 20px 0";
            container.appendChild(ruleHeader);

            ruleRejections.forEach(r => {
                const card = document.createElement('div');
                card.className = 'candidate-card status-rejected';
                card.innerHTML = `<h4>${r.name || r.filename}</h4><p>${r.reason}</p>`;
                container.appendChild(card);
            });
        }
    }
}

function renderCandidateCard(item, container, index, isRejected = false) {
    const card = document.createElement('div');
    card.className = `candidate-card animate-slide-up`;
    card.style.animationDelay = `${index * 0.1}s`;

    let statusClass = "status-recommended";
    if (isRejected) statusClass = "status-rejected";
    else if (item.status === 'Potential') statusClass = "status-potential";

    card.innerHTML = `
        <div class="card-header">
            <h4>${item.candidate_name || "Anonymous"} <span>${item.filename}</span></h4>
            <span class="status-badge ${statusClass}">${item.status || 'Verified'}</span>
        </div>
        <p class="analysis-text">${item.reasoning}</p>
        <div class="pros-cons">
            <div class="pros">
                <h5>Key Advantages</h5>
                <ul>${(item.strengths || []).slice(0, 3).map(s => `<li>${s}</li>`).join('')}</ul>
            </div>
            <div class="cons">
                <h5>${isRejected ? 'Critical Gaps' : 'Observation'}</h5>
                <ul>${(item.weaknesses || []).slice(0, 3).map(w => `<li>${w}</li>`).join('')}</ul>
            </div>
        </div>
    `;
    container.appendChild(card);
}

// --- Utilities ---
function showNotification(message, type = "info") {
    // Simple alert for now, could be a toast in the future
    alert(message);
}

// Open Folder Link
document.getElementById('open-report-btn').addEventListener('click', async () => {
    if (!currentReportPath) return;
    const formData = new FormData();
    formData.append('path', currentReportPath);
    fetch('http://localhost:8000/open_report', { method: 'POST', body: formData });
});

// Modal Logic placeholder
// Detailed Insight Modal
window.showScoreDetail = function (idx) {
    const cand = lastAnalysisData.candidates[idx];

    // Check if breakdown exists, if not create default
    const bd = cand.score.breakdown || { "Base Score": 0, "AI Bonus": 0, "Final": 0 };

    const details = `
    ----------- CANDIDATE INSIGHT -----------
    Name: ${cand.candidate_name || cand.name}
    File: ${cand.filename}
    Email: ${cand.email || "N/A"} | Phone: ${cand.phone || "N/A"}
    
    ----------- SCORE BREAKDOWN -----------
    Base Score (Skills + Exp):  ${bd["Base Score"] || cand.score.original_score || 0}
    AI Achievement Bonus:       ${bd["AI Bonus"] > 0 ? "+" + bd["AI Bonus"] : bd["AI Bonus"]}
    ---------------------------------------
    FINAL SCORE:                ${cand.score.total}%
    
    ----------- AI REASONING -----------
    ${cand.reasoning || "No detailed AI analysis available for this candidate."}
    
    ----------- STRENGTHS -----------
    ${(cand.strengths || []).map(s => "• " + s).join('\n')}
    `;

    alert(details);
};

