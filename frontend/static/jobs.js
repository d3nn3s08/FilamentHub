// Global variables
let jobs = [];
let printers = [];
let spools = [];
let currentJobId = null;
let deleteJobId = null;
let overrideJobId = null;

// Load data on page load
document.addEventListener('DOMContentLoaded', async () => {
    // erst Stammdaten laden, dann Jobs rendern, damit IDs aufgeloest werden
    try {
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

async function loadSpools() {
    try {
        const response = await fetch('/api/spools/');
        spools = await response.json();
        
        const spoolSelect = document.getElementById('jobSpool');
        spools.forEach(spool => {
            const name = spool.label || `Spule ${spool.id.substring(0, 6)}`;
            const slot = spool.ams_slot ?? '-';
            const mat = spool.material_id ? ` | ${spool.material_id}` : '';
            spoolSelect.innerHTML += `<option value="${spool.id}">${name} (Slot ${slot}${mat})</option>`;
        });
    } catch (error) {
        console.error('Fehler beim Laden der Spulen:', error);
    }
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
    
    if (jobsList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align: center;">Keine Druckaufträge vorhanden</td></tr>';
        return;
    }
    
    jobsList.forEach(job => {
        const printer = printers.find(p => p.id === job.printer_id);
        const usages = Array.isArray(job.usages) ? job.usages : [];
        const primarySpool = spools.find(s => s.id === job.spool_id);
        
        const status = job.finished_at ? 
            '<span class="status-badge status-online">Abgeschlossen</span>' : 
            '<span class="status-badge status-printing">Aktiv</span>';
        
        const startDate = new Date(job.started_at).toLocaleString('de-DE');
        const endDate = job.finished_at ? new Date(job.finished_at).toLocaleString('de-DE') : '-';
        
        const verbrauch = `${job.filament_used_g.toFixed(1)}g / ${(job.filament_used_mm / 1000).toFixed(2)}m`;
        
        const row = `
            <tr>
                <td>${job.name}</td>
                <td>${printer ? printer.name : '<em>Unbekannt</em>'}</td>
                <td>
                    ${
                        usages.length
                            ? `<div class="usage-badges">
                                ${usages.map((u) => {
                                    const sp = spools.find((s) => s.id === u.spool_id);
                                    const color = sp?.tray_color ? '#' + sp.tray_color.substring(0, 6) : null;
                                    const label =
                                        sp?.label ||
                                        (u.slot !== undefined && u.slot !== null
                                            ? `Slot ${u.slot}`
                                            : `Spule ${(sp?.id || '').substring(0, 6)}`);
                                    return `
                                        <span class="usage-badge">
                                            ${color ? `<span class="color-preview" style="background:${color}"></span>` : ''}
                                            <span>${label} (${(u.used_g || 0).toFixed(1)}g / ${(((u.used_mm || 0) / 1000)).toFixed(2)}m)</span>
                                        </span>`;
                                }).join('')}
                               </div>`
                            : (primarySpool
                                ? `<div style="display:flex;align-items:center;gap:8px;">
                                        ${primarySpool.tray_color ? `<span class="color-preview" style="background:#${primarySpool.tray_color.substring(0,6)};width:16px;height:16px;border-radius:4px;display:inline-block;"></span>` : ''}
                                        <span>${primarySpool.label || `Spule ${primarySpool.id.substring(0,6)}`}</span>
                                   </div>`
                                : '-')
                    }
                </td>
                <td>${verbrauch}</td>
                <td>${startDate}</td>
                <td>${endDate}</td>
                <td>${status}</td>
                <td>
                    <div class="action-group">
                        <button class="btn btn-sm" onclick="editJob('${job.id}')">Bearbeiten</button>
                        <button class="btn btn-sm" onclick="openOverrideModal('${job.id}')">Zuordnung überschreiben</button>
                        <button class="btn btn-sm btn-danger" onclick="deleteJob('${job.id}')">Löschen</button>
                    </div>
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
        const matchStatus = !statusFilter || 
            (statusFilter === 'active' && !job.finished_at) ||
            (statusFilter === 'completed' && job.finished_at);
        
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
    document.getElementById('filamentMm').value = '0';
    document.getElementById('filamentG').value = '0';
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
    document.getElementById('filamentMm').value = job.filament_used_mm;
    document.getElementById('filamentG').value = job.filament_used_g;
    
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

function closeModal() {
    document.getElementById('jobModal').style.display = 'none';
    currentJobId = null;
}

async function saveJob() {
    const name = document.getElementById('jobName').value.trim();
    const printer_id = document.getElementById('jobPrinter').value;
    const spool_id = document.getElementById('jobSpool').value || null;
    const filament_used_mm = parseFloat(document.getElementById('filamentMm').value) || 0;
    const filament_used_g = parseFloat(document.getElementById('filamentG').value) || 0;
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
            closeModal();
            clearFilters();
            await loadJobs();
            await loadStats();
        } else {
            alert('Fehler beim Speichern des Jobs');
        }
    } catch (error) {
        console.error('Fehler:', error);
        alert('Fehler beim Speichern');
    }
}

function deleteJob(id) {
    const job = jobs.find(j => j.id === id);
    if (!job) return;
    
    deleteJobId = id;
    document.getElementById('deleteJobName').textContent = job.name;
    document.getElementById('deleteModal').style.display = 'flex';
}

function closeDeleteModal() {
    document.getElementById('deleteModal').style.display = 'none';
    deleteJobId = null;
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
        } else {
            alert('Fehler beim Löschen des Jobs');
        }
    } catch (error) {
        console.error('Fehler:', error);
        alert('Fehler beim Löschen');
    }
}


function openOverrideModal(id) {
    const job = jobs.find(j => j.id === id);
    if (!job) return;
    overrideJobId = id;
    const info = document.getElementById('overrideJobInfo');
    info.textContent = `${job.name} – ${job.printer_id || 'Unbekannt'}`;

    const select = document.getElementById('overrideSpoolSelect');
    select.innerHTML = '<option value="">Keine Spule zuweisen</option>';
    const filtered = spools.filter(s => !job.printer_id || s.printer_id === job.printer_id || !s.printer_id);
    filtered.forEach(spool => {
        const name = spool.label || `Spule ${spool.id.substring(0,6)}`;
        const slot = spool.ams_slot ?? '-';
        const mat = spool.tray_type || spool.material_id || '';
        const option = document.createElement('option');
        option.value = spool.id;
        option.textContent = `${name} (Slot ${slot}${mat ? ' | ' + mat : ''})`;
        if (job.spool_id === spool.id) option.selected = true;
        select.appendChild(option);
    });

    document.getElementById('overrideModal').style.display = 'flex';
}

function closeOverrideModal() {
    document.getElementById('overrideModal').style.display = 'none';
    overrideJobId = null;
}

async function saveOverride() {
    if (!overrideJobId) return;
    const spoolId = document.getElementById('overrideSpoolSelect').value || null;
    try {
        const response = await fetch(`/api/jobs/${overrideJobId}/spool`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ spool_id: spoolId })
        });
        if (response.ok) {
            closeOverrideModal();
            await loadJobs();
        } else {
            alert('Konnte Zuordnung nicht speichern');
        }
    } catch (err) {
        console.error('Override Fehler', err);
        alert('Konnte Zuordnung nicht speichern');
    }
}

async function removeOverride() {
    if (!overrideJobId) return;
    try {
        const response = await fetch(`/api/jobs/${overrideJobId}/spool`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ spool_id: null })
        });
        if (response.ok) {
            closeOverrideModal();
            await loadJobs();
        } else {
            alert('Konnte Zuordnung nicht entfernen');
        }
    } catch (err) {
        console.error('Override Entfernen Fehler', err);
        alert('Konnte Zuordnung nicht entfernen');
    }
}

// Close modal on ESC or background click
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
        closeDeleteModal();
        closeOverrideModal();
    }
});

document.getElementById('jobModal').addEventListener('click', (e) => {
    if (e.target.id === 'jobModal') closeModal();
});

document.getElementById('deleteModal').addEventListener('click', (e) => {
    if (e.target.id === 'deleteModal') closeDeleteModal();
});

document.getElementById('overrideModal').addEventListener('click', (e) => {
    if (e.target.id === 'overrideModal') closeOverrideModal();
});
