document.addEventListener('DOMContentLoaded', () => {
    initializeElements();
    lucide.createIcons();
    setupEventListeners();
});

// --- Constants ---
const NEON_INNER_HTML = `
    <div class="neon-checkbox__frame">
        <div class="neon-checkbox__box">
            <div class="neon-checkbox__check-container">
                <svg viewBox="0 0 24 24" class="neon-checkbox__check">
                    <path d="M3,12.5l7,7L21,5"></path>
                </svg>
            </div>
            <div class="neon-checkbox__glow"></div>
            <div class="neon-checkbox__borders">
                <span></span><span></span><span></span><span></span>
            </div>
        </div>
        <div class="neon-checkbox__effects">
            <div class="neon-checkbox__particles">
                <span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span><span></span>
            </div>
            <div class="neon-checkbox__rings">
                <div class="ring"></div><div class="ring"></div><div class="ring"></div>
            </div>
            <div class="neon-checkbox__sparks">
                <span></span><span></span><span></span><span></span>
            </div>
        </div>
    </div>
`;

// --- State Management ---
let allMcqs = [];
let allCodingQuestions = [];
let selectedMcqs = new Set();
let selectedCoding = new Set();

// --- Elements ---
let generateBtn, jdInput, fileInput, fileNameDisplay, loader;
let selectionSection, questionsList, selectedCount, selectAllCheckbox, doneBtn;
let finalResultSection, finalAptitudeList, finalCodingList, codingQuestionsList, selectAllCoding;
let copyBtn, downloadPdfBtn, emailBtn;
let emailModal, closeEmailModal, cancelEmailBtn, confirmSendEmailBtn, receiverEmailsInput;
let viewAnalysisBtn, analysisDashboard, mainGeneratorCard, jobRolesView, candidateDetailsView, detailJobTitleText, candidatesTbody;

// --- Setup ---
function initializeElements() {
    generateBtn = document.getElementById('generate-aptitude-btn');
    jdInput = document.getElementById('jd-input');
    fileInput = document.getElementById('file-upload');
    fileNameDisplay = document.getElementById('file-name');
    loader = document.getElementById('loader');

    selectionSection = document.getElementById('selection-section');
    questionsList = document.getElementById('questions-list');
    selectedCount = document.getElementById('selected-count');
    selectAllCheckbox = document.getElementById('select-all-checkbox');
    doneBtn = document.getElementById('done-btn');

    finalResultSection = document.getElementById('final-result-section');
    finalAptitudeList = document.getElementById('final-aptitude-list');
    finalCodingList = document.getElementById('final-coding-list');
    codingQuestionsList = document.getElementById('coding-questions-list');
    selectAllCoding = document.getElementById('select-all-coding');
    copyBtn = document.getElementById('copy-btn');
    downloadPdfBtn = document.getElementById('download-pdf-btn');
    emailBtn = document.getElementById('email-btn');

    emailModal = document.getElementById('email-modal');
    closeEmailModal = document.getElementById('close-email-modal');
    cancelEmailBtn = document.getElementById('cancel-email');
    confirmSendEmailBtn = document.getElementById('confirm-send-email');
    receiverEmailsInput = document.getElementById('receiver-emails');

    viewAnalysisBtn = document.getElementById('view-analysis-btn');
    analysisDashboard = document.getElementById('analysis-dashboard-section');
    mainGeneratorCard = document.querySelector('.generator-layout .main-card:first-child');
    jobRolesView = document.getElementById('job-roles-view');
    candidateDetailsView = document.getElementById('candidate-details-view');
    detailJobTitleText = document.getElementById('detail-job-title');
    candidatesTbody = document.getElementById('candidates-tbody');
}

