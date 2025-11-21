// Global state
let ws = null;
let currentLeads = [];
let convertedData = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    loadFiles();
    refreshLeads();
    updateStats();
    setupWebSocket();
    setupFileUpload();
});

// WebSocket Setup
function setupWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/progress`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleProgressUpdate(data);
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };

    ws.onclose = () => {
        console.log('WebSocket closed, reconnecting...');
        setTimeout(setupWebSocket, 3000);
    };
}

// File Upload Setup
function setupFileUpload() {
    const fileInput = document.getElementById('file-upload');
    fileInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (file) {
            await uploadFile(file);
            fileInput.value = '';
        }
    });
}

// Load Files List
async function loadFiles() {
    try {
        const response = await fetch('/api/files');
        const files = await response.json();

        const container = document.getElementById('files-list');
        if (files.length === 0) {
            container.innerHTML = '<div class="text-gray-500 text-center py-4">No files found. Upload some data files.</div>';
            return;
        }

        container.innerHTML = files.map(file => `
            <div class="flex items-center justify-between p-3 border border-black">
                <div class="flex-1">
                    <div class="font-medium">${file.name}</div>
                    <div class="text-sm text-gray-600">${file.records} records • ${file.type}</div>
                </div>
                <div class="space-x-2">
                    <button onclick="previewFile('${file.name}')" class="btn-secondary px-3 py-1 text-sm">
                        Preview
                    </button>
                    <button onclick="downloadFile('${file.name}')" class="btn-secondary px-3 py-1 text-sm">
                        Download
                    </button>
                    <button onclick="deleteFile('${file.name}')" class="btn-secondary px-3 py-1 text-sm">
                        Delete
                    </button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        showNotification('Error loading files: ' + error.message, 'error');
    }
}

// Upload File (with automatic AI conversion)
async function uploadFile(file) {
    const formData = new FormData();
    formData.append('file', file);

    const fileExt = file.name.split('.').pop().toLowerCase();
    const needsConversion = ['csv', 'xlsx', 'txt'].includes(fileExt);

    if (needsConversion) {
        logToTerminal(`Uploading ${file.name} - will convert with AI...`);
        showNotification(`Converting ${file.name} with AI... This may take a minute`, 'info');
    } else {
        logToTerminal(`Uploading ${file.name}...`);
    }

    try {
        const response = await fetch('/api/files/upload', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            const result = await response.json();

            if (result.converted) {
                logToTerminal(`✓ AI conversion successful: ${result.filename} (${result.records_count} records, type: ${result.record_type})`);
                showNotification(`Converted to ${result.filename} with ${result.records_count} records`, 'success');
            } else {
                logToTerminal(`✓ File uploaded: ${result.filename}`);
                showNotification(`File "${result.filename}" uploaded successfully`, 'success');
            }

            await loadFiles();
        } else {
            const error = await response.json();
            logToTerminal(`✗ Upload failed: ${error.detail}`);
            showNotification('Upload failed: ' + error.detail, 'error');
        }
    } catch (error) {
        logToTerminal(`✗ Error: ${error.message}`);
        showNotification('Upload error: ' + error.message, 'error');
    }
}

