// Global variables
let jobs = [];
let printers = [];
let spools = [];
let materials = [];
let currentJobId = null;
let deleteJobId = null;
let overrideJobId = null;

// Load data on page load
document.addEventListener('DOMContentLoaded', async () => {
    // Stammdaten ERST laden, dann Jobs rendern, damit IDs aufgelöst werden
    try {
        await loadMaterials();
        await loadPrinters();
        await loadSpools();
        await loadJobs();
        await loadStats();
    } catch (e) {
        console.error('Init error', e);
    }

    // Set default start time to now
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    document.getElementById('startedAt').value = now.toISOString().slice(0, 16);

    // Search and filter
    document.getElementById('searchInput').addEventListener('input', filterJobs);
    document.getElementById('filterPrinter').addEventListener('change', filterJobs);
    document.getElementById('filterStatus').addEventListener('change', filterJobs);

    // Spulen-Suche (Job-Formular)
    const spoolSearch = document.getElementById('spoolSearch');
    if (spoolSearch) {
        spoolSearch.addEventListener('input', filterSpoolList);
    }

    // Spulen-Suche (Manual Usage Modal)
    const usageSpoolSearch = document.getElementById('usageSpoolSearch');
    if (usageSpoolSearch) {
        usageSpoolSearch.addEventListener('input', filterUsageSpoolList);
    }

    // Auto-refresh alle 15 Sekunden
    setInterval(async () => {
        await loadJobs();
        await loadStats();
    }, 15000);
});

async function loadJobs() {
    try {
        const response = await fetch('/api/jobs/with-usage');
        jobs = await response.json();
        renderJobs(jobs);
    } catch (error) {
        console.error('Fehler beim Laden der Jobs:', error);
    }
}

async function loadPrinters() {
    try {
        const response = await fetch('/api/printers/');
        printers = await response.json();
        
        // Populate printer selects
        const printerSelect = document.getElementById('jobPrinter');
        const filterSelect = document.getElementById('filterPrinter');
        
        printers.forEach(printer => {
            const option = `<option value="${printer.id}">${printer.name} (${printer.printer_type || printer.type || '-'})</option>`;
            printerSelect.innerHTML += option;
            filterSelect.innerHTML += option;
        });
    } catch (error) {
        console.error('Fehler beim Laden der Drucker:', error);
    }
}

async function loadMaterials() {
    try {
        const response = await fetch('/api/materials/');
        materials = await response.json();
    } catch (error) {
        console.error('Fehler beim Laden der Materialien:', error);
    }
}

async function loadSpools() {
    try {
        const response = await fetch('/api/spools/');
        spools = await response.json();
        renderSpoolList(spools);
    } catch (error) {
        console.error('Fehler beim Laden der Spulen:', error);
    }
}

function renderSpoolList(spoolsToRender) {
    const spoolSelect = document.getElementById('jobSpool');
    const usageSpoolSelect = document.getElementById('usageSpool');

    // Reset
    spoolSelect.innerHTML = '<option value="">-- Keine Spule --</option>';
    if (usageSpoolSelect) {
        usageSpoolSelect.innerHTML = '<option value="">-- Spule wählen --</option>';
    }

    spoolsToRender.forEach(spool => {
        // Material-Info holen
        const material = materials.find(m => m.id === spool.material_id);
        const materialName = material ? material.name : 'Unbekannt';
        const brand = material && material.brand ? ` (${material.brand})` : '';

        // Spulen-Nummer oder "RFID"
        const spoolNumber = spool.spool_number ? `#${spool.spool_number}` : (spool.tray_uuid ? '📡 RFID' : '-');

        // Farbe als Punkt
        const color = spool.tray_color ? `🎨` : '';

        // Restgewicht
        const remaining = spool.weight_current || spool.weight_remaining || 0;
        const weight = `${Math.round(remaining)}g`;

        // Label erstellen: "Material | #Nummer | Gewicht"
        const displayText = `${materialName}${brand} | ${spoolNumber} | ${weight} ${color}`;

        const option = `<option value="${spool.id}" data-search="${materialName.toLowerCase()} ${brand.toLowerCase()} ${spoolNumber.toLowerCase()}">${displayText}</option>`;
        spoolSelect.innerHTML += option;

        if (usageSpoolSelect) {
            usageSpoolSelect.innerHTML += option;
        }
    });
}