function setupEventListeners() {
    // Pre-fill JD from Generator
    const savedJD = localStorage.getItem('recruiter_generated_jd');
    if (savedJD) {
        jdInput.value = savedJD;
    }

    // File Upload handling
    fileInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) {
            fileNameDisplay.textContent = file.name;
            const reader = new FileReader();
            reader.onload = (re) => {
                jdInput.value = re.target.result;
            };
            reader.readAsText(file);
        }
    });

    // Step 1: Generate Real Questions from Backend
    generateBtn.addEventListener('click', async () => {
        const jdText = jdInput.value.trim();
        if (!jdText) {
            alert("Please paste a Job Description or upload a file first.");
            return;
        }

        showLoader(true);

        try {
            const response = await fetch('/aptitude-api/generate-aptitude', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ jd_text: jdText })
            });

            if (!response.ok) throw new Error("Failed to generate questions");

            const data = await response.json();
            console.log("DEBUG: Received Data:", data);
            allMcqs = data.mcqs || [];
            allCodingQuestions = data.coding_questions || [];

            renderMcqsToSelect();
            renderCodingToSelect();

            showLoader(false);
            showSection(selectionSection);
            selectionSection.scrollIntoView({ behavior: 'smooth' });
        } catch (error) {
            console.error("GENERATION ERROR:", error);
            alert(`Error: ${error.message}\n\nPlease ensure the backend is running on port 8002 and your network allows the connection.`);
            showLoader(false);
        }
    });

    // Selection Tabs Logic
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.tab;
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            document.querySelectorAll('.tab-content').forEach(c => c.classList.add('hidden'));
            document.getElementById(tab === 'mcqs' ? 'mcq-selection-view' : 'coding-selection-view').classList.remove('hidden');
        });
    });

    // Step 2: Confirmation
    doneBtn.addEventListener('click', () => {
        if (selectedMcqs.size === 0 && selectedCoding.size === 0) {
            alert("Please select at least one question (MCQ or Coding).");
            return;
        }
        renderFinalLists();
        showSection(finalResultSection);
        finalResultSection.scrollIntoView({ behavior: 'smooth' });
    });

    // Output Tabs Logic
    document.querySelectorAll('.out-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const t = btn.dataset.outTab;
            document.querySelectorAll('.out-tab-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            document.querySelectorAll('.out-tab-content').forEach(c => c.classList.add('hidden'));
            document.getElementById(t).classList.remove('hidden');
        });
    });

    // Final: Actions
    copyBtn.addEventListener('click', copyToClipboard);
    downloadPdfBtn.addEventListener('click', simulatePdfDownload);

    // Modal Events
    emailBtn.addEventListener('click', async () => {
        emailModal.classList.remove('hidden');

        // Auto-fill from Resume Screening
        const candidatesUrl = localStorage.getItem('aptitude_candidates_url');
        if (candidatesUrl && !receiverEmailsInput.value.trim()) {
            try {
                receiverEmailsInput.placeholder = "Loading candidates...";
                const resp = await fetch(candidatesUrl);
                if (resp.ok) {
                    const candidates = await resp.json();
                    const emails = candidates.map(c => c.email).filter(e => e).join(', ');
                    receiverEmailsInput.value = emails;
                }
            } catch (e) {
                console.error("Auto-fill failed", e);
                receiverEmailsInput.placeholder = "Failed to load candidates. Please paste manually.";
            }
        }
    });

    closeEmailModal.addEventListener('click', () => emailModal.classList.add('hidden'));
    cancelEmailBtn.addEventListener('click', () => emailModal.classList.add('hidden'));

    confirmSendEmailBtn.addEventListener('click', async () => {
        const emailsString = receiverEmailsInput.value.trim();
        if (!emailsString) {
            alert("Please enter at least one email address.");
            return;
        }

        // Dynamically get Job Title from JD text (looking for 'JOB TITLE: ...')
        const jdValue = jdInput.value;
        const jobTitleMatch = jdValue.match(/JOB TITLE:\s*(.*)/i);
        let jobTitle = "Technical Assessment";

        if (jobTitleMatch && jobTitleMatch[1]) {
            jobTitle = jobTitleMatch[1].trim();
        } else {
            // Fallback to header if JD parsing fails
            const headerTitle = document.querySelector('.main-generator h1')?.textContent.replace('Generated Questions for: ', '').trim();
            if (headerTitle) jobTitle = headerTitle;
        }

        const emailsArray = emailsString.split(',').map(e => e.trim()).filter(e => e);

        // Use current window location to generate link (helps in mobile/network testing)
        const baseUrl = window.location.origin + "/aptitude/test.html";
        const assessmentLink = `${baseUrl}?role=${encodeURIComponent(jobTitle)}&token=${Math.random().toString(36).substr(2, 9)}`;

        // Show loading state on button
        confirmSendEmailBtn.innerHTML = '<span>Sending...</span><i class="ai-spinner-small"></i>';
        confirmSendEmailBtn.disabled = true;

        try {
            const response = await fetch('/aptitude-api/send-assessment', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    emails: emailsArray,
                    job_title: jobTitle,
                    mcq_count: selectedMcqs.size,
                    coding_count: selectedCoding.size,
                    assessment_link: assessmentLink,
                    mcqs: Array.from(selectedMcqs),
                    coding_questions: Array.from(selectedCoding)
                })
            });

            if (!response.ok) {
                const err = await response.json();
                throw new Error(err.detail || "Failed to send emails");
            }

            await showCustomAlert("✅ Success!", `Assessments have been delivered to ${emailsArray.length} candidates successfully.`);
            emailModal.classList.add('hidden');
            receiverEmailsInput.value = '';
        } catch (error) {
            console.error(error);
            showCustomAlert("❌ Error", "Failed to complete request: " + error.message);
        } finally {
            confirmSendEmailBtn.innerHTML = '<span>Send Assessment</span><i data-lucide="send"></i>';
            confirmSendEmailBtn.disabled = false;
            lucide.createIcons();
        }
    });

    // Analysis Events
    viewAnalysisBtn.addEventListener('click', showAnalysisDashboard);

    // Select All Toggle (MCQs)
    selectAllCheckbox.addEventListener('change', () => {
        const isChecked = selectAllCheckbox.checked;
        const items = questionsList.querySelectorAll('.question-item');
        selectedMcqs.clear();
        items.forEach((item, index) => {
            const qObj = allMcqs[index];
            const checkbox = item.querySelector('.q-real-checkbox');
            if (isChecked) {
                item.classList.add('selected');
                checkbox.checked = true;
                selectedMcqs.add(qObj);
            } else {
                item.classList.remove('selected');
                checkbox.checked = false;
            }
        });
        updateCount();
    });

    // Select All Toggle (Coding)
    if (selectAllCoding) {
        selectAllCoding.addEventListener('change', () => {
            const isChecked = selectAllCoding.checked;
            const items = codingQuestionsList.querySelectorAll('.question-item');
            selectedCoding.clear();
            items.forEach((item, index) => {
                const cObj = allCodingQuestions[index];
                const checkbox = item.querySelector('.c-real-checkbox');
                if (isChecked) {
                    item.classList.add('selected');
                    checkbox.checked = true;
                    selectedCoding.add(cObj);
                } else {
                    item.classList.remove('selected');
                    checkbox.checked = false;
                }
            });
            updateCount();
        });
    }
}

