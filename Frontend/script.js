
const analyzeBtn = document.getElementById('analyze-btn');
const topNInput = document.getElementById('top-n-input');
const jdDrop = document.getElementById('jd-drop');
const resumeDrop = document.getElementById('resume-drop');

let jdFile = null;
let resumeFiles = [];

// Drag & Drop Handlers
function setupDrop(dropArea, callback) {
    dropArea.addEventListener('dragover', (e) => { e.preventDefault(); dropArea.style.borderColor = '#4f46e5'; });
    dropArea.addEventListener('dragleave', (e) => { e.preventDefault(); dropArea.style.borderColor = '#cbd5e1'; });
    dropArea.addEventListener('drop', (e) => {
        e.preventDefault();
        dropArea.style.borderColor = '#cbd5e1';
        callback(e.dataTransfer.files);
    });
    dropArea.addEventListener('click', (e) => {
        // Prevent file upload when clicking textarea, label, or ANY input (date, checkbox, range, etc.)
        if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'LABEL' || e.target.tagName === 'INPUT') return;
        dropArea.querySelector('input[type="file"]').click();
    });
    dropArea.querySelector('input').addEventListener('change', (e) => {
        callback(e.target.files);
    });
}

setupDrop(jdDrop, (files) => {
    if (files.length > 0) {
        jdFile = files[0];
        document.getElementById('jd-name').textContent = `✅ ${jdFile.name}`;
    }
});

setupDrop(resumeDrop, (files) => {
    resumeFiles = Array.from(files);
    document.getElementById('resume-count').textContent = `✅ ${resumeFiles.length} resumes loaded`;
});

// Gmail Checkbox Logic
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

// Analyze
analyzeBtn.addEventListener('click', async () => {
    const jdText = document.getElementById('jd-text') ? document.getElementById('jd-text').value.trim() : "";
    const startDate = document.getElementById('start-date').value;
    const endDate = document.getElementById('end-date').value;
    const useGmail = document.getElementById('gmail-checkbox') ? document.getElementById('gmail-checkbox').checked : false;

    // Common Validation: JD Required
    if (!jdFile && !jdText) {
        alert("Please provide a Job Description (Paste Text or Upload File)!");
        return;
    }

    // Validation: At least one source
    if (resumeFiles.length === 0 && !useGmail) {
        alert("Please upload resumes OR check 'Include Gmail Resumes'!");
        return;
    }

    // Gmail Validation
    if (useGmail && (!startDate || !endDate)) {
        alert("Please select Start and End dates for Gmail search.");
        return;
    }

    // UI Loading
    document.getElementById('loader').classList.remove('hidden');
    document.getElementById('results-area').classList.add('hidden');
    analyzeBtn.disabled = true;

    const formData = new FormData();
    if (jdFile) {
        formData.append('jd_file', jdFile);
    } else {
        formData.append('jd_text_input', jdText);
    }
    formData.append('top_n', topNInput.value);

    // Append Files
    resumeFiles.forEach(file => {
        formData.append('resume_files', file);
    });

    // Append Gmail Data if checked
    if (useGmail) {
        formData.append('start_date', startDate);
        formData.append('end_date', endDate);
    }

    try {
        const response = await fetch('http://localhost:8000/analyze', {
            method: 'POST',
            body: formData
        });

        if (!response.ok) throw new Error("Server Error");

        const data = await response.json();

        // Handle Backend Errors
        if (data.status === "error" || !data.candidates) {
            throw new Error(data.message || data.detail || "Unknown Backend Error");
        }

        renderResults(data);

    } catch (error) {
        alert(error.message);
    } finally {
        document.getElementById('loader').classList.add('hidden');
        analyzeBtn.disabled = false;
    }
});

// Open Report Folder
const openReportBtn = document.getElementById('open-report-btn');
let currentReportPath = "";

openReportBtn.addEventListener('click', async () => {
    if (!currentReportPath) {
        alert("No report generated yet.");
        return;
    }
    const formData = new FormData();
    formData.append('path', currentReportPath);
    try {
        await fetch('http://localhost:8000/open_report', { method: 'POST', body: formData });
    } catch (e) {
        alert("Could not open folder.");
    }
});

