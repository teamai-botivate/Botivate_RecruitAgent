document.addEventListener('DOMContentLoaded', () => {
    lucide.createIcons();
    initializeCustomSelects(); // Set up new premium dropdowns
    loadFormData();
});

const jdForm = document.getElementById('jd-form');
const generateBtn = document.getElementById('generate-btn');
const loader = document.getElementById('loader');
const resultSection = document.getElementById('result-section');
const jdOutput = document.getElementById('jd-output');
const copyBtn = document.getElementById('copy-btn');
const downloadBtn = document.getElementById('download-btn');

// --- Persistent Form Data (Step 1 Only) ---
const persistentFields = ['company-name', 'company-type', 'industry', 'location'];
const temporaryFields = ['role-title', 'experience', 'employment-type', 'work-mode'];

function savePersistentData() {
    const data = {};
    persistentFields.forEach(id => {
        const el = document.getElementById(id);
        if (el) data[id] = el.value;
    });
    localStorage.setItem('recruitAI_companyData', JSON.stringify(data));
}

function loadFormData() {
    const saved = localStorage.getItem('recruitAI_companyData');
    if (saved) {
        const data = JSON.parse(saved);
        persistentFields.forEach(id => {
            const el = document.getElementById(id);
            if (data[id] && el) {
                el.value = data[id];
            }
        });
    }
    
    // Attach auto-save ONLY to persistent fields
    persistentFields.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener('input', savePersistentData);
            el.addEventListener('change', savePersistentData);
        }
    });
}

function clearStep2Fields() {
    temporaryFields.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            if (el.tagName === 'SELECT') {
                el.selectedIndex = 0;
                // Update custom UI
                const wrapper = el.closest('.select-wrapper');
                if (wrapper) {
                    const triggerSpan = wrapper.querySelector('.custom-select-trigger span');
                    if (triggerSpan) triggerSpan.textContent = el.options[0].text;
                    wrapper.querySelectorAll('.custom-select-option').forEach(opt => opt.classList.remove('selected'));
                }
            } else {
                el.value = '';
            }
        }
    });
}

// --- Premium Select Transformation ---
function initializeCustomSelects() {
    const selects = document.querySelectorAll('select');
    
    selects.forEach(select => {
        // Create Wrapper
        const wrapper = document.createElement('div');
        wrapper.className = 'select-wrapper';
        select.parentNode.insertBefore(wrapper, select);
        wrapper.appendChild(select);
        select.classList.add('native-select');

        // Create Custom UI
        const trigger = document.createElement('div');
        trigger.className = 'custom-select-trigger';
        trigger.innerHTML = `<span>${select.options[select.selectedIndex].text}</span> <i data-lucide="chevron-down" style="width:16px; height:16px;"></i>`;
        
        const optionsContainer = document.createElement('div');
        optionsContainer.className = 'custom-select-options';

        Array.from(select.options).forEach((option, index) => {
            if (index === 0) return; // Skip placeholder
            const opt = document.createElement('div');
            opt.className = 'custom-select-option';
            opt.textContent = option.text;
            opt.addEventListener('click', () => {
                select.value = option.value;
                trigger.querySelector('span').textContent = option.text;
                optionsContainer.classList.remove('show');
                trigger.classList.remove('open');
                
                // Active state
                optionsContainer.querySelectorAll('.custom-select-option').forEach(o => o.classList.remove('selected'));
                opt.classList.add('selected');
                
                // Trigger change event for any listeners
                select.dispatchEvent(new Event('change'));
            });
            optionsContainer.appendChild(opt);
        });

        wrapper.appendChild(trigger);
        wrapper.appendChild(optionsContainer);

        // Toggle logic
        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = optionsContainer.classList.contains('show');
            
            // Close all other dropdowns
            document.querySelectorAll('.custom-select-options').forEach(o => o.classList.remove('show'));
            document.querySelectorAll('.custom-select-trigger').forEach(o => o.classList.remove('open'));

            if (!isOpen) {
                optionsContainer.classList.add('show');
                trigger.classList.add('open');
            }
        });
    });

    // Close on click outside
    document.addEventListener('click', () => {
        document.querySelectorAll('.custom-select-options').forEach(o => o.classList.remove('show'));
        document.querySelectorAll('.custom-select-trigger').forEach(o => o.classList.remove('open'));
    });

    lucide.createIcons();
}