// --- Logic Functions ---

function renderMcqsToSelect() {
    questionsList.innerHTML = '';
    selectedMcqs.clear();
    selectAllCheckbox.checked = false;
    updateCount();

    allMcqs.forEach((qObj, index) => {
        const item = document.createElement('div');
        item.className = 'question-item';

        const questionText = qObj.question;
        const options = qObj.options || [];
        const qId = qObj.id || `Q${index + 1}`;

        let optionsHtml = `
            <div class="options-grid">
                ${options.map((opt, i) => `<div class="option-box"><span>${String.fromCharCode(65 + i)})</span> ${opt}</div>`).join('')}
            </div>
        `;

        item.innerHTML = `
            <div class="q-checkbox-wrapper">
                <label class="neon-checkbox">
                    <input type="checkbox" class="q-real-checkbox">
                    ${NEON_INNER_HTML}
                </label>
            </div>
            <div class="q-content">
                <div class="q-id-text">${qId}: ${questionText}</div>
                ${optionsHtml}
            </div>
        `;

        const checkbox = item.querySelector('.q-real-checkbox');
        item.addEventListener('click', (e) => {
            // If clicking the checkbox area itself, let the label/input handle it
            if (e.target.closest('.neon-checkbox')) return;

            checkbox.checked = !checkbox.checked;
            toggleMcqSelection();
        });
        checkbox.addEventListener('change', toggleMcqSelection);

        function toggleMcqSelection() {
            if (checkbox.checked) {
                item.classList.add('selected');
                selectedMcqs.add(qObj);
            } else {
                item.classList.remove('selected');
                selectedMcqs.delete(qObj);
            }
            selectAllCheckbox.checked = (selectedMcqs.size === allMcqs.length);
            updateCount();
        }

        questionsList.appendChild(item);
    });
    lucide.createIcons();
}

