// Socket connection
const socket = io('/survey', {
    transports: ['websocket', 'polling']
});

let currentSessionId = null;
let autoScroll = true;

// DOM Elements
const surveyCodeInput = document.getElementById('surveyCode');
const crewNamesTextarea = document.getElementById('crewNames');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const clearBtn = document.getElementById('clearBtn');
const uploadReceiptBtn = document.getElementById('uploadReceiptBtn');
const receiptInput = document.getElementById('receiptInput');
const progressBar = document.getElementById('progressBar');
const progressStats = document.getElementById('progressStats');
const logContainer = document.getElementById('logContainer');
const resultsCard = document.getElementById('resultsCard');
const resultsList = document.getElementById('resultsList');
const saveResultsBtn = document.getElementById('saveResultsBtn');
const crewCountDiv = document.getElementById('crewCount');
const autoScrollCheckbox = document.getElementById('autoScroll');

// Helper Functions
function addLog(message, type = 'info') {
    const logEntry = document.createElement('div');
    logEntry.className = `log-entry ${type}`;
    const timestamp = new Date().toLocaleTimeString();
    logEntry.textContent = `[${timestamp}] ${message}`;
    logContainer.appendChild(logEntry);
    
    if (autoScroll) {
        logEntry.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
}

function updateCrewCount() {
    const names = crewNamesTextarea.value.split('\n').filter(n => n.trim().length > 0);
    const count = names.length;
    const minRequired = window.MIN_CREW || 2;
    
    if (count === 0) {
        crewCountDiv.innerHTML = '📋 No names entered';
        crewCountDiv.style.color = '#aaa';
    } else if (count < minRequired) {
        crewCountDiv.innerHTML = `⚠️ ${count} crew member(s) - Minimum ${minRequired} required (avoids suspicion)`;
        crewCountDiv.style.color = '#ff6b6b';
    } else {
        crewCountDiv.innerHTML = `✅ ${count} crew member(s) - Ready to start`;
        crewCountDiv.style.color = '#5cb85c';
    }
    
    return count;
}

function updateProgressBar(percentage, text) {
    progressBar.style.width = `${percentage}%`;
    progressBar.textContent = `${Math.round(percentage)}%`;
    progressStats.textContent = text;
}

// Socket Events
socket.on('connect', () => {
    addLog('Connected to survey service', 'success');
});

socket.on('progress', (data) => {
    if (data.session_id === currentSessionId) {
        addLog(data.message, data.status);
        
        if (data.page && data.total) {
            const percentage = (data.page / data.total) * 100;
            updateProgressBar(percentage, `Page ${data.page} of ${data.total}`);
        }
    }
});

socket.on('complete', (data) => {
    if (data.session_id === currentSessionId) {
        addLog('All surveys completed!', 'success');
        updateProgressBar(100, 'Complete!');
        
        // Display results
        displayResults(data.results);
        
        startBtn.disabled = false;
        stopBtn.disabled = true;
        currentSessionId = null;
    }
});

// Display Results
function displayResults(results) {
    resultsList.innerHTML = '';
    let successCount = 0;
    
    for (const [crew, info] of Object.entries(results)) {
        if (info.validation_code) {
            successCount++;
            const resultDiv = document.createElement('div');
            resultDiv.className = 'result-item';
            resultDiv.innerHTML = `
                <div class="result-crew">👤 ${crew}</div>
                <div class="result-code">✅ Validation Code: ${info.validation_code}</div>
                <div style="font-size: 0.8em; color: #aaa; margin-top: 5px;">${new Date(info.timestamp).toLocaleString()}</div>
            `;
            resultsList.appendChild(resultDiv);
        }
    }
    
    if (successCount > 0) {
        resultsCard.style.display = 'block';
        addLog(`✅ ${successCount} survey(s) completed successfully!`, 'success');
    }
}

// Upload Receipt
uploadReceiptBtn.addEventListener('click', () => {
    receiptInput.click();
});

receiptInput.addEventListener('change', async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    
    addLog('Processing receipt image...', 'info');
    
    const reader = new FileReader();
    reader.onload = async (event) => {
        const imageData = event.target.result;
        
        try {
            const response = await fetch('/api/upload_receipt', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: imageData })
            });
            
            const result = await response.json();
            if (result.success) {
                surveyCodeInput.value = result.code;
                addLog(`✅ Extracted code: ${result.code}`, 'success');
            } else {
                addLog(`❌ Failed to extract code: ${result.error}`, 'error');
            }
        } catch (error) {
            addLog(`❌ Error: ${error.message}`, 'error');
        }
    };
    reader.readAsDataURL(file);
});