// Tab Switching
window.switchTab = function (tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

    const clickedBtn = document.querySelector(`.tab-btn[onclick="switchTab('${tabName}')"]`);
    if (clickedBtn) clickedBtn.classList.add('active');

    if (tabName === 'report') {
        document.getElementById('report-view').classList.add('active');
    } else {
        document.getElementById('table-view').classList.add('active');
    }
}

/* Modal Logic */
const modalHtml = `
<div id="score-modal" class="modal hidden">
    <div class="modal-content">
        <div class="modal-header">
            <h3 id="modal-title">Score Breakdown</h3>
            <span class="close-modal">&times;</span>
        </div>
        <div id="modal-body"></div>
    </div>
</div>
`;
document.body.insertAdjacentHTML('beforeend', modalHtml);

const modal = document.getElementById('score-modal');
const closeModal = document.querySelector('.close-modal');
if (closeModal) closeModal.onclick = () => modal.classList.add('hidden');
window.onclick = (e) => { if (e.target == modal) modal.classList.add('hidden'); };

window.showScoreDetail = function (index) {
    if (!lastAnalysisData || !lastAnalysisData.candidates[index]) return;
    const cand = lastAnalysisData.candidates[index];

    document.getElementById('modal-body').innerHTML = `
        <div class="score-row"><span><strong>Total Score:</strong></span> <span><strong>${cand.score.total.toFixed(1)}</strong></span></div>
        <div class="score-row"><span>Keywords (25%):</span> <span>${cand.score.keyword_score.toFixed(1)}</span></div>
        <div class="score-row"><span>Experience (20%):</span> <span>${cand.score.experience_score.toFixed(1)}</span></div>
        <div class="score-row"><span>Education (10%):</span> <span>${cand.score.education_score.toFixed(1)}</span></div>
        <div class="score-row"><span>Visuals/Format (30%):</span> <span>${cand.score.visual_score.toFixed(1)}</span></div>
        <div class="score-row"><span>Format Valid:</span> <span>${cand.score.format_score.toFixed(1)}</span></div>
        <div class="score-row"><span>Semantic Match:</span> <span>${cand.semantic_score.toFixed(2)}</span></div>
    `;
    document.getElementById('modal-title').innerText = `Analysis: ${cand.name || cand.filename}`;
    modal.classList.remove('hidden');
}

let lastAnalysisData = null;

window.switchAnalysisFilter = function (filter) {
    document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(`filter-${filter}`).classList.add('active');
    renderAnalysisContent(filter);
}

function renderCard(item, container) {
    const card = document.createElement('div');
    card.className = 'candidate-card';

    // Determine strict status
    const allRejected = lastAnalysisData.rejected_candidates || [];
    const isHardRejected = allRejected.some(r => r.filename === item.filename);
    const isSoftRejected = !isHardRejected && (item.status === 'Rejected' || (item.status || "").toLowerCase().includes("reject"));

    let displayStatus = item.status;
    let badgeClass = 'badge-yellow';

    if (isHardRejected) {
        displayStatus = "Rejected"; // Rule Failure
        badgeClass = 'badge-red';
    } else if (isSoftRejected) {
        displayStatus = "Not Selected"; // Low Score
        badgeClass = 'badge-yellow';
    } else if (item.status === 'Recommended') {
        badgeClass = 'badge-green';
    } else if (item.status === 'Potential') {
        badgeClass = 'badge-yellow';
    }

    card.innerHTML = `
    <div class="card-header">
        <h4>${item.candidate_name || "Unknown"} <span>${item.filename}</span></h4>
        <span class="badge ${badgeClass}">${displayStatus}</span>
    </div>
    <p class="analysis-text">${item.reasoning}</p>
    <div class="pros-cons">
        <div class="pros">
            <h5>Strengths</h5>
            <ul>${(item.strengths || []).map(s => `<li>${s}</li>`).join('')}</ul>
        </div>
        <div class="cons">
            <h5>${isHardRejected || isSoftRejected ? 'Rejection Factors & Gaps' : 'Areas of Concern'}</h5>
            <ul>${(item.weaknesses || []).map(w => `<li>${w}</li>`).join('')}</ul>
        </div>
    </div>
    `;
    container.appendChild(card);
}