function renderCodingToSelect() {
    codingQuestionsList.innerHTML = '';
    selectedCoding.clear();

    allCodingQuestions.forEach((cObj, index) => {
        const item = document.createElement('div');
        item.className = 'question-item';

        item.innerHTML = `
            <div class="q-checkbox-wrapper">
                <label class="neon-checkbox">
                    <input type="checkbox" class="c-real-checkbox">
                    ${NEON_INNER_HTML}
                </label>
            </div>
            <div class="q-content">
                <div class="q-id-text">${cObj.id || "C" + (index + 1)}: ${String(cObj.title || cObj.name || cObj.problem_name || "Untitled Question")}</div>
                <div class="q-desc">${String(cObj.description || cObj.problem || cObj.desc || cObj.problem_statement || "No description provided.")}</div>
                ${(cObj.constraints || cObj.constraint) ? `<div class="q-constraints" style="font-size: 0.8rem; color: #ef4444; font-weight: 700; margin-top: 8px;">Constraints: ${String(cObj.constraints || cObj.constraint)}</div>` : ''}
                <div class="code-example">
                    <span class="example-label">Example Input</span>
                    <pre style="white-space: pre-wrap;">${typeof (cObj.example_input || cObj.input) === 'object' ? JSON.stringify(cObj.example_input || cObj.input, null, 2) : String(cObj.example_input || cObj.input || "N/A")}</pre>
                    <span class="example-label" style="margin-top:10px;">Example Output</span>
                    <pre style="white-space: pre-wrap;">${typeof (cObj.example_output || cObj.output) === 'object' ? JSON.stringify(cObj.example_output || cObj.output, null, 2) : String(cObj.example_output || cObj.output || "N/A")}</pre>
                </div>
            </div>
        `;

        const checkbox = item.querySelector('.c-real-checkbox');
        item.addEventListener('click', (e) => {
            // If clicking the checkbox area itself, let the label/input handle it
            if (e.target.closest('.neon-checkbox')) return;

            checkbox.checked = !checkbox.checked;
            toggleCodingSelection();
        });
        checkbox.addEventListener('change', toggleCodingSelection);

        function toggleCodingSelection() {
            if (checkbox.checked) {
                item.classList.add('selected');
                selectedCoding.add(cObj);
            } else {
                item.classList.remove('selected');
                selectedCoding.delete(cObj);
            }
            // Update Select All checkbox state
            selectAllCoding.checked = (selectedCoding.size === allCodingQuestions.length);
            updateCount();
        }

        codingQuestionsList.appendChild(item);
    });
    lucide.createIcons();
}

function updateCount() {
    selectedCount.textContent = selectedMcqs.size + selectedCoding.size;
}