function filterSpoolList() {
    const searchTerm = document.getElementById('spoolSearch').value.toLowerCase();

    if (!searchTerm) {
        renderSpoolList(spools);
        return;
    }

    const filtered = spools.filter(spool => {
        const material = materials.find(m => m.id === spool.material_id);
        const materialName = material ? material.name.toLowerCase() : '';
        const brand = material && material.brand ? material.brand.toLowerCase() : '';
        const spoolNumber = spool.spool_number ? spool.spool_number.toString() : '';
        const label = spool.label ? spool.label.toLowerCase() : '';

        return materialName.includes(searchTerm) ||
               brand.includes(searchTerm) ||
               spoolNumber.includes(searchTerm) ||
               label.includes(searchTerm);
    });

    renderSpoolList(filtered);
}

function filterUsageSpoolList() {
    const searchTerm = document.getElementById('usageSpoolSearch').value.toLowerCase();

    if (!searchTerm) {
        renderSpoolList(spools);
        return;
    }

    const filtered = spools.filter(spool => {
        const material = materials.find(m => m.id === spool.material_id);
        const materialName = material ? material.name.toLowerCase() : '';
        const brand = material && material.brand ? material.brand.toLowerCase() : '';
        const spoolNumber = spool.spool_number ? spool.spool_number.toString() : '';
        const label = spool.label ? spool.label.toLowerCase() : '';

        return materialName.includes(searchTerm) ||
               brand.includes(searchTerm) ||
               spoolNumber.includes(searchTerm) ||
               label.includes(searchTerm);
    });

    renderSpoolList(filtered);
}

async function loadStats() {
    try {
        const response = await fetch('/api/jobs/stats/summary');
        const stats = await response.json();
        
        document.getElementById('totalJobs').textContent = stats.total_jobs;
        document.getElementById('completedJobs').textContent = stats.completed_jobs;
        document.getElementById('activeJobs').textContent = stats.active_jobs;
        document.getElementById('totalFilament').textContent = stats.total_filament_g + 'g';
    } catch (error) {
        console.error('Fehler beim Laden der Statistiken:', error);
    }
}

function renderJobs(jobsList) {
    const tbody = document.getElementById('jobsTable');
    tbody.innerHTML = '';

    // Update count
    document.getElementById('jobCount').textContent = jobsList.length;

    if (jobsList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align: center; padding: 2rem; color: var(--text-dim);">Keine Druckaufträge vorhanden</td></tr>';
        return;
    }

    jobsList.forEach(job => {
        const printer = printers.find(p => p.id === job.printer_id);
        const primarySpool = spools.find(s => s.id === job.spool_id);

        // Prüfe ob Job Tracking braucht (kein Verbrauch und keine Spule)
        const needsTracking = (!job.spool_id || job.filament_used_g === 0 || job.filament_used_mm === 0) && job.finished_at;

        const status = job.finished_at ?
            '<span class="status-badge status-online">Abgeschlossen</span>' :
            '<span class="status-badge status-printing">Aktiv</span>';

        const verbrauch = needsTracking ?
            '<span style="color: var(--error, #dc3545); font-weight: bold;">⚠️ 0g</span>' :
            `<strong>${job.filament_used_g.toFixed(1)}g</strong><br><small>${(job.filament_used_mm / 1000).toFixed(2)}m</small>`;

        // Berechne Dauer
        const start = new Date(job.started_at);
        const end = job.finished_at ? new Date(job.finished_at) : new Date();
        const durationMs = end - start;
        const durationMin = Math.floor(durationMs / 60000);
        const hours = Math.floor(durationMin / 60);
        const minutes = durationMin % 60;
        const durationText = hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;

        const spoolDisplay = primarySpool ?
            `<div style="display:flex;align-items:center;gap:8px;">
                ${primarySpool.tray_color ? `<span class="color-preview" style="background:#${primarySpool.tray_color.substring(0,6)}"></span>` : ''}
                <span>${primarySpool.label || `Spule ${primarySpool.id.substring(0,6)}`}</span>
             </div>` :
            (needsTracking ? '<span style="color: var(--error, #dc3545); font-weight: bold;">⚠️ Keine</span>' : '<span style="color: var(--text-dim);">-</span>');

        // Aktionen: "Verbrauch nachtragen" Button wenn nötig
        const actions = needsTracking ?
            `<div class="table-actions">
                <button class="btn btn-warning btn-sm" onclick="openManualUsageModal('${job.id}')" title="Verbrauch nachtragen" style="padding: 4px 8px; font-size: 0.85rem;">
                    📝 Nachtragen
                </button>
                <button class="btn-icon btn-delete" onclick="deleteJob('${job.id}')" title="Löschen">🗑️</button>
            </div>` :
            `<div class="table-actions">
                <button class="btn-icon" onclick="editJob('${job.id}')" title="Bearbeiten">✏️</button>
                <button class="btn-icon btn-delete" onclick="deleteJob('${job.id}')" title="Löschen">🗑️</button>
            </div>`;

        const rowClass = needsTracking ? ' style="background: var(--warning-bg, #fff3cd);"' : '';

        const row = `
            <tr${rowClass}>
                <td><strong>${needsTracking ? '⚠️ ' : ''}${job.name}</strong></td>
                <td>${printer ? printer.name : '<em style="color: var(--text-dim);">Unbekannt</em>'}</td>
                <td>${spoolDisplay}</td>
                <td>${verbrauch}</td>
                <td>${status}</td>
                <td><strong>${durationText}</strong></td>
                <td>
                    ${actions}
                </td>
            </tr>
        `;
        tbody.innerHTML += row;
    });
}