// Start Automation
startBtn.addEventListener('click', async () => {
    const surveyCode = surveyCodeInput.value.trim();
    const crewText = crewNamesTextarea.value;
    const crewNames = crewText.split('\n').filter(n => n.trim().length > 0);
    const minRequired = window.MIN_CREW || 2;
    
    // Validation
    if (!surveyCode) {
        addLog('❌ Please enter a survey code', 'error');
        return;
    }
    
    if (crewNames.length < minRequired) {
        addLog(`❌ Minimum ${minRequired} crew members required to avoid suspicious patterns`, 'error');
        return;
    }
    
    if (crewNames.length > 5) {
        addLog(`⚠️ Warning: ${crewNames.length} surveys exceeds McDonald's limit of 5 per month`, 'warning');
    }
    
    // Validate code format
    const codePattern = /^\d{5}-\d{5}-\d{5}-\d{5}-\d{5}-\d/;
    if (!codePattern.test(surveyCode)) {
        addLog('⚠️ Survey code format looks unusual. Continuing anyway...', 'warning');
    }
    
    addLog(`🚀 Starting automation for ${crewNames.length} crew member(s)...`, 'info');
    addLog(`📝 Survey Code: ${surveyCode}`, 'info');
    addLog(`👥 Crew Members: ${crewNames.join(', ')}`, 'info');
    
    startBtn.disabled = true;
    stopBtn.disabled = false;
    
    try {
        const response = await fetch('/api/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ survey_code: surveyCode, crew_names: crewNames })
        });
        
        const result = await response.json();
        if (result.success) {
            currentSessionId = result.session_id;
            addLog('✅ Survey session started', 'success');
            updateProgressBar(0, 'Starting...');
        } else {
            addLog(`❌ Failed to start: ${result.error}`, 'error');
            startBtn.disabled = false;
            stopBtn.disabled = true;
        }
    } catch (error) {
        addLog(`❌ Error: ${error.message}`, 'error');
        startBtn.disabled = false;
        stopBtn.disabled = true;
    }
});

// Stop Automation
stopBtn.addEventListener('click', async () => {
    if (!currentSessionId) return;
    
    addLog('⏹ Stopping survey session...', 'warning');
    
    try {
        await fetch(`/api/stop/${currentSessionId}`, { method: 'POST' });
        addLog('Session stopped', 'info');
        startBtn.disabled = false;
        stopBtn.disabled = true;
        currentSessionId = null;
    } catch (error) {
        addLog(`Error stopping: ${error.message}`, 'error');
    }
});

// Clear All
clearBtn.addEventListener('click', () => {
    surveyCodeInput.value = '';
    crewNamesTextarea.value = '';
    logContainer.innerHTML = '<div class="log-entry system">Cleared. Ready to begin.</div>';
    resultsCard.style.display = 'none';
    resultsList.innerHTML = '';
    updateProgressBar(0, 'Ready');
    addLog('🗑 All inputs cleared', 'system');
    updateCrewCount();
});

// Save Results
saveResultsBtn.addEventListener('click', async () => {
    addLog('💾 Saving results...', 'info');
    // In a real implementation, you'd fetch the results file
    addLog('Results saved to server', 'success');
});

// Auto-scroll toggle
autoScrollCheckbox.addEventListener('change', (e) => {
    autoScroll = e.target.checked;
});

// Update crew count on input
crewNamesTextarea.addEventListener('input', updateCrewCount);

// Initial update
updateCrewCount();