function renderFinalLists() {
    finalAptitudeList.innerHTML = '';
    finalCodingList.innerHTML = '';

    // Render MCQs
    Array.from(selectedMcqs).forEach((qObj, i) => {
        const container = document.createElement('div');
        container.className = 'final-q-card';
        const optionsHtml = `
            <div class="final-options-grid">
                ${(qObj.options || []).map((opt, i) => `<div class="final-opt"><span>${String.fromCharCode(65 + i)})</span> ${opt}</div>`).join('')}
            </div>
        `;
        container.innerHTML = `
            <div class="final-q-text"><strong>Q${i + 1}:</strong> ${qObj.question}</div>
            ${optionsHtml}
            <div class="final-answer">Correct Answer: ${qObj.answer}</div>
        `;
        finalAptitudeList.appendChild(container);
    });

    // Render Coding
    Array.from(selectedCoding).forEach((cObj, i) => {
        const container = document.createElement('div');
        container.className = 'final-q-card';
        const title = String(cObj.title || cObj.name || cObj.problem_name || "Untitled Question");
        const desc = String(cObj.description || cObj.problem || cObj.desc || cObj.problem_statement || "No description provided.");
        const constraints = String(cObj.constraints || cObj.constraint || "");
        const input = typeof (cObj.example_input || cObj.input) === 'object' ? JSON.stringify(cObj.example_input || cObj.input, null, 2) : String(cObj.example_input || cObj.input || "N/A");
        const output = typeof (cObj.example_output || cObj.output) === 'object' ? JSON.stringify(cObj.example_output || cObj.output, null, 2) : String(cObj.example_output || cObj.output || "N/A");

        container.innerHTML = `
            <div class="final-q-text"><strong>C${i + 1}:</strong> ${title}</div>
            <div class="q-desc">${desc}</div>
            ${constraints ? `<div class="q-constraints" style="font-size: 0.85rem; color: #ef4444; font-weight: 700; margin-bottom: 10px;">Constraints: ${constraints}</div>` : ''}
            <div class="code-example">
                <span class="example-label">Example Input</span> <pre>${input}</pre>
                <span class="example-label" style="margin-top:10px;">Example Output</span> <pre>${output}</pre>
            </div>
        `;
        finalCodingList.appendChild(container);
    });
}

function showLoader(show) {
    if (show) loader.classList.remove('hidden');
    else loader.classList.add('hidden');
}

function showSection(section) {
    section.classList.remove('hidden');
}

function copyToClipboard() {
    let text = "--- MCQs ---\n\n";
    Array.from(selectedMcqs).forEach((q, i) => {
        text += `Q${i + 1}: ${q.question}\nOptions: ${q.options.join(', ')}\nAnswer: ${q.answer}\n\n`;
    });

    if (selectedCoding.size > 0) {
        text += "\n--- Coding Questions ---\n\n";
        Array.from(selectedCoding).forEach((c, i) => {
            text += `C${i + 1}: ${c.title}\nDescription: ${c.description}\nExample Input: ${c.example_input}\nExample Output: ${c.example_output}\n\n`;
        });
    }

    navigator.clipboard.writeText(text).then(() => {
        const originalText = copyBtn.innerHTML;
        copyBtn.innerHTML = '<i data-lucide="check"></i> Copied!';
        lucide.createIcons();
        setTimeout(() => {
            copyBtn.innerHTML = originalText;
            lucide.createIcons();
        }, 2000);
    });
}

function simulatePdfDownload() {
    alert("In the full implementation, this will generate a formatted PDF of your selected questions.");
}

// --- Custom Modal Helper ---
const confirmModal = document.getElementById('confirm-modal');
const confirmTitle = document.getElementById('confirm-title');
const confirmMsg = document.getElementById('confirm-message');
const confirmOkBtn = document.getElementById('confirm-ok-btn');
const confirmCancelBtn = document.getElementById('confirm-cancel-btn');
const closeConfirmBtn = document.getElementById('close-confirm');