function filterJobs() {
    const search = document.getElementById('searchInput').value.toLowerCase();
    const printerFilter = document.getElementById('filterPrinter').value;
    const statusFilter = document.getElementById('filterStatus').value;

    const filtered = jobs.filter(job => {
        const matchSearch = job.name.toLowerCase().includes(search);
        const matchPrinter = !printerFilter || job.printer_id === printerFilter;

        // Erweiterter Status-Filter mit "no-tracking"
        let matchStatus = !statusFilter;
        if (statusFilter === 'active') {
            matchStatus = !job.finished_at;
        } else if (statusFilter === 'completed') {
            matchStatus = job.finished_at;
        } else if (statusFilter === 'no-tracking') {
            // Jobs ohne Tracking: kein Verbrauch ODER keine Spule UND abgeschlossen
            matchStatus = (!job.spool_id || job.filament_used_g === 0 || job.filament_used_mm === 0) && job.finished_at;
        }

        return matchSearch && matchPrinter && matchStatus;
    });

    renderJobs(filtered);
}

function clearFilters() {
    document.getElementById('searchInput').value = '';
    document.getElementById('filterPrinter').value = '';
    document.getElementById('filterStatus').value = '';
    filterJobs();
}

function openAddModal() {
    currentJobId = null;
    document.getElementById('modalTitle').textContent = 'Neuer Druckauftrag';
    document.getElementById('jobName').value = '';
    document.getElementById('jobPrinter').value = '';
    document.getElementById('jobSpool').value = '';
    document.getElementById('filamentUsedMm').value = '0';
    document.getElementById('filamentUsedG').value = '0';
    document.getElementById('finishedAt').value = '';
    
    const now = new Date();
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
    document.getElementById('startedAt').value = now.toISOString().slice(0, 16);
    
    document.getElementById('jobModal').style.display = 'flex';
}

function editJob(id) {
    const job = jobs.find(j => j.id === id);
    if (!job) return;
    
    currentJobId = id;
    document.getElementById('modalTitle').textContent = 'Job bearbeiten';
    document.getElementById('jobName').value = job.name;
    document.getElementById('jobPrinter').value = job.printer_id;
    document.getElementById('jobSpool').value = job.spool_id || '';
    document.getElementById('filamentUsedMm').value = job.filament_used_mm;
    document.getElementById('filamentUsedG').value = job.filament_used_g;
    
    const startDate = new Date(job.started_at);
    startDate.setMinutes(startDate.getMinutes() - startDate.getTimezoneOffset());
    document.getElementById('startedAt').value = startDate.toISOString().slice(0, 16);
    
    if (job.finished_at) {
        const endDate = new Date(job.finished_at);
        endDate.setMinutes(endDate.getMinutes() - endDate.getTimezoneOffset());
        document.getElementById('finishedAt').value = endDate.toISOString().slice(0, 16);
    } else {
        document.getElementById('finishedAt').value = '';
    }
    
    document.getElementById('jobModal').style.display = 'flex';
}

function closeAddModal() {
    document.getElementById('jobModal').style.display = 'none';
    currentJobId = null;
}

function closeDeleteModal() {
    document.getElementById('deleteModal').style.display = 'none';
    deleteJobId = null;
}

async function saveJob(event) {
    event.preventDefault();
    
    const name = document.getElementById('jobName').value.trim();
    const printer_id = document.getElementById('jobPrinter').value;
    const spool_id = document.getElementById('jobSpool').value || null;
    const filament_used_mm = parseFloat(document.getElementById('filamentUsedMm').value) || 0;
    const filament_used_g = parseFloat(document.getElementById('filamentUsedG').value) || 0;
    const started_at = document.getElementById('startedAt').value;
    const finished_at = document.getElementById('finishedAt').value || null;
    
    if (!name || !printer_id) {
        alert('Bitte füllen Sie alle Pflichtfelder aus!');
        return;
    }
    
    const jobData = {
        name,
        printer_id,
        spool_id,
        filament_used_mm,
        filament_used_g,
        started_at: started_at ? new Date(started_at).toISOString() : new Date().toISOString(),
        finished_at: finished_at ? new Date(finished_at).toISOString() : null
    };
    
    try {
        const url = currentJobId ? `/api/jobs/${currentJobId}` : '/api/jobs/';
        const method = currentJobId ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(jobData)
        });
        
        if (response.ok) {
            closeAddModal();
            clearFilters();
            await loadJobs();
            await loadStats();
            showNotification(currentJobId ? 'Job aktualisiert!' : 'Job erstellt!', 'success');
        } else {
            alert('Fehler beim Speichern des Jobs');
        }
    } catch (error) {
        console.error('Fehler:', error);
        alert('Fehler beim Speichern');
    }
}

