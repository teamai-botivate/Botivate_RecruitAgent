const analyzeBtn = document.getElementById('analyze-btn');
const topNInput = document.getElementById('top-n-input');
const jdDrop = document.getElementById('jd-drop');
const resumeDrop = document.getElementById('resume-drop');

let jdFile = null;
let resumeFiles = [];
let lastAnalysisData = null;
let currentReportPath = "";

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    // Load JD from Generator if present
    const savedJD = localStorage.getItem('recruiter_generated_jd');
    if (savedJD) {
        document.getElementById('jd-text').value = savedJD;
    }
});

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
        // Don't interfere with textarea or direct input clicks
        if (['TEXTAREA', 'INPUT'].includes(e.target.tagName)) return;
        // If click is inside a label with a `for` attribute, let the browser handle it natively
        if (e.target.closest('label[for]')) return;
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

// Gmail OAuth Integration
const gmailCheckbox = document.getElementById('gmail-checkbox');
const gmailInputs = document.getElementById('gmail-inputs');
const gmailConnection = document.getElementById('gmail-connection');
const connectGmailBtn = document.getElementById('connect-gmail-btn');
const gmailStatusBadge = document.getElementById('gmail-status-badge');
const gmailStatusIcon = document.getElementById('gmail-status-icon');
const gmailStatusText = document.getElementById('gmail-status-text');

const API_BASE = 'http://localhost:8000';
const COMPANY_ID = 'default_company';

// Check Gmail connection on page load
async function checkGmailConnection() {
    try {
        const response = await fetch(`${API_BASE}/auth/gmail/status?company_id=${COMPANY_ID}`);
        const data = await response.json();

        if (data.connected) {
            // Gmail is connected
            gmailStatusIcon.textContent = '✅';
            gmailStatusText.textContent = data.email || 'Connected';
            gmailStatusBadge.classList.add('connected');
            connectGmailBtn.textContent = 'Disconnect';
            connectGmailBtn.onclick = disconnectGmail;
        } else {
            // Not connected
            gmailStatusIcon.textContent = '🔗';
            gmailStatusText.textContent = 'Not Connected';
            gmailStatusBadge.classList.remove('connected');
            connectGmailBtn.textContent = 'Connect Gmail';
            connectGmailBtn.onclick = connectGmail;
        }
    } catch (error) {
        console.error('Error checking Gmail status:', error);
    }
}

// Connect Gmail - Opens OAuth popup
function connectGmail() {
    const width = 600;
    const height = 700;
    const left = (screen.width - width) / 2;
    const top = (screen.height - height) / 2;

    const authUrl = `${API_BASE}/auth/gmail/start?company_id=${COMPANY_ID}`;

    window.open(
        authUrl,
        'Gmail OAuth',
        `width=${width},height=${height},left=${left},top=${top}`
    );
}

// Disconnect Gmail
async function disconnectGmail() {
    if (!confirm('Are you sure you want to disconnect Gmail?')) {
        return;
    }

    try {
        connectGmailBtn.disabled = true;
        connectGmailBtn.textContent = 'Disconnecting...';

        const response = await fetch(`${API_BASE}/auth/gmail/disconnect?company_id=${COMPANY_ID}`, {
            method: 'POST'
        });

        const data = await response.json();

        if (data.status === 'success') {
            showNotification('Gmail disconnected successfully', 'success');
            await checkGmailConnection();
        }
    } catch (error) {
        console.error('Error disconnecting Gmail:', error);
        showNotification('Failed to disconnect Gmail', 'error');
    } finally {
        connectGmailBtn.disabled = false;
    }
}

// Listen for OAuth popup success
window.addEventListener('message', (event) => {
    if (event.data.type === 'gmail_connected') {
        console.log('Gmail connected:', event.data.email);
        showNotification(`Gmail connected: ${event.data.email}`, 'success');
        checkGmailConnection();
    }
});