function renderAnalysisContent(filter) {
    const container = document.getElementById('analysis-dynamic-content');
    container.innerHTML = '';
    const analysis = lastAnalysisData.ai_analysis;
    const allRejected = lastAnalysisData.rejected_candidates || [];
    const rejectedFilenames = new Set(allRejected.map(r => r.filename));

    if (filter === 'shortlist') {
        if (!analysis || (Array.isArray(analysis) && analysis.length > 0 && analysis[0].filename === 'report')) {
            container.innerHTML = `<pre class="analysis-text" style="white-space: pre-wrap;">${lastAnalysisData.ai_report || "No analysis available"}</pre>`;
            return;
        }

        if (Array.isArray(analysis)) {
            // STRICT FILTER: Exclude Hard Rejects (Backend) AND Soft Rejects (AI Status)
            analysis.filter(item => {
                const s = (item.status || "").toLowerCase();
                return !rejectedFilenames.has(item.filename) && !s.includes('reject');
            }).forEach(item => {
                renderCard(item, container);
            });
        }
    } else if (filter === 'rejected') {
        let analyzedCount = 0;
        const analyzedFilenames = new Set();

        // 1. Render Detailed Cards for AI-Analyzed Rejected Candidates
        if (Array.isArray(analysis)) {
            // Include ONLY those who are in the backend rejection list OR explicitly marked rejected by AI
            analysis.filter(item => {
                const s = (item.status || "").toLowerCase();
                return rejectedFilenames.has(item.filename) || s.includes('reject');
            }).forEach(item => {
                renderCard(item, container);
                analyzedFilenames.add(item.filename);
                analyzedCount++;
            });
        }

        // 2. Render Table for Validated Rejections (Page Limits, etc) NOT in AI Analysis
        const remaining = allRejected.filter(r => !analyzedFilenames.has(r.filename));

        if (remaining.length > 0) {
            const h4 = document.createElement('h4');
            h4.style.margin = "2rem 0 1rem 0";
            h4.textContent = "Automatically Rejected (Rules)";
            container.appendChild(h4);

            const table = document.createElement('table');
            table.className = 'rejected-table';
            table.innerHTML = `<thead><tr><th>Candidate</th><th>Rejection Reason</th></tr></thead><tbody>
             ${remaining.map(r => `<tr><td><strong>${r.name || "Unknown"}</strong><br>${r.filename}</td><td>${r.reason}</td></tr>`).join('')}
             </tbody>`;
            container.appendChild(table);
        } else if (analyzedCount === 0) {
            container.innerHTML = '<p class="analysis-text">No candidates were rejected.</p>';
        }
    }
}

function renderResults(data) {
    document.getElementById('results-area').classList.remove('hidden');
    currentReportPath = data.report_path;
    lastAnalysisData = data;

    // Setup Analysis Area
    const reportBox = document.getElementById('ai-report-content');
    reportBox.innerHTML = `
        <div class="filters-bar">
            <button id="filter-shortlist" class="filter-btn active" onclick="switchAnalysisFilter('shortlist')">✅ Shortlisted Candidates</button>
            <button id="filter-rejected" class="filter-btn" onclick="switchAnalysisFilter('rejected')">🚫 Rejected Candidates (${data.rejected_count || 0})</button>
        </div>
        <div id="analysis-dynamic-content"></div>
    `;

    switchAnalysisFilter('shortlist'); // Default View

    // Render Table (Show ONLY Top N Selected Candidates)
    const tbody = document.getElementById('results-body');
    tbody.innerHTML = '';

    const topN = parseInt(document.getElementById('top-n-input').value) || 5;

    // Filter out Soft Rejects (AI Status)
    const statusMap = new Map();
    if (data.ai_analysis) data.ai_analysis.forEach(item => statusMap.set(item.filename, (item.status || "").toLowerCase()));

    data.candidates.filter(cand => {
        const s = statusMap.get(cand.filename);
        if (s && s.includes('reject')) return false;
        return true;
    }).slice(0, topN).forEach((cand, index) => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td>
                <strong>${cand.name || "Unknown"}</strong>
                <br><span style="font-size: 0.8em; color: gray;">${cand.filename}</span>
            </td>
            <td><strong>${cand.score.total.toFixed(1)}</strong> / 100</td>
            <td>${cand.score.keyword_score.toFixed(1)}</td>
            <td>${cand.score.experience_score.toFixed(1)}</td>
            <td>
                <button class="primary-btn" style="padding: 0.25rem 0.5rem; font-size: 0.8rem;" onclick='showScoreDetail(${index})'>View Breakdown</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}