function deleteJob(id) {
    deleteJobId = id;
    document.getElementById('deleteModal').style.display = 'flex';
}

async function confirmDelete() {
    if (!deleteJobId) return;
    
    try {
        const response = await fetch(`/api/jobs/${deleteJobId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            closeDeleteModal();
            clearFilters();
            await loadJobs();
            await loadStats();
            showNotification('Job gelöscht!', 'success');
        } else {
            alert('Fehler beim Löschen des Jobs');
        }
    } catch (error) {
        console.error('Fehler:', error);
        alert('Fehler beim Löschen');
    }
}

// ===== Manual Usage Modal =====
let manualUsageJobId = null;

function openManualUsageModal(jobId) {
    manualUsageJobId = jobId;
    const job = jobs.find(j => j.id === jobId);

    if (!job) {
        alert('Job nicht gefunden');
        return;
    }

    // Job-Name anzeigen
    document.getElementById('usageJobName').textContent = job.name;

    // Spulen-Dropdown befüllen (nur verfügbare Spulen)
    const spoolSelect = document.getElementById('usageSpool');
    spoolSelect.innerHTML = '<option value="">-- Spule wählen --</option>';

    spools.forEach(spool => {
        // Filtere nur Spulen die verfügbar sind (nicht leer, nicht im AMS eines anderen Druckers)
        const isAvailable = !spool.is_empty;
        if (isAvailable) {
            const name = spool.label || `#${spool.spool_number || spool.id.substring(0, 6)}`;
            const vendor = spool.vendor || '';
            const color = spool.tray_color ? ` (${spool.tray_color.substring(0, 6)})` : '';
            const displayName = vendor ? `${name} - ${vendor}${color}` : `${name}${color}`;
            spoolSelect.innerHTML += `<option value="${spool.id}">${displayName}</option>`;
        }
    });

    // Felder zurücksetzen
    document.getElementById('usageGrams').value = '';
    document.getElementById('usageMm').value = '';

    // Modal öffnen
    document.getElementById('manualUsageModal').style.display = 'flex';
}

function closeManualUsageModal() {
    document.getElementById('manualUsageModal').style.display = 'none';
    manualUsageJobId = null;
}

async function saveManualUsage(event) {
    event.preventDefault();

    const spool_id = document.getElementById('usageSpool').value;
    const used_g = parseFloat(document.getElementById('usageGrams').value);
    const usageMmMeters = parseFloat(document.getElementById('usageMm').value) || 0;
    const used_mm = usageMmMeters > 0 ? usageMmMeters * 1000 : null; // Meter → mm

    if (!spool_id) {
        alert('Bitte wähle eine Spule aus!');
        return;
    }

    if (!used_g && !used_mm) {
        alert('Bitte gib den Verbrauch in Gramm oder Meter an!');
        return;
    }

    const payload = {
        spool_id,
        used_g: used_g || null,
        used_mm: used_mm || null
    };

    try {
        const response = await fetch(`/api/jobs/${manualUsageJobId}/manual-usage`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            closeManualUsageModal();
            clearFilters();
            await loadJobs();
            await loadStats();
            await loadSpools(); // Spulen neu laden (Gewicht hat sich geändert)
            showNotification('Verbrauch erfolgreich nachgetragen!', 'success');
        } else {
            const error = await response.json();
            alert(`Fehler: ${error.detail || 'Verbrauch konnte nicht gespeichert werden'}`);
        }
    } catch (error) {
        console.error('Fehler:', error);
        alert('Fehler beim Speichern des Verbrauchs');
    }
}


// Close modal on ESC or background click
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeAddModal();
        closeDeleteModal();
        closeManualUsageModal();
    }
});

document.getElementById('jobModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'jobModal') closeAddModal();
});

document.getElementById('deleteModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'deleteModal') closeDeleteModal();
});

document.getElementById('manualUsageModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'manualUsageModal') closeManualUsageModal();
});