function showCustomAlert(title, message) {
    confirmTitle.textContent = title;
    confirmMsg.textContent = message;
    confirmCancelBtn.classList.add('hidden');
    confirmModal.classList.remove('hidden');
    return new Promise((resolve) => {
        const handleOk = () => {
            confirmModal.classList.add('hidden');
            confirmOkBtn.removeEventListener('click', handleOk);
            resolve(true);
        };
        confirmOkBtn.addEventListener('click', handleOk);
    });
}

function showCustomConfirm(title, message) {
    confirmTitle.textContent = title;
    confirmMsg.textContent = message;
    confirmCancelBtn.classList.remove('hidden');
    confirmModal.classList.remove('hidden');
    return new Promise((resolve) => {
        const handleOk = () => {
            confirmModal.classList.add('hidden');
            cleanup();
            resolve(true);
        };
        const handleCancel = () => {
            confirmModal.classList.add('hidden');
            cleanup();
            resolve(false);
        };
        const cleanup = () => {
            confirmOkBtn.removeEventListener('click', handleOk);
            confirmCancelBtn.removeEventListener('click', handleCancel);
            closeConfirmBtn.removeEventListener('click', handleCancel);
        };
        confirmOkBtn.addEventListener('click', handleOk);
        confirmCancelBtn.addEventListener('click', handleCancel);
        closeConfirmBtn.addEventListener('click', handleCancel);
    });
}

window.showCustomAlert = showCustomAlert;
window.showCustomConfirm = showCustomConfirm;

// --- Helper: Format Date as DD/MM/YYYY : HH/MM/SS ---
function formatProctoringDate(timestamp) {
    if (!timestamp) return '-';
    const d = new Date(timestamp * 1000);
    const pad = (n) => n.toString().padStart(2, '0');

    const date = `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
    const time = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;

    return `${date} : ${time}`;
}

async function showAnalysisDashboard() {
    mainGeneratorCard.classList.add('hidden');
    selectionSection.classList.add('hidden');
    finalResultSection.classList.add('hidden');
    analysisDashboard.classList.remove('hidden');

    const rolesTbody = document.getElementById('job-roles-tbody');
    const emptyState = document.getElementById('empty-state');
    const table = document.querySelector('.modern-table');
    const totalSentStat = document.getElementById('total-tests-stat');
    const completionRateStat = document.getElementById('completion-rate-stat');

    // Reset view
    rolesTbody.innerHTML = '';
    totalSentStat.textContent = '0';
    completionRateStat.textContent = '0%';
    emptyState.classList.add('hidden');
    table.classList.remove('hidden');

    try {
        const response = await fetch('/aptitude-api/get-analytics');
        if (!response.ok) throw new Error("Backend not reachable");

        const db = await response.json();

        if (!db.assessments || db.assessments.length === 0) {
            table.classList.add('hidden');
            emptyState.classList.remove('hidden');
            return;
        }

        // Update Stats
        const totalSent = db.assessments.reduce((acc, curr) => acc + curr.emails.length, 0);
        totalSentStat.textContent = totalSent;

        const totalAttempted = db.submissions.length;
        const rate = totalSent > 0 ? Math.round((totalAttempted / totalSent) * 100) : 0;
        completionRateStat.textContent = rate + '%';

        // Update Header for Date Column
        const thead = document.querySelector('#roles-table-header');
        if (thead && !thead.innerHTML.includes('SENT DATE')) {
            const actionsTh = thead.lastElementChild;
            const dateTh = document.createElement('th');
            dateTh.textContent = 'SENT DATE';
            thead.insertBefore(dateTh, actionsTh);
        }

        // Render Roles Table
        rolesTbody.innerHTML = db.assessments.map(a => {
            const attempted = db.submissions.filter(s => s.token === a.token).length;
            const pending = a.emails.length - attempted;
            const sentDate = formatProctoringDate(a.timestamp);

            const mcqCount = a.mcqs ? a.mcqs.length : (a.questions ? a.questions.length : 0);
            const codeCount = a.coding_questions ? a.coding_questions.length : 0;

            return `
                <tr>
                    <td onclick="viewCandidateDetails('${a.job_title}', '${a.token}')">
                        <div style="font-weight: 700;">${a.job_title}</div>
                        <div style="font-size: 0.7rem; color: #94a3b8;">${mcqCount} MCQ | ${codeCount} Code</div>
                    </td>
                    <td><span class="status-badge status-sent">Sent</span></td>
                    <td>${a.emails.length}</td>
                    <td>${attempted}</td>
                    <td>${new Date(a.timestamp * 1000).toLocaleDateString()}</td>
                    <td class="actions-cell">
                        <button class="glass-btn sm" onclick="viewCandidateDetails('${a.job_title}', '${a.token}')">View Details</button>
                        <button class="delete-btn" onclick="event.stopPropagation(); deleteAssessment('${a.token}')" title="Delete Assessment">
                            <i data-lucide="trash-2"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
        lucide.createIcons();
    } catch (error) {
        console.error("Failed to fetch analytics:", error);
        table.classList.add('hidden');
        emptyState.querySelector('p').textContent = "Unable to connect to service. Please ensure the backend server is running.";
        emptyState.classList.remove('hidden');
    }
}