// Delete File
async function deleteFile(filename) {
    if (!confirm(`Delete "${filename}"?`)) return;

    try {
        const response = await fetch(`/api/files/${filename}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showNotification(`File "${filename}" deleted`, 'success');
            await loadFiles();
        } else {
            showNotification('Delete failed', 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
}

// Download File
async function downloadFile(filename) {
    try {
        const response = await fetch(`/api/files/${filename}/download`);
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        window.URL.revokeObjectURL(url);
    } catch (error) {
        showNotification('Download error: ' + error.message, 'error');
    }
}

// Preview File
async function previewFile(filename) {
    try {
        const response = await fetch(`/api/files/${filename}`);
        const data = await response.json();
        showPreviewModal(filename, data);
    } catch (error) {
        showNotification('Preview error: ' + error.message, 'error');
    }
}

// Show Preview Modal
function showPreviewModal(filename, data) {
    const modal = document.getElementById('preview-modal');
    const modalFilename = document.getElementById('modal-filename');
    const modalContent = document.getElementById('modal-content');
    const recordCount = document.getElementById('modal-record-count');

    modalFilename.textContent = filename;
    recordCount.textContent = `${data.records.length} records`;
    modalContent.textContent = JSON.stringify(data, null, 2);

    modal.classList.remove('hidden');
}

// Close Preview Modal
function closePreviewModal() {
    document.getElementById('preview-modal').classList.add('hidden');
}

// Show Completion Popup
function showCompletionPopup(leadsCount) {
    const popup = document.createElement('div');
    popup.className = 'completion-popup';
    popup.innerHTML = `
        <div class="bg-white border-2 border-black p-6 rounded-lg shadow-lg max-w-md">
            <h2 class="text-2xl font-bold mb-4">Processing Complete!</h2>
            <p class="text-lg mb-4">All data has been successfully processed.</p>
            <div class="text-center mb-4">
                <div class="text-4xl font-bold">${leadsCount}</div>
                <div class="text-gray-600">Citizenship Leads Found</div>
            </div>
            <button onclick="closeCompletionPopup()" class="btn-primary w-full py-2">
                View Results
            </button>
        </div>
    `;
    document.body.appendChild(popup);

    // Auto-close after 5 seconds
    setTimeout(() => {
        closeCompletionPopup();
    }, 5000);
}

// Close Completion Popup
function closeCompletionPopup() {
    const popup = document.querySelector('.completion-popup');
    if (popup) {
        popup.remove();
    }
}

// Load All Data
async function loadAllData() {
    const section = document.getElementById('processing-section');
    section.classList.remove('hidden');

    logToTerminal('Starting batch processing of all data files...');

    try {
        const response = await fetch('/api/load-all', {
            method: 'POST'
        });

        if (response.ok) {
            const result = await response.json();
            logToTerminal(`Submitted ${result.job_ids.length} files for processing`);
            showNotification('Processing started...', 'info');
        } else {
            logToTerminal('✗ Failed to start processing');
            showNotification('Failed to start processing', 'error');
        }
    } catch (error) {
        logToTerminal(`✗ Error: ${error.message}`);
        showNotification('Error: ' + error.message, 'error');
    }
}

// Handle Progress Updates
function handleProgressUpdate(data) {
    const progressContainer = document.getElementById('progress-bars');
    const processingSection = document.getElementById('processing-section');

    if (data.status === 'complete') {
        // Clear progress bars
        progressContainer.innerHTML = '';

        // Hide processing section
        processingSection.classList.add('hidden');

        // Log completion
        logToTerminal(`✓ All processing complete! Found ${data.leads_count} citizenship leads`);

        // Show success notification
        showNotification(`Processing complete! Found ${data.leads_count} leads`, 'success');

        // Show completion popup
        showCompletionPopup(data.leads_count);

        // Refresh data
        refreshLeads();
        updateStats();
        return;
    }

    if (data.file) {
        let progressBar = document.getElementById(`progress-${data.file}`);
        if (!progressBar) {
            progressBar = document.createElement('div');
            progressBar.id = `progress-${data.file}`;
            progressBar.innerHTML = `
                <div class="text-sm mb-1">${data.file}</div>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 0%"></div>
                </div>
            `;
            progressContainer.appendChild(progressBar);
        }

        const fill = progressBar.querySelector('.progress-fill');
        fill.style.width = `${data.progress}%`;

        // Log progress events
        if (data.status === 'submitted') {
            logToTerminal(`Processing ${data.file}...`);
        } else if (data.status === 'completed') {
            logToTerminal(`✓ ${data.file} completed`);
            // Mark progress bar as complete
            progressBar.style.opacity = '0.5';
        } else if (data.status === 'failed') {
            logToTerminal(`✗ ${data.file} failed`);
            progressBar.querySelector('.progress-fill').style.background = 'red';
        } else if (data.status === 'error') {
            logToTerminal(`✗ ${data.file}: ${data.error}`);
            progressBar.querySelector('.progress-fill').style.background = 'red';
        }
    }
}

// Refresh Leads
async function refreshLeads() {
    try {
        const response = await fetch('/api/leads?min_score=50');
        currentLeads = await response.json();
        renderLeads(currentLeads);
    } catch (error) {
        showNotification('Error loading leads: ' + error.message, 'error');
    }
}

// Render Leads Table
function renderLeads(leads) {
    const tbody = document.getElementById('leads-tbody');

    if (leads.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center text-gray-500 py-8">
                    No leads found. Load data to get started.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = leads.map((lead, idx) => `
        <tr class="cursor-pointer" onclick="toggleExpandRow(${idx})">
            <td class="font-bold">${lead.lead_score}</td>
            <td>${lead.name}</td>
            <td>${lead.last_known_address}</td>
            <td>${lead.german_ancestor.name}</td>
            <td>${lead.sources_count}</td>
            <td>${lead.data_confidence}</td>
        </tr>
        <tr id="expand-${idx}" class="expandable-row">
            <td colspan="6" class="bg-gray-50 p-4">
                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <h4 class="font-bold mb-2">Person Details</h4>
                        <p><strong>ID:</strong> ${lead.person_id}</p>
                        <p><strong>Name:</strong> ${lead.name}</p>
                        <p><strong>Address:</strong> ${lead.last_known_address}</p>
                    </div>
                    <div>
                        <h4 class="font-bold mb-2">German Ancestor</h4>
                        <p><strong>Name:</strong> ${lead.german_ancestor.name}</p>
                        <p><strong>Birth Place:</strong> ${lead.german_ancestor.birth_place}</p>
                        <p><strong>Birth Date:</strong> ${lead.german_ancestor.birth_date || 'Unknown'}</p>
                        <p><strong>Naturalization:</strong> ${lead.german_ancestor.naturalization_date || 'N/A'}</p>
                        <p><strong>Eligible:</strong> ${lead.german_ancestor.citizenship_eligible ? 'Yes' : 'No'}</p>
                    </div>
                </div>
            </td>
        </tr>
    `).join('');
}

// Toggle Expand Row
function toggleExpandRow(idx) {
    const row = document.getElementById(`expand-${idx}`);
    row.classList.toggle('show');
}

// Sort Table
let sortDirection = {};
function sortTable(column) {
    sortDirection[column] = !sortDirection[column];
    const sorted = [...currentLeads].sort((a, b) => {
        let aVal = column === 'score' ? a.lead_score : a.name;
        let bVal = column === 'score' ? b.lead_score : b.name;
        return sortDirection[column] ? (aVal > bVal ? 1 : -1) : (aVal < bVal ? 1 : -1);
    });
    renderLeads(sorted);
}

// Export Leads
function exportLeads() {
    if (currentLeads.length === 0) {
        showNotification('No leads to export', 'error');
        return;
    }

    const csv = [
        ['Score', 'Name', 'Address', 'German Ancestor', 'Birth Place', 'Birth Date', 'Sources'],
        ...currentLeads.map(l => [
            l.lead_score,
            l.name,
            l.last_known_address,
            l.german_ancestor.name,
            l.german_ancestor.birth_place,
            l.german_ancestor.birth_date || '',
            l.sources_count
        ])
    ].map(row => row.join(',')).join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'citizenship_leads.csv';
    a.click();
    window.URL.revokeObjectURL(url);

    showNotification('Exported leads to CSV', 'success');
}

// Update Statistics
async function updateStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();

        document.getElementById('stat-records').textContent = stats.total_records || 0;
        document.getElementById('stat-persons').textContent = stats.unique_persons || 0;
        document.getElementById('stat-leads').textContent = stats.leads_count || 0;
        document.getElementById('stat-dedup').textContent = stats.dedup_rate || '0%';
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// Show/Hide Converter
function convertFile() {
    document.getElementById('converter-section').classList.remove('hidden');
}

function closeConverter() {
    document.getElementById('converter-section').classList.add('hidden');
    document.getElementById('conversion-preview').classList.add('hidden');
    document.getElementById('save-converted-btn').classList.add('hidden');
    convertedData = null;
}

// Perform AI Conversion
async function performConversion() {
    const fileInput = document.getElementById('convert-file-input');
    const recordType = document.getElementById('record-type').value;

    if (!fileInput.files[0]) {
        showNotification('Please select a file to convert', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('record_type', recordType);

    showNotification('Converting with AI... This may take a minute', 'info');

    try {
        const response = await fetch('/api/convert', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            convertedData = await response.json();
            document.getElementById('preview-content').textContent =
                JSON.stringify(convertedData.records.slice(0, 3), null, 2);
            document.getElementById('conversion-preview').classList.remove('hidden');
            document.getElementById('save-converted-btn').classList.remove('hidden');
            showNotification('Conversion successful! Review and save.', 'success');
        } else {
            const error = await response.json();
            showNotification('Conversion failed: ' + error.detail, 'error');
        }
    } catch (error) {
        showNotification('Error: ' + error.message, 'error');
    }
}

// Save Converted File
async function saveConvertedFile() {
    if (!convertedData) return;

    const filename = prompt('Save as (e.g., my_data.json):');
    if (!filename) return;

    const blob = new Blob([JSON.stringify(convertedData, null, 2)], { type: 'application/json' });
    const formData = new FormData();
    formData.append('file', blob, filename);

    try {
        const response = await fetch('/api/files/upload', {
            method: 'POST',
            body: formData
        });

        if (response.ok) {
            showNotification(`Saved as ${filename}`, 'success');
            closeConverter();
            loadFiles();
        }
    } catch (error) {
        showNotification('Save error: ' + error.message, 'error');
    }
}

// Show Notification
function showNotification(message, type = 'info') {
    const container = document.getElementById('notifications');
    const notification = document.createElement('div');
    notification.className = 'notification';
    notification.innerHTML = `
        <div class="font-bold mb-1">${type === 'error' ? 'Error' : type === 'success' ? 'Success' : 'Info'}</div>
        <div>${message}</div>
    `;
    container.appendChild(notification);

    setTimeout(() => {
        notification.remove();
    }, 5000);
}

// Terminal Logger
function logToTerminal(message) {
    const terminal = document.getElementById('terminal');
    const timestamp = new Date().toLocaleTimeString();
    const line = document.createElement('div');
    line.textContent = `[${timestamp}] ${message}`;
    terminal.appendChild(line);

    // Auto-scroll to bottom
    terminal.scrollTop = terminal.scrollHeight;
}