// --- Form Submission ---
jdForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    // Save Step 1 data
    savePersistentData();

    // Show Loader
    loader.classList.remove('hidden');
    resultSection.classList.add('hidden');
    generateBtn.disabled = true;

    // Collect Data
    const formData = {
        companyName: document.getElementById('company-name').value,
        companyType: document.getElementById('company-type').value,
        industry: document.getElementById('industry').value,
        location: document.getElementById('location').value,
        roleTitle: document.getElementById('role-title').value,
        experience: document.getElementById('experience').value,
        employmentType: document.getElementById('employment-type').value,
        workMode: document.getElementById('work-mode').value
    };

    try {
        const response = await fetch('http://127.0.0.1:8001/generate-jd', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        const result = await response.json();
        
        if (result.status === 'success') {
            displayResult(result.jd);
            clearStep2Fields(); // Reset Step 2 after successful generation
        } else {
            throw new Error(result.detail || "Generation failed");
        }

    } catch (error) {
        console.error("Backend Error:", error);
        alert("Neural Link Failure: Could not reach the JD Agent. Ensure backend is running.");
    } finally {
        loader.classList.add('hidden');
        generateBtn.disabled = false;
    }
});

function displayResult(content) {
    // Format headings: "1. COMPANY NAME:" -> emboldened with primary color
    let formattedContent = content
        .replace(/^(\d+\.\s+[A-Z\s]+:)/gm, '<span class="jd-heading">$1</span>')
        // Ensure bold markdown or stars if AI used them are also handled
        .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
        .replace(/\*(.*?)\*/g, '<b>$1</b>');

    jdOutput.innerHTML = formattedContent;
    resultSection.classList.remove('hidden');
    resultSection.scrollIntoView({ behavior: 'smooth' });
}

// --- Actions ---
copyBtn.addEventListener('click', () => {
    const text = jdOutput.textContent;
    navigator.clipboard.writeText(text).then(() => {
        const originalInner = copyBtn.innerHTML;
        copyBtn.innerHTML = '<i data-lucide="check"></i> Copied!';
        lucide.createIcons();
        setTimeout(() => {
            copyBtn.innerHTML = originalInner;
            lucide.createIcons();
        }, 2000);
    });
});

downloadBtn.addEventListener('click', () => {
    const text = jdOutput.textContent;
    const blob = new Blob([text], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `JD_${document.getElementById('role-title').value.replace(/\s+/g, '_')}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
});

// --- Mock AI Generator Logic ---
function mockGenerateJD(data) {
    const { companyName, roleTitle, experience, location, industry, workMode, employmentType } = data;
    
    return `1. COMPANY NAME: ${companyName}

2. JOB TITLE: ${roleTitle} (${experience})

3. ROLE SUMMARY:
As a ${roleTitle} at ${companyName}, you will be part of a dynamic ${industry} team. Based in ${location} (${workMode}), you will contribute to innovative solutions and drive excellence in a ${employmentType} capacity. We are looking for a proactive professional who can handle complex challenges and deliver high-quality results.

4. KEY RESPONSIBILITIES:
• Design, develop, and maintain high-performance, reusable, and reliable code.
• Collaborate with cross-functional teams to define, design, and ship new features.
• Identify and correct bottlenecks and fix bugs to improve application performance.
• Maintain code quality through robust testing and structured documentation.
• Participate in architectural decisions and technical roadmap planning.
• Ensure the best possible performance, quality, and responsiveness of applications.
• Contribute to continuous improvement by investigating alternatives and technologies.

5. REQUIRED SKILLS:
• Strong grasp of software development life cycle (SDLC).
• Excellent analytical and problem-solving skills.
• Ability to work in a fast-paced and collaborative environment.
• Effective communication skills and stakeholder management.

6. TECH STACK:
• Core: Python, FastAPI / Node.js, Express
• Frontend: React / Vue.js, Tailwind CSS
• Databases: PostgreSQL, MongoDB, Redis
• DevOps: Docker, Git, CI/CD, AWS/Azure

7. PREFERRED SKILLS:
• Experience with cloud-native architectures.
• Understanding of security best practices in development.
• Familiarity with AI-driven development tools.

8. BENEFITS:
• Competitive compensation package.
• Health insurance and wellness programs.
• Career growth opportunities and mentorship.
• Modern work environment with flexible timing.

9. CLOSING LINE:
Join ${companyName} and help us redefine ${industry} standards. We look forward to your application!`;
}