window.deleteAssessment = async function (token) {
    const confirmed = await showCustomConfirm("Delete Assessment", "Are you sure you want to delete this assessment and all its submission data? This cannot be undone.");
    if (!confirmed) return;

    try {
        const response = await fetch(`/aptitude-api/delete-assessment/${token}`, { method: 'DELETE' });
        if (response.ok) {
            showAnalysisDashboard(); // Refresh
        } else {
            showCustomAlert("Error", "Failed to delete assessment.");
        }
    } catch (error) {
        showCustomAlert("Error", "Connection error. Could not delete.");
    }
}

window.hideAnalysis = function () {
    analysisDashboard.classList.add('hidden');
    mainGeneratorCard.classList.remove('hidden');
}

const candidateList = document.getElementById('candidate-submissions-list');

window.viewCandidateDetails = async function (jobTitle, token) {
    detailJobTitleText.textContent = jobTitle;
    jobRolesView.classList.add('hidden');
    candidateDetailsView.classList.remove('hidden');

    candidateList.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:20px;">Loading candidates...</td></tr>';

    try {
        const response = await fetch('/aptitude-api/get-analytics');
        const db = await response.json();

        const assessment = db.assessments.find(a => a.token === token);
        const submissions = db.submissions.filter(s => s.token === token);

        if (!assessment) return;

        candidateList.innerHTML = assessment.emails.map(email => {
            const sub = submissions.find(s => s.email === email);

            let status = sub ? 'Attempted' : 'Pending';
            let statusClass = sub ? 'status-attempted' : 'status-pending';

            if (sub && sub.suspicious !== "Normal") {
                status = "Flagged";
                statusClass = "status-sent"; // reuse style or add flagged
            }

            const mcqScore = sub ? (sub.mcq_score !== undefined ? `${sub.mcq_score}/${sub.mcq_total}` : `${sub.score}/${sub.total}`) : '-';
            const codingScore = sub ? (sub.coding_score !== undefined ? `${sub.coding_score}/${sub.coding_total}` : '-') : '-';
            const date = sub ? new Date(sub.timestamp * 1000).toLocaleDateString() : '-';

            return `
                <tr>
                    <td>${email}</td>
                    <td style="font-weight:700; color:var(--primary);">${mcqScore}</td>
                    <td style="font-weight:700; color:#10b981;">${codingScore}</td>
                    <td><span class="status-badge ${statusClass}">${status}</span></td>
                    <td>${date}</td>
                </tr>
            `;
        }).join('');
    } catch (error) {
        console.error("Failed to fetch candidate details:", error);
        candidateList.innerHTML = '<tr><td colspan="5" style="text-align:center; color:red;">Error loading details.</td></tr>';
    }
    lucide.createIcons();
}

window.backToRoles = function () {
    candidateDetailsView.classList.add('hidden');
    jobRolesView.classList.remove('hidden');
}