// Gmail toggle - show/hide connection and date picker
if (gmailCheckbox) {
    gmailCheckbox.addEventListener('change', () => {
        if (gmailCheckbox.checked) {
            gmailConnection.classList.remove('hidden');
            gmailInputs.classList.remove('hidden');
        } else {
            gmailConnection.classList.add('hidden');
            gmailInputs.classList.add('hidden');
        }
    });
}

// Check Gmail connection on page load
window.addEventListener('load', () => {
    checkGmailConnection();
});

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
        const response = await fetch('/api/analyze', {
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
            const res = await fetch(`/api/status/${jobId}`);
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
// --- Tab Switching ---
window.switchTab = function (tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(content => content.classList.remove('active'));

    const clickedBtn = document.querySelector(`.tab-btn[onclick="switchTab('${tabName}')"]`);
    if (clickedBtn) clickedBtn.classList.add('active');

    document.getElementById(`${tabName}-view`).classList.add('active');
}

// --- Rendering Logic ---
function renderResults(data) {
    lastAnalysisData = data;
    currentReportPath = data.report_path;
    document.getElementById('results-area').classList.remove('hidden');

    // Render Analysis Cards directly (No more filters)
    renderAnalysisContent();
    renderNotSelectedContent();  // Render not-selected candidates tab
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


// Simplified: Show All Analyzed Candidates (Sorted by Score)
function renderAnalysisContent() {
    const container = document.getElementById('analysis-dynamic-content');
    container.innerHTML = ''; // definitive clear

    let topN = parseInt(topNInput.value);
    if (isNaN(topN) || topN < 1) topN = 5; // Fallback to 5 if input invalid

    // 1. Get List
    let candidates = lastAnalysisData.candidates || [];

    // 2. Strict Slice: Only consider the first Top N (as defined by backend logic)
    // The backend guarantees sorted order: 0..N-1 are the "Selected" set.
    let selected = candidates.slice(0, topN);

    // 3. Status Filter: Hide anyone explicitly marked as "Not Selected" or "Rejected"
    // This handles edge cases where the slice includes someone the backend flagged for rejection (e.g. strict rule failure)
    selected = selected.filter(item => {
        const s = (item.status || "").toLowerCase();
        return !s.includes("not selected") && !s.includes("rejected");
    });

    if (selected.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 40px; color: #6b7280;">
                <p>No qualified candidates found in the top ${topN} selection.</p>
            </div>
        `;
        return;
    }

    selected.forEach((item, idx) => {
        // Double check status before rendering (Redundant but safe)
        const s = (item.status || "").toLowerCase();
        if (s.includes("not selected")) return;

        renderCandidateCard(item, container, idx, false);
    });
}


// Render Not Selected Candidates - HYBRID APPROACH
function renderNotSelectedContent() {
    const container = document.getElementById('notselected-content');
    container.innerHTML = '';

    const topN = parseInt(topNInput.value) || 5;

    // Get all candidates
    const allCandidates = lastAnalysisData.candidates || [];

    // Separate into categories
    const remaining = allCandidates.slice(topN);

    // Further split remaining into analyzed vs not-analyzed  
    const notSelected_analyzed = remaining.filter(c => c.ai_analyzed === true || c.reasoning);
    const notSelected_similarity = remaining.filter(c => c.ai_analyzed === false && !c.reasoning);

    // Section 1: Analyzed but not selected
    if (notSelected_analyzed.length > 0) {
        const section1 = document.createElement('div');
        section1.className = 'not-selected-section';
        section1.innerHTML = `
            <h3 style="color: #f59e0b; margin-bottom: 16px; display: flex; align-items: center; gap: 8px;">
                <i data-lucide="alert-circle" style="width: 20px; height: 20px;"></i>
                Not Selected - AI Analyzed (${notSelected_analyzed.length})
            </h3>
            <p style="opacity: 0.7; font-size: 14px; margin-bottom: 16px;">
                These candidates were analyzed by AI but didn't make the top ${topN} cut
            </p>
        `;

        const grid1 = document.createElement('div');
        grid1.className = 'candidate-grid';
        notSelected_analyzed.forEach((item, idx) => {
            renderCandidateCard(item, grid1, idx, true);
        });
        section1.appendChild(grid1);
        container.appendChild(section1);
    }

    // Section 2: Not analyzed (by similarity only)
    if (notSelected_similarity.length > 0) {
        const section2 = document.createElement('div');
        section2.className = 'not-selected-section';
        section2.style.marginTop = '48px';
        section2.innerHTML = `
            <h3 style="color: #6b7280; margin-bottom: 16px; display: flex; align-items: center; gap: 8px;">
                <i data-lucide="bar-chart-2" style="width: 20px; height: 20px;"></i>
                Not Selected - By Similarity Score (${notSelected_similarity.length})
            </h3>
            <p style="opacity: 0.7; font-size: 14px; margin-bottom: 16px;">
                Ranked by semantic similarity to JD but not selected for detailed AI analysis
            </p>
        `;

        const grid2 = document.createElement('div');
        grid2.className = 'candidate-grid';
        notSelected_similarity.forEach((item, idx) => {
            renderSimilarityCard(item, grid2, idx);
        });
        section2.appendChild(grid2);
        container.appendChild(section2);
    }

    // If both empty
    if (notSelected_analyzed.length === 0 && notSelected_similarity.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 60px 20px; color: rgba(255,255,255,0.6);">
                <i data-lucide="check-circle" style="width: 48px; height: 48px; margin-bottom: 16px;"></i>
                <p>All valid candidates were selected!</p>
            </div>
        `;
    }

    lucide.createIcons();
}

function renderCandidateCard(item, container, index, isRejected = false) {
    const card = document.createElement('div');
    card.className = `candidate-card animate-slide-up`;
    card.style.animationDelay = `${index * 0.1}s`;

    let statusClass = "status-recommended";
    // Smart Status determination
    const s = (item.status || "").toLowerCase();
    if (isRejected || s.includes("reject") || s.includes("review")) statusClass = "status-rejected";
    else if (s.includes("potential")) statusClass = "status-potential";

    // Smart Name Fallback
    let displayName = item.candidate_name;
    if (!displayName || displayName === "Not Found" || displayName === "Unknown") {
        // Fallback to clean filename
        displayName = item.filename.replace(/\.pdf$/i, '').replace(/_/g, ' ');
    }

    // PDF Link
    const pdfLink = `http://localhost:8000/reports/${lastAnalysisData.campaign_folder}/All_Resumes/${item.filename}`;

    // Achievements HTML
    let achievementsHtml = '';
    if (item.hobbies_and_achievements && item.hobbies_and_achievements.length > 0) {
        achievementsHtml = `
        <div class="achievements-section" style="margin-top: 15px; border-top: 1px solid #eee; padding-top: 10px;">
            <h5 style="color: #6366f1; font-size: 0.9em; margin-bottom: 5px;">🏆 Achievements & Hobbies</h5>
            <ul class="achievement-list" style="padding-left: 20px; font-size: 0.9em; color: #555;">
                ${item.hobbies_and_achievements.map(a => `<li>${a}</li>`).join('')}
            </ul>
        </div>`;
    }

    card.innerHTML = `
        <div class="card-header" style="justify-content: space-between; align-items: start;">
            <div>
                <h4 style="margin: 0;">${displayName}</h4>
                <a href="${pdfLink}" target="_blank" style="font-size: 0.8em; color: #6366f1; text-decoration: none; display: flex; align-items: center; gap: 4px; margin-top: 4px;">
                    📄 View Resume <span style="font-size: 10px;">↗</span>
                </a>
            </div>
            <span class="status-badge ${statusClass}">${item.status || 'Analyzed'}</span>
        </div>
        
        <p class="analysis-text" style="margin: 12px 0;">${item.reasoning || "Reasoning not available."}</p>
        
        <div class="pros-cons" style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
            <div class="pros">
                <h5 style="color: #10b981; font-size: 0.9em; margin-bottom: 5px;">✅ Key Advantages</h5>
                <ul style="padding-left: 20px; font-size: 0.9em; margin: 0;">
                    ${(item.strengths || []).slice(0, 3).map(s => `<li>${s}</li>`).join('')}
                </ul>
            </div>
            <div class="cons">
                <h5 style="color: #ef4444; font-size: 0.9em; margin-bottom: 5px;">⚠️ Observation</h5>
                <ul style="padding-left: 20px; font-size: 0.9em; margin: 0;">
                    ${(item.weaknesses || []).slice(0, 3).map(w => `<li>${w}</li>`).join('')}
                </ul>
            </div>
        </div>
        
        ${achievementsHtml}
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
    fetch('/api/open_report', { method: 'POST', body: formData });
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

// --- Handover Logic ---
const rejectProceedBtn = document.getElementById('reject-proceed-btn');
if (rejectProceedBtn) {
    rejectProceedBtn.addEventListener('click', async () => {
        if (!lastAnalysisData || !lastAnalysisData.campaign_folder) {
            alert("Analysis data not found. Please run screening first.");
            return;
        }

        if (!confirm("This will send rejection emails to all 'Not Selected' candidates and proceed to Test Formation. Continue?")) return;

        const reportFolder = lastAnalysisData.campaign_folder;

        // 1. Fetch Not Selected List
        try {
            const resp = await fetch(`http://localhost:8000/reports/${reportFolder}/not_selected_candidates.json`);
            if (!resp.ok) throw new Error("Could not find rejection list.");
            const rejectedList = await resp.json();

            // 2. Extract Emails
            const emails = rejectedList.map(c => c.email).filter(e => e);

            if (emails.length > 0) {
                // 3. Send Rejection
                const sendResp = await fetch('http://localhost:8000/aptitude-api/send-rejection', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        emails: emails,
                        job_title: "Applicant" // Could extract from JD
                    })
                });
                if (!sendResp.ok) alert("Warning: Failed to send some rejection emails.");
                else alert(`Rejection emails sent to ${emails.length} candidates.`);
            } else {
                alert("No candidates to reject (or no emails found). Proceeding.");
            }

            // 4. Save Selected List URL for Aptitude App
            localStorage.setItem('aptitude_candidates_url', `http://localhost:8000/reports/${reportFolder}/selected_candidates.json`);

            // 5. Navigate
            window.location.href = '/aptitude/index.html';

        } catch (e) {
            alert("Error during handover: " + e.message);
        }
    });
}

// --- All Candidates Modal ---
const viewAllCandidatesBtn = document.getElementById('view-all-candidates-btn');
if (viewAllCandidatesBtn) {
    viewAllCandidatesBtn.addEventListener('click', () => {
        if (!lastAnalysisData) {
            alert("No analysis data available. Please run screening first.");
            return;
        }
        showCandidatesModal();
    });
}

function showCandidatesModal() {
    const modal = document.getElementById('candidates-modal');
    const topN = parseInt(topNInput.value) || 5;

    // Get all analyzed candidates
    const allAnalyzed = lastAnalysisData.candidates.filter(c => c.reasoning);
    const selected = allAnalyzed.slice(0, topN);
    const notSelected = allAnalyzed.slice(topN);

    // Populate Selected Candidates Table
    const selectedTbody = document.getElementById('selected-candidates-tbody');
    selectedTbody.innerHTML = '';

    if (selected.length === 0) {
        selectedTbody.innerHTML = '<tr><td colspan="4" style="text-align: center; opacity: 0.6;">No selected candidates</td></tr>';
    } else {
        selected.forEach(cand => {
            const pdfUrl = `/reports/${lastAnalysisData.campaign_folder}/All_Resumes/${cand.filename}`;
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${cand.name || 'Unknown'}</td>
                <td>${cand.email || 'N/A'}</td>
                <td><span class="score-pill">${cand.score.total}</span></td>
                <td>
                    <a href="${pdfUrl}" target="_blank" class="glass-btn secondary-btn" style="padding: 6px 12px; font-size: 12px;">
                        <i data-lucide="file-text" style="width: 14px; height: 14px;"></i> View PDF
                    </a>
                </td>
            `;
            selectedTbody.appendChild(row);
        });
    }

    // Populate Not Selected Candidates Table
    const notSelectedTbody = document.getElementById('notselected-candidates-tbody');
    notSelectedTbody.innerHTML = '';

    if (notSelected.length === 0) {
        notSelectedTbody.innerHTML = '<tr><td colspan="4" style="text-align: center; opacity: 0.6;">No not-selected candidates</td></tr>';
    } else {
        notSelected.forEach(cand => {
            const pdfUrl = `/reports/${lastAnalysisData.campaign_folder}/All_Resumes/${cand.filename}`;
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${cand.name || 'Unknown'}</td>
                <td>${cand.email || 'N/A'}</td>
                <td><span class="score-pill">${cand.score.total}</span></td>
                <td>
                    <a href="${pdfUrl}" target="_blank" class="glass-btn secondary-btn" style="padding: 6px 12px; font-size: 12px;">
                        <i data-lucide="file-text" style="width: 14px; height: 14px;"></i> View PDF
                    </a>
                </td>
            `;
            notSelectedTbody.appendChild(row);
        });
    }

    // Show modal
    modal.classList.remove('hidden');
    lucide.createIcons();
}

function closeCandidatesModal() {
    const modal = document.getElementById('candidates-modal');
    modal.classList.add('hidden');
}

// Close modal on outside click
document.getElementById('candidates-modal')?.addEventListener('click', (e) => {
    if (e.target.id === 'candidates-modal') {
        closeCandidatesModal();
    }
});

// Render similarity-only cards (for candidates not AI-analyzed)
function renderSimilarityCard(item, container, index) {
    const card = document.createElement('div');
    card.className = 'candidate-card similarity-card animate-slide-up';
    card.style.animationDelay = `${index * 0.1}s`;
    card.style.opacity = '0.85';
    card.style.border = '1px solid rgba(107, 114, 128, 0.3)';

    const pdfUrl = `/reports/${lastAnalysisData.campaign_folder}/All_Resumes/${item.filename}`;
    const vectorScore = item.vector_score || 0;

    card.innerHTML = `
        <div class="card-header-row">
            <h4>${item.name || 'Unknown'}</h4>
            <span class="status-badge" style="background: rgba(107, 114, 128, 0.2); color: #9ca3af;">
                Similarity Only
            </span>
        </div>
        
        <div class="score-row" style="margin-top: 12px;">
            <div class="score-item">
                <span class="score-label">Semantic Match</span>
                <span class="score-value" style="color: #9ca3af;">${(vectorScore * 100).toFixed(1)}%</span>
            </div>
        </div>
        
        <div class="info-grid" style="margin-top: 16px;">
            <div class="info-item">
                <i data-lucide="mail"></i>
                <span>${item.email || 'N/A'}</span>
            </div>
        </div>
        
        <p style="margin-top: 12px; opacity: 0.6; font-size: 13px; display: flex; align-items: center; gap: 6px;">
            <i data-lucide="info" style="width: 14px; height: 14px;"></i>
            Not selected for detailed AI analysis (ranked by similarity only)
        </p>
        
        <div class="card-actions" style="margin-top: 16px;">
            <a href="${pdfUrl}" target="_blank" class="action-btn" style="background: rgba(107, 114, 128, 0.1);">
                <i data-lucide="file-text"></i> View Resume
            </a>
        </div>
    `;

    container.appendChild(card);
}