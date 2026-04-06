// Global variables
let jobs = [];
let printers = [];
let spools = [];
let materials = [];
let currentJobId = null;
let deleteJobId = null;
let overrideJobId = null;

// G-Code Modal Sortierung
let gcodeSortField = 'date';
let gcodeSortDirection = 'desc';
let gcodeOriginalFiles = [];  // Original-Liste (wird beim Filtern nicht überschrieben)

function toNumber(val) {
    const n = parseFloat(val);
    return isNaN(n) ? null : n;
}

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

    // Initiale Sortier-Indikatoren setzen
    updateSortIndicators();

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
        // Sortierung und Filter anwenden
        filterJobs();
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
        const materialColor = material ? material.color : null;

        // Farbe extrahieren (Material-Farbe oder Tray-Farbe)
        let colorName = '';
        if (materialColor) {
            // Verwende Material-Farbe
            colorName = materialColor.replace('#', '').toUpperCase();
        } else if (spool.tray_color) {
            // Verwende Tray-Farbe (Bambu Lab)
            colorName = spool.tray_color.substring(0, 6).toUpperCase();
        }

        // Spulen-Nummer oder "RFID"
        const spoolNumber = spool.spool_number ? `#${spool.spool_number}` : (spool.tray_uuid ? '📡 RFID' : '');

        // Restgewicht mit Format: "332.50g / 1000g"
        const weightCurrent = toNumber(spool.remaining_weight_g);
        const weightFull = toNumber(spool.total_weight_g);
        let weight = 'N/A';
        if (weightCurrent != null && weightFull != null) {
            weight = `${weightCurrent.toFixed(2)}g / ${weightFull.toFixed(0)}g`;
        } else if (weightCurrent != null) {
            weight = `${weightCurrent.toFixed(2)}g`;
        }

        // Label erstellen: "PLA Basic BLAU | #5 | 332.50g / 1000g"
        const parts = [materialName];
        if (colorName) parts.push(colorName);
        if (spoolNumber) parts.push(`| ${spoolNumber}`);
        parts.push(`| ${weight}`);

        const displayText = parts.join(' ');

        const option = `<option value="${spool.id}" data-search="${materialName.toLowerCase()} ${colorName.toLowerCase()} ${spoolNumber.toLowerCase()}">${displayText}</option>`;
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

    document.getElementById('jobCount').textContent = jobsList.length;

    if (jobsList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 2rem; color: var(--text-dim);">Keine Druckauftraege vorhanden</td></tr>';
        return;
    }

    const printerMap = new Map(printers.map(p => [p.id, p]));
    const spoolMap = new Map(spools.map(s => [s.id, s]));
    let allRows = '';

    jobsList.forEach(job => {
        const printer = printerMap.get(job.printer_id);
        const primarySpool = spoolMap.get(job.spool_id);

        const usages = job.spools || job.usages || job.spool_usages || [];
        const hasSpools = (usages && usages.length > 0) || job.spool_id;
        const needsTracking = (!hasSpools || job.filament_used_g === 0) && job.finished_at;

        let status;
        const jobStatus = (job.status || 'running').toLowerCase();

        if (jobStatus === 'completed') {
            status = '<span class="status-badge status-online">OK Abgeschlossen</span>';
        } else if (jobStatus === 'pending_weight') {
            status = '<span class="status-badge status-paused">Gewicht ausstehend</span>';
        } else if (jobStatus === 'running' || jobStatus === 'printing') {
            status = '<span class="status-badge status-printing">Aktiv</span>';
        } else if (jobStatus === 'failed' || jobStatus === 'error' || jobStatus === 'exception') {
            status = '<span class="status-badge status-offline">Fehlgeschlagen</span>';
        } else if (jobStatus === 'cancelled' || jobStatus === 'canceled') {
            status = '<span class="status-badge status-paused">Abgebrochen</span>';
        } else if (jobStatus === 'aborted' || jobStatus === 'stopped') {
            status = '<span class="status-badge status-paused">Gestoppt</span>';
        } else {
            status = `<span class="status-badge status-idle">${jobStatus}</span>`;
        }

        const verbrauch = (needsTracking && job.filament_used_g === 0)
            ? '<span style="color: var(--error, #dc3545); font-weight: bold;">Warnung 0g</span>'
            : `<strong>${job.filament_used_g.toFixed(1)}g</strong><br><small>${(job.filament_used_mm / 1000).toFixed(2)}m</small>`;

        const start = new Date(job.started_at);
        const end = job.finished_at ? new Date(job.finished_at) : new Date();
        const durationMs = end - start;
        const durationMin = Math.floor(durationMs / 60000);
        const hours = Math.floor(durationMin / 60);
        const minutes = durationMin % 60;
        const durationText = hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;

        let spoolDisplay;
        if (usages && usages.length > 0) {
            const spoolItems = usages.map(usage => {
                const spool = spoolMap.get(usage.spool_id);
                if (!spool) return null;
                const colorHex = spool.tray_color ? spool.tray_color.substring(0, 6) : 'cccccc';
                const slotNum = usage.slot !== null && usage.slot !== undefined ? usage.slot : '?';
                const label = spool.label || `AMS Slot ${slotNum}`;
                const usedG = parseFloat(usage.used_g || 0);
                const usedGText = usedG > 0
                    ? `${usedG.toFixed(1)}g`
                    : (job.finished_at ? '—' : 'läuft...');
                const remainText = spool.weight_current != null ? ` | ${Math.round(spool.weight_current)}g verbleibend` : '';
                return `<div style="display:flex;align-items:center;gap:3px;padding:2px 6px;background:rgba(255,255,255,0.1);border-radius:4px;" title="${label}: ${usedGText}${remainText}"><span class="color-preview" style="background:#${colorHex}; width:12px; height:12px; border-radius:2px;"></span><span style="font-size:11px;color:var(--text-dim);">Slot ${slotNum}</span></div>`;
            }).filter(Boolean);
            spoolDisplay = spoolItems.length > 0 ? `<div style="display:flex;align-items:center;gap:4px;flex-wrap:wrap;">${spoolItems.join('')}</div>` : '<span style="color: var(--text-dim);">-</span>';
        } else if (primarySpool) {
            spoolDisplay = `<div style="display:flex;align-items:center;gap:8px;">${primarySpool.tray_color ? `<span class="color-preview" style="background:#${primarySpool.tray_color.substring(0,6)}"></span>` : ''}<span>${primarySpool.label || `Spule ${primarySpool.id.substring(0,6)}`}</span></div>`;
        } else {
            spoolDisplay = needsTracking ? '<span style="color: var(--error, #dc3545); font-weight: bold;">Warnung Keine</span>' : '<span style="color: var(--text-dim);">-</span>';
        }

        const canRefreshGcode = job.finished_at && printer && printer.ip_address && (printer.api_key || printer.printer_type === 'klipper');
        const showCloudButton = job.finished_at || jobStatus === 'running'; // Cloud auch bei laufenden Jobs anbieten
        // "Force Complete"-Button: nur für hängende running-Jobs (kein finished_at)
        const isStuckRunning = jobStatus === 'running' && !job.finished_at;

        const actions = needsTracking
            ? `<div class="table-actions"><button class="btn btn-warning btn-sm" onclick="openManualUsageModal('${job.id}')" title="Verbrauch nachtragen" style="padding: 4px 8px; font-size: 0.85rem;">&#9998; Nachtragen</button>${canRefreshGcode ? `<button class="btn btn-secondary btn-sm" onclick="refreshWeightFromGcode('${job.id}')" title="Gewicht aus G-Code laden" style="padding: 4px 8px; font-size: 0.85rem;">G-Code</button>` : ''}<button class="btn btn-info btn-sm" onclick="fetchCloudDataForJob('${job.id}')" title="Daten aus Bambu Cloud laden" style="padding: 4px 8px; font-size: 0.85rem;">Cloud</button><button class="btn-icon btn-delete" onclick="deleteJob('${job.id}')" title="Loeschen">&#128465;</button></div>`
            : `<div class="table-actions"><button class="btn-icon" onclick="editJob('${job.id}')" title="Bearbeiten">&#9998;</button>${canRefreshGcode ? `<button class="btn btn-secondary btn-sm" onclick="refreshWeightFromGcode('${job.id}')" title="Gewicht aus G-Code aktualisieren" style="padding: 4px 8px; font-size: 0.85rem;">G-Code</button>` : ''}${showCloudButton ? `<button class="btn btn-info btn-sm" onclick="fetchCloudDataForJob('${job.id}')" title="Daten aus Bambu Cloud laden" style="padding: 4px 8px; font-size: 0.85rem;">Cloud</button>` : ''}${isStuckRunning ? `<button class="btn btn-success btn-sm" onclick="forceCompleteJob('${job.id}')" title="Job als abgeschlossen markieren (Drucker hat FINISH nicht gesendet)" style="padding: 4px 8px; font-size: 0.85rem;">✓ Fertig</button>` : ''}<button class="btn-icon btn-delete" onclick="deleteJob('${job.id}')" title="Loeschen">&#128465;</button></div>`;

        const rowClass = needsTracking ? ' class="row-warning"' : '';
        const dateText = start.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
        const timeText = start.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
        const jobDisplayName = job.display_name || job.name;

        allRows += `<tr${rowClass}><td><strong>${needsTracking ? 'Warnung ' : ''}${jobDisplayName}</strong><br><small style="color: var(--text-dim);">ID: ${job.task_id || job.id || '-'}</small></td><td>${printer ? printer.name : '<em style="color: var(--text-dim);">Unbekannt</em>'}</td><td>${spoolDisplay}</td><td>${verbrauch}</td><td>${status}</td><td><strong>${dateText}</strong><br><small style="color: var(--text-dim);">${timeText}</small></td><td><strong>${durationText}</strong></td><td>${actions}</td></tr>`;
    });

    tbody.innerHTML = allRows;
}

// Aktuelle Sortierung (global)
let currentSort = { field: 'started_at', direction: 'desc' };

function filterJobs() {
    const search = document.getElementById('searchInput').value.toLowerCase();
    const printerFilter = document.getElementById('filterPrinter').value;
    const statusFilter = document.getElementById('filterStatus').value;

    let filtered = jobs.filter(job => {
        // Suche in name/display_name + task_id + lokaler id
        const searchableName = (job.display_name || job.name || '').toLowerCase();
        const matchSearch =
            searchableName.includes(search) ||
            (job.task_id || '').toLowerCase().includes(search) ||
            (job.id || '').toLowerCase().includes(search);
        // FIX: Konvertiere beide zu Strings für sicheren Vergleich
        const matchPrinter = !printerFilter || String(job.printer_id) === String(printerFilter);

        // Erweiterter Status-Filter mit "no-tracking"
        let matchStatus = !statusFilter;
        if (statusFilter === 'active') {
            matchStatus = !job.finished_at;
        } else if (statusFilter === 'completed') {
            matchStatus = job.finished_at && (job.status || '').toLowerCase() !== 'pending_weight';
        } else if (statusFilter === 'no-tracking') {
            // Jobs ohne Tracking: kein Verbrauch ODER keine Spule UND abgeschlossen
            // Multi-Color Support: Prüfe auch job.spools/usages Array
            const usagesForStatus = job.spools || job.usages || job.spool_usages || [];
            const hasSpools = (usagesForStatus && usagesForStatus.length > 0) || job.spool_id;
            matchStatus = (!hasSpools || job.filament_used_g === 0) && job.finished_at;
        }

        return matchSearch && matchPrinter && matchStatus;
    });

    // Sortierung anwenden
    filtered = sortJobs(filtered);

    renderJobs(filtered);
}

function sortJobs(jobsList) {
    const { field, direction } = currentSort;
    const multiplier = direction === 'asc' ? 1 : -1;

    return [...jobsList].sort((a, b) => {
        let valA, valB;

        switch (field) {
            case 'name':
                // Sortiere nach display_name wenn vorhanden, sonst name
                valA = (a.display_name || a.name || '').toLowerCase();
                valB = (b.display_name || b.name || '').toLowerCase();
                return multiplier * valA.localeCompare(valB);

            case 'started_at':
                valA = a.started_at ? new Date(a.started_at).getTime() : 0;
                valB = b.started_at ? new Date(b.started_at).getTime() : 0;
                return multiplier * (valA - valB);

            case 'finished_at':
                valA = a.finished_at ? new Date(a.finished_at).getTime() : 0;
                valB = b.finished_at ? new Date(b.finished_at).getTime() : 0;
                return multiplier * (valA - valB);

            case 'filament':
                valA = a.filament_used_g || 0;
                valB = b.filament_used_g || 0;
                return multiplier * (valA - valB);

            case 'duration':
                const durationA = a.finished_at && a.started_at
                    ? new Date(a.finished_at) - new Date(a.started_at)
                    : (a.started_at ? Date.now() - new Date(a.started_at) : 0);
                const durationB = b.finished_at && b.started_at
                    ? new Date(b.finished_at) - new Date(b.started_at)
                    : (b.started_at ? Date.now() - new Date(b.started_at) : 0);
                return multiplier * (durationA - durationB);

            default:
                return 0;
        }
    });
}

function setSortField(field) {
    if (currentSort.field === field) {
        // Toggle direction
        currentSort.direction = currentSort.direction === 'asc' ? 'desc' : 'asc';
    } else {
        currentSort.field = field;
        currentSort.direction = 'desc';  // Default: neueste zuerst
    }

    // Update UI Sort Indicators
    updateSortIndicators();

    // Refilter (which also sorts)
    filterJobs();
}

function updateSortIndicators() {
    // Entferne alle Indikatoren
    document.querySelectorAll('th[data-sort]').forEach(th => {
        th.classList.remove('sort-asc', 'sort-desc');
    });

    // Setze aktuellen Indikator
    const currentTh = document.querySelector(`th[data-sort="${currentSort.field}"]`);
    if (currentTh) {
        currentTh.classList.add(currentSort.direction === 'asc' ? 'sort-asc' : 'sort-desc');
    }

    // Sync Dropdown
    const sortSelect = document.getElementById('sortSelect');
    if (sortSelect) {
        sortSelect.value = `${currentSort.field}-${currentSort.direction}`;
    }
}

function applySortFromSelect() {
    const sortSelect = document.getElementById('sortSelect');
    if (!sortSelect) return;

    const [field, direction] = sortSelect.value.split('-');
    currentSort.field = field;
    currentSort.direction = direction;

    updateSortIndicators();
    filterJobs();
}

function clearFilters() {
    document.getElementById('searchInput').value = '';
    document.getElementById('filterPrinter').value = '';
    document.getElementById('filterStatus').value = '';
    // Sortierung auf Standard zurücksetzen
    currentSort = { field: 'started_at', direction: 'desc' };
    const sortSelect = document.getElementById('sortSelect');
    if (sortSelect) sortSelect.value = 'started_at-desc';
    updateSortIndicators();
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

    // Bei neuen Jobs sind Verbrauchsfelder immer editierbar
    const mmField = document.getElementById('filamentUsedMm');
    const gField = document.getElementById('filamentUsedG');
    mmField.readOnly = false;
    gField.readOnly = false;
    mmField.style.backgroundColor = '';
    gField.style.backgroundColor = '';
    mmField.title = '';
    gField.title = '';

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
    // display_name bearbeiten (nicht name - das bleibt für Matching)
    document.getElementById('jobName').value = job.display_name || job.name;
    document.getElementById('jobPrinter').value = job.printer_id;
    document.getElementById('jobSpool').value = job.spool_id || '';
    document.getElementById('filamentUsedMm').value = job.filament_used_mm;
    document.getElementById('filamentUsedG').value = job.filament_used_g;

    // Verbrauchsfelder: Nur bei manuellen Jobs editierbar
    // MQTT-getrackte Jobs haben automatischen Verbrauch -> readonly
    // Nur auf filament_used_g prüfen, da A1 Mini keine filament_used_mm-Daten liefert
    const hasTracking = job.filament_used_g > 0;
    const mmField = document.getElementById('filamentUsedMm');
    const gField = document.getElementById('filamentUsedG');

    if (hasTracking) {
        mmField.readOnly = true;
        gField.readOnly = true;
        mmField.style.backgroundColor = 'var(--bg-secondary, #f5f5f5)';
        gField.style.backgroundColor = 'var(--bg-secondary, #f5f5f5)';
        mmField.title = 'Automatisch getrackt (nicht editierbar)';
        gField.title = 'Automatisch getrackt (nicht editierbar)';
    } else {
        mmField.readOnly = false;
        gField.readOnly = false;
        mmField.style.backgroundColor = '';
        gField.style.backgroundColor = '';
        mmField.title = '';
        gField.title = '';
    }

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

    const displayName = document.getElementById('jobName').value.trim();
    const printer_id = document.getElementById('jobPrinter').value;
    const spool_id = document.getElementById('jobSpool').value || null;
    const filament_used_mm = parseFloat(document.getElementById('filamentUsedMm').value) || 0;
    const filament_used_g = parseFloat(document.getElementById('filamentUsedG').value) || 0;
    const started_at = document.getElementById('startedAt').value;
    const finished_at = document.getElementById('finishedAt').value || null;

    if (!displayName || !printer_id) {
        alert('Bitte füllen Sie alle Pflichtfelder aus!');
        return;
    }

    // Bei bestehendem Job: NUR display_name senden (PATCH)
    // Bei neuem Job: Alle Felder senden (POST)
    const jobData = currentJobId ? {
        display_name: displayName
    } : {
        name: displayName,
        display_name: displayName,
        printer_id,
        spool_id,
        filament_used_mm,
        filament_used_g,
        started_at: started_at ? new Date(started_at).toISOString() : new Date().toISOString(),
        finished_at: finished_at ? new Date(finished_at).toISOString() : null
    };

    try {
        const url = currentJobId ? `/api/jobs/${currentJobId}` : '/api/jobs/';
        // PATCH für Updates (nur display_name ändern), POST für neue Jobs
        const method = currentJobId ? 'PATCH' : 'POST';

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

async function markJobAsCompleted() {
    // Erst speichern, dann Status ändern
    const name = document.getElementById('jobName').value.trim();
    const printer_id = document.getElementById('jobPrinter').value;
    const spool_id = document.getElementById('jobSpool').value || null;
    const filament_used_mm = parseFloat(document.getElementById('filamentUsedMm').value) || 0;
    const filament_used_g = parseFloat(document.getElementById('filamentUsedG').value) || 0;
    const started_at = document.getElementById('startedAt').value;
    const finished_at = document.getElementById('finishedAt').value;
    
    if (!name || !printer_id) {
        alert('Bitte füllen Sie alle Pflichtfelder aus!');
        return;
    }
    
    // Stelle sicher dass finished_at gesetzt ist
    let finalFinishedAt = finished_at;
    if (!finalFinishedAt) {
        finalFinishedAt = new Date().toISOString();
        document.getElementById('finishedAt').value = new Date().toLocaleString('de-DE', {
            year: 'numeric', month: '2-digit', day: '2-digit',
            hour: '2-digit', minute: '2-digit'
        });
    }
    
    const jobData = {
        name,
        printer_id,
        spool_id,
        filament_used_mm,
        filament_used_g,
        started_at: started_at ? new Date(started_at).toISOString() : new Date().toISOString(),
        finished_at: finalFinishedAt ? new Date(finalFinishedAt).toISOString() : new Date().toISOString(),
        status: 'completed'  // Set status to completed
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
            showNotification('✓ Job als abgeschlossen markiert!', 'success');
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

async function forceCompleteJob(id) {
    if (!confirm('Job als "Abgeschlossen" markieren?\n\nDies ist nötig wenn der Drucker den FINISH-Status nicht gesendet hat (z.B. A1 Mini nach Server-Neustart).')) return;

    try {
        const response = await fetch(`/api/jobs/${id}/force-complete`, { method: 'POST' });
        if (response.ok) {
            showNotification('Job als abgeschlossen markiert!', 'success');
            await loadJobs();
            await loadStats();
        } else {
            const err = await response.json().catch(() => ({}));
            alert('Fehler: ' + (err.detail || 'Unbekannter Fehler'));
        }
    } catch (error) {
        console.error('Fehler beim Force-Complete:', error);
        alert('Netzwerkfehler');
    }
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


    // ===== G-Code Weight Refresh =====
    let gcodeRefreshJobId = null;
    let gcodeSelectionFiles = [];
    let gcodeConfirmData = null;

    // pending_weight = Job fertig aber kein Gewicht/Spule → auch Bestätigung anzeigen
    const GCODE_CONFIRM_STATUSES = ['failed', 'aborted', 'cancelled', 'stopped', 'error', 'pending_weight'];

    window.refreshWeightFromGcode = async function(jobId, selectedFilename = null) {
        gcodeRefreshJobId = jobId;

        const job = jobs.find(j => j.id === jobId);
        const isFailedJob = job && GCODE_CONFIRM_STATUSES.includes((job.status || '').toLowerCase());

        // Für fehlgeschlagene/abgebrochene Jobs: kein File-Selection-Modal vorab.
        // Wir scannen im Hintergrund und zeigen dann direkt die Bestätigungs-Ansicht.
        // Für normale Jobs: File-Selection-Modal mit Spinner sofort öffnen.
        if (!isFailedJob && !selectedFilename) {
            if (job) {
                document.getElementById('gcodeJobName').textContent = job.name;
                document.getElementById('gcodeSelectionModal').style.display = 'flex';
            }
            showGcodeLoading(true);
        } else if (!isFailedJob) {
            showGcodeLoading(true);
        }

        try {

            // Für fehlgeschlagene/abgebrochene Jobs immer dry_run, damit User das Gewicht zuerst sieht
            const useDryRun = isFailedJob;

            let url = selectedFilename
                ? `/api/jobs/${jobId}/refresh-weight-gcode?gcode_filename=${encodeURIComponent(selectedFilename)}`
                : `/api/jobs/${jobId}/refresh-weight-gcode`;

            if (useDryRun) url += (url.includes('?') ? '&' : '?') + 'dry_run=true';

            updateGcodeLoadingStatus("Verbindung zum Drucker...");

            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });

            updateGcodeLoadingStatus("Verarbeitung...");
            const result = await response.json();

            showGcodeLoading(false);

            if (result.needs_confirmation) {
                // Inline-Vorschau im File-Selection-Modal anzeigen (kein zweites Modal)
                _showInlineWeightPreview(jobId, result);
            } else if (result.connection_error) {
                // Verbindungsfehler: Modal öffnen und Fehler-Panel anzeigen
                _showGcodeConnectionError(jobId, result);
            } else if (result.success) {
                showNotification(
                    `✅ ${result.message} (${result.weight_diff > 0 ? '+' : ''}${result.weight_diff.toFixed(1)}g)`,
                    'success'
                );
                window.closeGcodeSelectionModal();
                await loadJobs();
                await loadStats();
            } else if (result.multiple_matches) {
                window.openGcodeSelectionModal(jobId, result.files, result.message, result.connection_method);
            } else if (result.no_match) {
                window.openGcodeSelectionModal(jobId, result.available_files, result.message, result.connection_method);
            } else {
                alert(`❌ ${result.error || 'G-Code Download fehlgeschlagen'}`);
                window.closeGcodeSelectionModal();
            }

        } catch (error) {
            console.error('G-Code Refresh Error:', error);
            alert('Fehler bei der Verbindung zum Drucker');
            showGcodeLoading(false);
            window.closeGcodeSelectionModal();
        }
    }

    // Zeigt Gewicht-Vorschau + Empfehlung inline im File-Selection-Modal
    function _showInlineWeightPreview(jobId, data) {
        const weight = data.weight != null ? parseFloat(data.weight) : null;
        gcodeConfirmData = {
            jobId,
            filename: data.filename,
            originalWeight: weight,
            durationMin: data.duration_min,
            filamentWeightsG: data.filament_weights_g || null,
        };

        const modal = document.getElementById('gcodeSelectionModal');

        // Dateiliste aufbauen (nur lokale Drucker-Dateien, kein Cloud-Mix)
        let fileList;
        if (data.available_files && data.available_files.length > 0) {
            fileList = data.available_files.map(f =>
                f.name === data.filename
                    ? { ...f, weight_g: weight, _auto_matched: true }
                    : f
            );
        } else {
            fileList = [{ name: data.filename, weight_g: weight, mtime_str: null, _auto_matched: true }];
        }

        const modalMsg = data.filename && !data.no_match
            ? `Automatisch gefunden: "${data.filename}" — andere Datei waehlen falls falsch`
            : data.job_name
            ? `Keine passende Datei fuer "${data.job_name}" — bitte manuell auswaehlen`
            : 'Datei auswaehlen';

        if (modal.style.display === 'none' || !modal.style.display) {
            window.openGcodeSelectionModal(jobId, fileList, modalMsg, data.connection_method);
        } else {
            gcodeOriginalFiles = [...fileList];
            gcodeSelectionFiles = fileList;
            renderGcodeOptions(fileList, false);
            const infoTitle = document.getElementById('gcodeInfoTitle');
            if (infoTitle) infoTitle.textContent = `ℹ️ ${modalMsg}`;
        }

        // Verstecktes Select-Feld setzen
        const selectEl = document.getElementById('gcodeFileSelect');
        if (selectEl && data.filename) selectEl.value = data.filename;

        // Gewicht anzeigen wenn vorhanden
        if (weight != null) {
            const previewBox = document.getElementById('gcodeWeightPreview');
            document.getElementById('gcodePreviewWeightDisplay').textContent = `${weight.toFixed(2)} g`;
            const weightInput = document.getElementById('gcodePreviewWeight');
            weightInput.value = weight.toFixed(2);
            previewBox.style.display = 'block';
            _updatePreviewRecommendation(weight, data.duration_min);
            _renderSpoolBreakdown(data.filament_weights_g);
            const btn = document.getElementById('gcodeConfirmBtn');
            if (btn) btn.textContent = `Uebernehmen (${weight.toFixed(1)} g)`;
        }

        showGcodeLoading(false);
    }

    window.gcodeResetPreviewWeight = function() {
        if (gcodeConfirmData?.originalWeight != null) {
            document.getElementById('gcodePreviewWeight').value = gcodeConfirmData.originalWeight.toFixed(2);
        }
    }

    // Lädt Gewicht-Preview für eine gewählte Datei (via dry_run)
    async function _reloadPreviewForFile(jobId, filename, knownWeightG) {
        const recEl = document.getElementById('gcodePreviewRecommendation');
        const displayEl = document.getElementById('gcodePreviewWeightDisplay');
        const inputEl = document.getElementById('gcodePreviewWeight');
        const btn = document.getElementById('gcodeConfirmBtn');
        const previewBox = document.getElementById('gcodeWeightPreview');

        // Preview-Box immer anzeigen
        if (previewBox) previewBox.style.display = 'block';

        // Hilfsfunktion: Gewicht-Zelle in Tabelle aktualisieren
        function _updateWeightCell(w) {
            const allRows = document.querySelectorAll('#gcodeFilesBody tr');
            allRows.forEach(r => {
                // Suche die Zeile mit diesem Dateinamen (2. Spalte = Name)
                const nameTd = r.querySelectorAll('td')[1];
                if (nameTd && nameTd.querySelector('span')?.textContent?.trim() === filename) {
                    // 3. Spalte = Gewicht (Index 2)
                    const wTd = r.querySelectorAll('td')[2];
                    if (wTd) {
                        if (w && w > 0) {
                            wTd.textContent = w.toFixed(1) + ' g';
                            wTd.classList.add('loaded');
                        } else {
                            wTd.textContent = '—';
                            wTd.classList.remove('loaded');
                        }
                    }
                }
            });
        }

        // Falls Gewicht schon bekannt (aus Dateiliste-Metadaten) → direkt anzeigen
        if (knownWeightG && knownWeightG > 0) {
            const w = parseFloat(knownWeightG);
            gcodeConfirmData = { ...(gcodeConfirmData || {}), filename, originalWeight: w };
            displayEl.textContent = `${w.toFixed(2)} g`;
            inputEl.value = w.toFixed(2);
            if (btn) btn.textContent = `✓ Übernehmen (${w.toFixed(1)} g)`;
            _updatePreviewRecommendation(w, gcodeConfirmData?.durationMin);
            _renderSpoolBreakdown(gcodeConfirmData?.filamentWeightsG || null);
            _updateWeightCell(w);
            return;
        }

        // Gewicht nicht bekannt → dry_run API-Call
        displayEl.textContent = '…';
        displayEl.style.color = 'var(--text-dim)';
        inputEl.value = '';
        recEl.textContent = '⏳ Bitte warten… Lade Gewichtsdaten';
        recEl.style.cssText = 'background:rgba(52,152,219,0.08); border:1px solid rgba(52,152,219,0.2); border-radius:6px; padding:9px 13px; font-size:13px; color:#3498db;';
        if (btn) btn.textContent = '✓ Übernehmen';

        try {
            const url = `/api/jobs/${jobId}/refresh-weight-gcode?gcode_filename=${encodeURIComponent(filename)}&dry_run=true`;
            const resp = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
            const result = await resp.json();
            if (result.needs_confirmation && result.weight > 0) {
                const w = parseFloat(result.weight);
                gcodeConfirmData = { ...(gcodeConfirmData || {}), filename, originalWeight: w,
                    durationMin: result.duration_min ?? gcodeConfirmData?.durationMin,
                    filamentWeightsG: result.filament_weights_g || gcodeConfirmData?.filamentWeightsG || null };
                displayEl.textContent = `${w.toFixed(2)} g`;
                displayEl.style.color = '#2ecc71';
                inputEl.value = w.toFixed(2);
                if (btn) btn.textContent = `✓ Übernehmen (${w.toFixed(1)} g)`;
                _updatePreviewRecommendation(w, gcodeConfirmData.durationMin);
                _renderSpoolBreakdown(gcodeConfirmData.filamentWeightsG);
                _updateWeightCell(w);
            } else {
                displayEl.textContent = '—';
                displayEl.style.color = 'var(--text-dim)';
                recEl.textContent = result.error || 'Kein Gewicht gefunden — bitte manuell eingeben';
                recEl.style.cssText = 'background:rgba(255,165,0,0.1); border:1px solid rgba(255,165,0,0.3); border-radius:6px; padding:9px 13px; font-size:13px; color:#f0a500;';
                _updateWeightCell(null);
            }
        } catch (e) {
            displayEl.textContent = '—';
            displayEl.style.color = 'var(--text-dim)';
            recEl.textContent = '⚠️ Fehler beim Laden — Verbindungsproblem';
            recEl.style.cssText = 'background:rgba(231,76,60,0.1); border:1px solid rgba(231,76,60,0.3); border-radius:6px; padding:9px 13px; font-size:13px; color:#e74c3c;';
        }
    }

    function _updatePreviewRecommendation(weight, durationMin) {
        const recEl = document.getElementById('gcodePreviewRecommendation');
        if (!recEl) return;
        if (durationMin > 0) {
            const gPerMin = weight / durationMin;
            let text, bg;
            if (gPerMin < 0.05 || gPerMin > 3.0) {
                text = `⚠️ ${weight.toFixed(1)} g bei ${durationMin} min klingt ungewöhnlich (${gPerMin.toFixed(2)} g/min). Bitte prüfen.`;
                bg = 'rgba(231,76,60,0.15)';
            } else if (gPerMin < 0.15) {
                text = `💡 ${weight.toFixed(1)} g bei ${durationMin} min — kleines Objekt (${gPerMin.toFixed(2)} g/min). Plausibel.`;
                bg = 'rgba(52,152,219,0.15)';
            } else {
                text = `✅ ${weight.toFixed(1)} g bei ${durationMin} min klingt plausibel (${gPerMin.toFixed(2)} g/min).`;
                bg = 'rgba(46,204,113,0.15)';
            }
            recEl.textContent = text;
            recEl.style.cssText = `background:${bg}; border:1px solid ${bg.replace('0.15','0.4')}; border-radius:6px; padding:9px 13px; font-size:13px;`;
        } else {
            recEl.textContent = `ℹ️ ${weight.toFixed(1)} g ausgewaehlt — Dauer unbekannt, kein Plausibilitaetscheck.`;
            recEl.style.cssText = 'background:rgba(255,255,255,0.04); border:1px solid rgba(255,255,255,0.12); border-radius:6px; padding:9px 13px; font-size:13px; color:var(--text-dim);';
        }
    }

    function _openGcodeConfirmModal(jobId, data) {
        const weight = data.weight != null ? parseFloat(data.weight) : null;
        gcodeConfirmData = { jobId, filename: data.filename, originalWeight: weight };

        // Job-Status aus lokaler Liste holen
        const job = jobs.find(j => j.id === jobId);
        const statusLabels = {
            failed: '❌ Fehlgeschlagen', aborted: '⛔ Abgebrochen',
            cancelled: '🚫 Abgebrochen', stopped: '⏹ Gestoppt', error: '❌ Fehler'
        };
        const statusKey = (job?.status || '').toLowerCase();

        // Felder befüllen
        document.getElementById('gcodeConfirmJobName').textContent = data.job_name || jobId;
        document.getElementById('gcodeConfirmFilename').textContent = data.filename || '—';
        document.getElementById('gcodeConfirmDuration').textContent =
            data.duration_min != null ? `${data.duration_min} min` : '—';
        document.getElementById('gcodeConfirmStatus').textContent =
            statusLabels[statusKey] || job?.status || '—';
        document.getElementById('gcodeConfirmWeightDisplay').textContent =
            weight != null ? `${weight.toFixed(2)} g` : '—';
        document.getElementById('gcodeConfirmWeight').value =
            weight != null ? weight.toFixed(2) : '';

        // Empfehlung berechnen
        const recBox = document.getElementById('gcodeConfirmRecommendation');
        if (weight != null && data.duration_min > 0) {
            const gPerMin = weight / data.duration_min;
            let recText, recColor;
            if (gPerMin < 0.05) {
                recText = `⚠️ ${weight.toFixed(1)} g bei ${data.duration_min} min ist ungewöhnlich wenig (${gPerMin.toFixed(2)} g/min). Bitte prüfen — ggf. falscher G-Code.`;
                recColor = 'rgba(231,76,60,0.15)';
            } else if (gPerMin > 3.0) {
                recText = `⚠️ ${weight.toFixed(1)} g bei ${data.duration_min} min ist ungewöhnlich viel (${gPerMin.toFixed(2)} g/min). Bitte prüfen — ggf. falscher G-Code.`;
                recColor = 'rgba(231,76,60,0.15)';
            } else if (gPerMin < 0.15) {
                recText = `💡 ${weight.toFixed(1)} g bei ${data.duration_min} min klingt nach einem sehr kleinen Objekt (${gPerMin.toFixed(2)} g/min). Plausibel für Miniaturen.`;
                recColor = 'rgba(52,152,219,0.15)';
            } else {
                recText = `✅ ${weight.toFixed(1)} g bei ${data.duration_min} min klingt plausibel (${gPerMin.toFixed(2)} g/min).`;
                recColor = 'rgba(46,204,113,0.15)';
            }
            recBox.textContent = recText;
            recBox.style.background = recColor;
            recBox.style.border = `1px solid ${recColor.replace('0.15', '0.4')}`;
            recBox.style.display = 'block';
        } else {
            recBox.style.display = 'none';
        }

        document.getElementById('gcodeConfirmModal').style.display = 'flex';
    }

    window.closeGcodeConfirmModal = function() {
        document.getElementById('gcodeConfirmModal').style.display = 'none';
        gcodeConfirmData = null;
    }

    window.applyGcodeConfirmedWeight = async function() {
        if (!gcodeConfirmData) return;

        const weightInput = document.getElementById('gcodeConfirmWeight');
        const confirmedWeight = parseFloat(weightInput.value);

        if (isNaN(confirmedWeight) || confirmedWeight <= 0) {
            alert('Bitte ein gültiges Gewicht eingeben (> 0)');
            return;
        }

        const { jobId, filename } = gcodeConfirmData;
        window.closeGcodeConfirmModal();

        try {
            let url = `/api/jobs/${jobId}/refresh-weight-gcode`
                + `?gcode_filename=${encodeURIComponent(filename)}`
                + `&confirmed_weight=${confirmedWeight}`;
            if (gcodeConfirmData?.filamentWeightsG) {
                url += `&filament_weights_json=${encodeURIComponent(JSON.stringify(gcodeConfirmData.filamentWeightsG))}`;
            }

            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const result = await response.json();

            if (result.success) {
                showNotification(
                    `✅ ${result.message} (${result.weight_diff > 0 ? '+' : ''}${result.weight_diff.toFixed(1)}g)`,
                    'success'
                );
                await loadJobs();
                await loadStats();
            } else {
                alert(`❌ ${result.error || 'Fehler beim Speichern des Gewichts'}`);
            }
        } catch (error) {
            console.error('G-Code Confirm Error:', error);
            alert('Fehler beim Speichern des Gewichts');
        }
    }

function showGcodeLoading(isLoading) {
    const spinner = document.getElementById('gcodeLoadingSpinner');
    const formActions = document.getElementById('gcodeFormActions');
    
    if (isLoading) {
        spinner.style.display = 'block';
        formActions.style.display = 'none';
    } else {
        spinner.style.display = 'none';
        formActions.style.display = 'flex';
    }
}

function updateGcodeLoadingStatus(message) {
    const statusText = document.getElementById('gcodeLoadingStatus');
    if (statusText) {
        statusText.textContent = message;
    }
}

window.openGcodeSelectionModal = function(jobId, files, message = null, connectionMethod = null) {
        const job = jobs.find(j => j.id === jobId);
        if (!job) return;

        document.getElementById('gcodeJobName').textContent = job.name;

        const select = document.getElementById('gcodeFileSelect');
        select.innerHTML = '';
        gcodeOriginalFiles = files || [];  // Original speichern
        gcodeSelectionFiles = [...gcodeOriginalFiles];  // Kopie für Filterung

        const infoTitle = document.getElementById('gcodeInfoTitle');
        if (infoTitle) {
            infoTitle.textContent = message ? `⚠️ ${message}` : 'ℹ️ G-Code Datei wählen';
        }

        // Verbindungsstatus im Header anzeigen
        _updateGcodeConnStatus(job, connectionMethod);

        // Fehler-Panel ausblenden, Datei- und Preview-Panel anzeigen
        const errPanel = document.getElementById('gcodeErrorPanel');
        const filePanel = document.getElementById('gcodeFilePanel');
        const previewPanel = document.getElementById('gcodePreviewPanel');
        const formActions = document.getElementById('gcodeFormActions');
        if (errPanel) errPanel.style.display = 'none';
        if (filePanel) filePanel.style.display = '';
        if (previewPanel) previewPanel.style.display = '';
        if (formActions) formActions.style.display = 'flex';

        // Reset Sortierung auf Standard (Datum, neueste zuerst)
        gcodeSortField = 'date';
        gcodeSortDirection = 'desc';
        updateGcodeSortIndicators();

        renderGcodeOptions(gcodeSelectionFiles, false);

        gcodeRefreshJobId = jobId;
        document.getElementById('gcodeSelectionModal').style.display = 'flex';

        // Job IDs im Hintergrund laden und Spalte befüllen
        _loadJobIdMap().then(map => _updateJobIdCells(map, gcodeSelectionFiles));

        // Gewichte im Hintergrund laden (sofort nach Öffnen)
        _loadAllWeightsOnOpen(jobId, gcodeSelectionFiles);
    }

    // Zeigt Verbindungsstatus im Modal-Header
    function _updateGcodeConnStatus(job, connectionMethod) {
        const el = document.getElementById('gcodeConnStatus');
        if (!el) return;
        if (!connectionMethod) { el.textContent = ''; return; }
        const printer = job?.printer_name || '';
        if (connectionMethod === 'ftps' || connectionMethod === 'ftps_ftplib') {
            const label = connectionMethod === 'ftps_ftplib' ? 'FTPLib-FTPS' : 'FTPS';
            el.innerHTML = `<span style="color:#2ecc71;">🖨️ ${printer} — ${label} verbunden</span>`;
        } else if (connectionMethod === 'cloud_fallback') {
            el.innerHTML = `<span style="color:#3498db;">☁ ${printer} — Cloud Fallback aktiv</span>`;
        } else if (connectionMethod && connectionMethod.startsWith('ftps_failed')) {
            el.innerHTML = `<span style="color:#e74c3c;">❌ ${printer} — Verbindung fehlgeschlagen</span>`;
        } else {
            el.textContent = '';
        }
    }

    // Zeigt Verbindungsfehler-Panel im Modal
    function _showGcodeConnectionError(jobId, result) {
        const job = jobs.find(j => j.id === jobId);
        const modal = document.getElementById('gcodeSelectionModal');

        // Modal öffnen falls nötig
        if (modal.style.display === 'none' || !modal.style.display) {
            if (job) document.getElementById('gcodeJobName').textContent = job.name;
            gcodeRefreshJobId = jobId;
            modal.style.display = 'flex';
        }

        // Verbindungsstatus im Header
        _updateGcodeConnStatus(job, result.connection_method);

        // Bei needs_manual: Direkt zur manuellen Eingabe (kein Fehler-Panel)
        if (result.needs_manual) {
            const filePanel2 = document.getElementById('gcodeFilePanel');
            const previewPanel2 = document.getElementById('gcodePreviewPanel');
            const formActions2 = document.getElementById('gcodeFormActions');
            const errPanel2 = document.getElementById('gcodeErrorPanel');
            const previewBox2 = document.getElementById('gcodeWeightPreview');
            if (filePanel2) filePanel2.style.display = 'none';
            if (errPanel2) errPanel2.style.display = 'none';
            if (previewPanel2) previewPanel2.style.display = '';
            if (previewBox2) previewBox2.style.display = 'block';
            if (formActions2) formActions2.style.display = 'flex';
            // Hinweis-Text setzen
            const recEl2 = document.getElementById('gcodePreviewRecommendation');
            if (recEl2) {
                const ftpsHint = result.error_detail ? `\n(${result.error_detail})` : '';
                recEl2.textContent = `⚠️ ${result.error_message || 'Verbindung fehlgeschlagen'} — Gewicht manuell eingeben.${ftpsHint}`;
                recEl2.style.cssText = 'background:rgba(231,76,60,0.08); border:1px solid rgba(231,76,60,0.25); border-radius:6px; padding:9px 13px; font-size:12px; color:#e77;';
            }
            const infoTitle2 = document.getElementById('gcodeInfoTitle');
            if (infoTitle2) infoTitle2.textContent = `✏️ Manuell eingeben — ${job?.name || ''}`;
            const weightInput2 = document.getElementById('gcodePreviewWeight');
            if (weightInput2) { weightInput2.value = ''; setTimeout(() => weightInput2.focus(), 100); }
            showGcodeLoading(false);
            return;
        }

        // Fehler-Panel anzeigen, andere Panels ausblenden
        const errPanel = document.getElementById('gcodeErrorPanel');
        const filePanel = document.getElementById('gcodeFilePanel');
        const previewPanel = document.getElementById('gcodePreviewPanel');
        const formActions = document.getElementById('gcodeFormActions');
        const previewBox = document.getElementById('gcodeWeightPreview');
        if (filePanel) filePanel.style.display = 'none';
        if (previewPanel) previewPanel.style.display = 'none';
        if (formActions) formActions.style.display = 'none';
        if (previewBox) previewBox.style.display = 'none';
        if (errPanel) errPanel.style.display = 'block';

        const titleEl = document.getElementById('gcodeErrorTitle');
        const detailEl = document.getElementById('gcodeErrorDetail');
        if (titleEl) titleEl.textContent = result.error_message || 'Verbindung fehlgeschlagen';
        if (detailEl) detailEl.textContent = result.error_detail || '';

        // Info-Box aktualisieren
        const infoTitle = document.getElementById('gcodeInfoTitle');
        if (infoTitle) infoTitle.textContent = `❌ Verbindungsfehler`;

        showGcodeLoading(false);
    }

    // Erneut versuchen (Retry-Button im Fehler-Panel)
    window.retryGcodeConnection = function() {
        if (gcodeRefreshJobId) {
            showGcodeLoading(true);
            const errPanel = document.getElementById('gcodeErrorPanel');
            const filePanel = document.getElementById('gcodeFilePanel');
            if (errPanel) errPanel.style.display = 'none';
            if (filePanel) filePanel.style.display = '';
            window.refreshWeightFromGcode(gcodeRefreshJobId);
        }
    }

    // Manuell eingeben (Fehler-Panel → rechtes Panel zeigen)
    window.gcodeShowManualEntry = function() {
        // Placeholder setzen damit confirmGcodeSelection nicht an !selectedFile scheitert
        const currentJobId = gcodeRefreshJobId || (gcodeConfirmData && gcodeConfirmData.jobId);
        if (currentJobId) {
            gcodeConfirmData = { ...(gcodeConfirmData || {}), jobId: currentJobId, filename: 'manual_entry' };
            const selectEl = document.getElementById('gcodeFileSelect');
            if (selectEl) selectEl.value = 'manual_entry';
        }
        const errPanel = document.getElementById('gcodeErrorPanel');
        const previewBox = document.getElementById('gcodeWeightPreview');
        const previewPanel = document.getElementById('gcodePreviewPanel');
        const formActions = document.getElementById('gcodeFormActions');
        if (errPanel) errPanel.style.display = 'none';
        if (previewPanel) previewPanel.style.display = '';
        if (previewBox) previewBox.style.display = 'block';
        if (formActions) formActions.style.display = 'flex';
        const recEl = document.getElementById('gcodePreviewRecommendation');
        if (recEl) {
            recEl.textContent = 'Gewicht aus dem Slicer ablesen und manuell eingeben.';
            recEl.style.cssText = 'background:rgba(255,255,255,0.05); border:1px solid rgba(255,255,255,0.12); border-radius:6px; padding:9px 13px; font-size:13px; color:var(--text-dim);';
        }
        const weightInput = document.getElementById('gcodePreviewWeight');
        if (weightInput) { weightInput.value = ''; weightInput.placeholder = 'Gramm eingeben...'; weightInput.focus(); }
    }

    window.closeGcodeSelectionModal = function() {
        _weightLoadAbortFlag = true;  // Hintergrundlader stoppen
        document.getElementById('gcodeSelectionModal').style.display = 'none';
        // Inline-Preview zurücksetzen
        const preview = document.getElementById('gcodeWeightPreview');
        if (preview) preview.style.display = 'none';
        const btn = document.getElementById('gcodeConfirmBtn');
        if (btn) btn.textContent = '✓ Gewicht laden';
        // Fehler-Panel zurücksetzen, alle Panels wieder anzeigen
        const errPanel = document.getElementById('gcodeErrorPanel');
        const filePanel = document.getElementById('gcodeFilePanel');
        const previewPanel = document.getElementById('gcodePreviewPanel');
        const formActions2 = document.getElementById('gcodeFormActions');
        if (errPanel) errPanel.style.display = 'none';
        if (filePanel) filePanel.style.display = '';
        if (previewPanel) previewPanel.style.display = '';
        if (formActions2) formActions2.style.display = 'flex';
        // Verbindungsstatus leeren
        const connStatus = document.getElementById('gcodeConnStatus');
        if (connStatus) connStatus.textContent = '';
        gcodeConfirmData = null;
        gcodeRefreshJobId = null;
        gcodeSelectionFiles = [];
    }

    // -----------------------------------------------------------------------
    // Gewicht-Hintergrundlader: lädt alle Gewichte sofort nach Modal-Öffnung
    // -----------------------------------------------------------------------
    let _weightLoadAbortFlag = false;

    async function _loadAllWeightsOnOpen(jobId, fileList) {
        _weightLoadAbortFlag = false;
        for (let idx = 0; idx < fileList.length; idx++) {
            if (_weightLoadAbortFlag) break;
            const fileInfo = fileList[idx];
            const cellId = 'gcode-wt-' + idx;

            // Bereits bekannt → sofort anzeigen
            if (fileInfo.weight_g && Number(fileInfo.weight_g) > 0) {
                const cell = document.getElementById(cellId);
                if (cell) {
                    cell.textContent = Number(fileInfo.weight_g).toFixed(1) + ' g';
                    cell.classList.add('loaded');
                    cell.classList.remove('na');
                    cell.style.color = '';
                }
                continue;
            }

            // Modal noch offen?
            const modal = document.getElementById('gcodeSelectionModal');
            if (!modal || modal.style.display === 'none') break;

            const cell = document.getElementById(cellId);
            if (!cell) continue;
            cell.textContent = '⏳';
            cell.classList.remove('loaded', 'na');
            cell.style.color = '';

            try {
                const url = `/api/jobs/${jobId}/refresh-weight-gcode?gcode_filename=${encodeURIComponent(fileInfo.name)}&dry_run=true`;
                const resp = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
                const result = await resp.json();

                if (_weightLoadAbortFlag) break;
                const c = document.getElementById(cellId);
                if (!c) continue;

                if (result.needs_confirmation && result.weight > 0) {
                    const w = parseFloat(result.weight);
                    c.textContent = w.toFixed(1) + ' g';
                    c.classList.add('loaded');
                    c.classList.remove('na');
                    c.style.color = '';
                    // In-Memory aktualisieren damit Click sofort Gewicht kennt
                    fileInfo.weight_g = w;
                    const fi = gcodeSelectionFiles.find(f => f.name === fileInfo.name);
                    if (fi) fi.weight_g = w;
                } else {
                    c.textContent = 'N/A';
                    c.classList.add('na');
                    c.classList.remove('loaded');
                }
            } catch (e) {
                const c = document.getElementById(cellId);
                if (c) {
                    c.textContent = 'N/A';
                    c.classList.add('na');
                    c.classList.remove('loaded');
                }
            }
        }
    }

    // -----------------------------------------------------------------------
    // Hilfsfunktion: FTP-Datum formatieren ("Mar 15 10:30" → "15.03. 10:30")
    // -----------------------------------------------------------------------
    function _formatFtpDate(str) {
        if (!str || str === '—') return '—';
        const months = { Jan:'01',Feb:'02',Mar:'03',Apr:'04',May:'05',Jun:'06',
                         Jul:'07',Aug:'08',Sep:'09',Oct:'10',Nov:'11',Dec:'12' };
        const parts = str.trim().split(/\s+/);
        if (parts.length < 3) return str;
        const mon = months[parts[0]] || parts[0];
        const day = parts[1].padStart(2, '0');
        const yearOrTime = parts[2];
        if (yearOrTime.includes(':')) {
            // Aktuelles Jahr mit Uhrzeit → "15.03. 10:30"
            return `${day}.${mon}. ${yearOrTime}`;
        } else {
            // Älteres Datum mit Jahr → "15.03.26"
            const yr = yearOrTime.slice(-2);
            return `${day}.${mon}.${yr}`;
        }
    }

    window.confirmGcodeSelection = async function() {
        const select = document.getElementById('gcodeFileSelect');
        const selectedFile = select.value;

        if (!selectedFile) {
            alert('Bitte wähle eine G-Code Datei aus');
            return;
        }

        // Wenn Inline-Vorschau aktiv ist (fehlgeschlagener Job mit bestätigtem Gewicht)
        const previewBox = document.getElementById('gcodeWeightPreview');
        if (previewBox && previewBox.style.display !== 'none' && gcodeConfirmData) {
            const weightInput = document.getElementById('gcodePreviewWeight');
            const confirmedWeight = parseFloat(weightInput?.value);
            if (isNaN(confirmedWeight) || confirmedWeight <= 0) {
                alert('Bitte ein gültiges Gewicht eingeben (> 0)');
                return;
            }
            window.closeGcodeSelectionModal();
            try {
                let url = `/api/jobs/${gcodeConfirmData.jobId}/refresh-weight-gcode`
                    + `?gcode_filename=${encodeURIComponent(selectedFile)}`
                    + `&confirmed_weight=${confirmedWeight}`;
                if (gcodeConfirmData.filamentWeightsG) {
                    url += `&filament_weights_json=${encodeURIComponent(JSON.stringify(gcodeConfirmData.filamentWeightsG))}`;
                }
                const resp = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
                const result = await resp.json();
                if (result.success) {
                    showNotification(`✅ ${result.message} (${result.weight_diff > 0 ? '+' : ''}${result.weight_diff.toFixed(1)}g)`, 'success');
                    await loadJobs();
                    await loadStats();
                } else {
                    alert(`❌ ${result.error || 'Fehler beim Speichern'}`);
                }
            } catch (e) {
                alert('Fehler beim Speichern des Gewichts');
            }
            return;
        }

        // Normaler Pfad: erneuter API-Call mit gewähltem Filename
        window.refreshWeightFromGcode(gcodeRefreshJobId, selectedFile);
    }

// Lädt Jobs-Liste und erstellt Name→task_id Map für Job-ID-Spalte
async function _loadJobIdMap() {
    try {
        const resp = await fetch('/api/jobs?limit=500');
        if (!resp.ok) return new Map();
        const data = await resp.json();
        const jobList = Array.isArray(data) ? data : (data.jobs || data.items || []);
        const map = new Map();
        for (const job of jobList) {
            const label = job.task_id || (job.id ? job.id.slice(0, 8) : null);
            if (!label) continue;
            // Key: Job-Name ohne Datei-Extension, lowercase für fuzzy Match
            const key = (job.name || '').toLowerCase()
                .replace(/\.gcode\.3mf$/i, '').replace(/\.3mf$/i, '').replace(/\.gcode$/i, '').trim();
            if (key) map.set(key, label);
        }
        return map;
    } catch (_) {
        return new Map();
    }
}

// Befüllt Job-ID-Zellen nach dem Render mit gematchten task_ids
function _updateJobIdCells(map, files) {
    const cells = document.querySelectorAll('#gcodeFilesBody .gcode-jobid-cell');
    cells.forEach((cell, idx) => {
        const f = files && files[idx];
        if (!f) return;
        const key = (f.name || '').toLowerCase()
            .replace(/\.gcode\.3mf$/i, '').replace(/\.3mf$/i, '').replace(/\.gcode$/i, '').trim();
        const taskId = map.get(key);
        if (taskId) {
            cell.textContent = taskId;
            cell.style.color = 'var(--accent, #f0a500)';
            cell.title = taskId;
        } else {
            cell.textContent = '—';
        }
    });
}

// Zeigt per-Spool Gewicht-Breakdown (Multicolor, bis zu 16 Filamente)
function _renderSpoolBreakdown(weights) {
    const el = document.getElementById('gcodeSpoolBreakdown');
    if (!el) return;
    // DOM leeren
    while (el.firstChild) el.removeChild(el.firstChild);
    // Nur bei 2+ genutzten Filamenten anzeigen
    const active = (weights || []).filter(w => w > 0);
    if (!weights || active.length < 2) {
        el.style.display = 'none';
        return;
    }
    const total = weights.reduce((a, b) => a + b, 0);
    weights.forEach((w, i) => {
        if (w <= 0) return; // Ungenutzte Slots überspringen
        const row = document.createElement('div');
        row.style.cssText = 'display:flex; justify-content:space-between; margin-bottom:2px;';
        const lbl = document.createElement('span');
        lbl.textContent = `Filament ${i + 1}`;
        const val = document.createElement('strong');
        val.textContent = `${w.toFixed(2)} g`;
        row.appendChild(lbl);
        row.appendChild(val);
        el.appendChild(row);
    });
    // Trennlinie + Gesamtsumme
    const sep = document.createElement('div');
    sep.style.cssText = 'border-top:1px solid rgba(255,255,255,0.15); margin-top:4px; padding-top:4px; display:flex; justify-content:space-between;';
    const totLbl = document.createElement('span');
    totLbl.textContent = 'Gesamt';
    const totVal = document.createElement('strong');
    totVal.style.color = 'var(--text)';
    totVal.textContent = `${total.toFixed(2)} g`;
    sep.appendChild(totLbl);
    sep.appendChild(totVal);
    el.appendChild(sep);
    el.style.display = 'block';
}

function renderGcodeOptions(fileList, skipSort = false) {
    const tbody = document.getElementById('gcodeFilesBody');
    if (!tbody) return;
    tbody.innerHTML = '';

    if (!fileList || fileList.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="padding: 20px; text-align: center; color: var(--text-dim);">Keine Dateien gefunden</td></tr>';
        return;
    }

    // Konvertiere alle zu Object-Format
    let files = fileList.map(f => {
        if (typeof f === 'string') {
            return { name: f, mtime_str: '', extension: f.split('.').pop().toLowerCase() };
        }
        return f;
    });

    // Sortierung anwenden (außer wenn skipSort=true)
    if (!skipSort) {
        files = applySortToGcodeFiles(files);
    }

    // Rendere Tabelle
    files.forEach((fileInfo, idx) => {
        const rowId = 'gcode-row-' + idx;
        const weightCellId = 'gcode-wt-' + idx;

        const row = document.createElement('tr');
        row.id = rowId;
        row.style.borderBottom = '1px solid rgba(255,255,255,0.08)';
        row.style.cursor = 'pointer';
        row.style.transition = 'background 0.1s';

        // Auto-gematchte Datei leicht hervorheben
        if (fileInfo._auto_matched) {
            row.style.background = 'rgba(255,165,0,0.10)';
            row.title = 'Automatisch gefunden';
        }

        row.onclick = () => {
            // Deselect alle Zeilen
            document.querySelectorAll('#gcodeFilesBody tr').forEach(r => {
                if (r._isAutoMatch) {
                    r.style.background = 'rgba(255,165,0,0.10)';
                } else {
                    r.style.background = '';
                }
            });
            // Diese Zeile selektieren
            row.style.background = 'rgba(255, 165, 0, 0.28)';
            document.getElementById('gcodeFileSelect').value = fileInfo.name;

            const currentJobId = gcodeRefreshJobId || (gcodeConfirmData && gcodeConfirmData.jobId);
            if (!currentJobId) return;

            const wCell = document.getElementById(weightCellId);
            // Gewicht schon geladen → direkt in Preview übernehmen
            if (wCell && wCell.classList.contains('loaded')) {
                const knownW = fileInfo.weight_g && fileInfo.weight_g > 0
                    ? fileInfo.weight_g
                    : parseFloat(wCell.textContent);
                _reloadPreviewForFile(currentJobId, fileInfo.name, knownW || null);
            } else {
                // Noch nicht geladen oder N/A → API-Call auslösen
                if (wCell && !wCell.classList.contains('na')) {
                    wCell.textContent = '⏳';
                }
                _reloadPreviewForFile(currentJobId, fileInfo.name, null);
            }
        };

        row.onmouseover = () => {
            if (document.getElementById('gcodeFileSelect').value !== fileInfo.name)
                row.style.background = 'rgba(255,255,255,0.05)';
        };
        row.onmouseout = () => {
            const isSelected = document.getElementById('gcodeFileSelect').value === fileInfo.name;
            if (!isSelected) {
                row.style.background = fileInfo._auto_matched ? 'rgba(255,165,0,0.10)' : '';
            }
        };

        row._isAutoMatch = !!fileInfo._auto_matched;

        // --- Typ-Badge (1. Spalte) ---
        const typeCell = document.createElement('td');
        typeCell.style.cssText = 'padding: 6px 4px 6px 8px; width: 44px; text-align: center; white-space: nowrap;';
        const ext = (fileInfo.extension || (fileInfo.name || '').split('.').pop() || '').toLowerCase();
        const badge = document.createElement('span');
        badge.className = 'gcode-badge';
        if (ext === '3mf') {
            badge.textContent = '3mf';
            badge.classList.add('gcode-badge-3mf');
        } else if (ext === 'gcode' || ext === 'gc') {
            badge.textContent = 'gc';
            badge.classList.add('gcode-badge-gc');
        } else {
            badge.textContent = ext || '?';
            badge.classList.add('gcode-badge-other');
        }
        typeCell.appendChild(badge);

        // --- Name (2. Spalte) ---
        const nameCell = document.createElement('td');
        nameCell.style.cssText = 'padding: 7px 10px; overflow: hidden; text-overflow: ellipsis;';
        const filenameSpan = document.createElement('span');
        filenameSpan.style.cssText = 'white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block; max-width: 100%;';
        filenameSpan.textContent = fileInfo.name;
        nameCell.appendChild(filenameSpan);

        // --- Gewicht-Zelle (3. Spalte) ---
        const weightCell = document.createElement('td');
        weightCell.id = weightCellId;
        weightCell.className = 'gcode-weight-cell';
        if (fileInfo.weight_g && Number(fileInfo.weight_g) > 0) {
            weightCell.textContent = Number(fileInfo.weight_g).toFixed(1) + ' g';
            weightCell.classList.add('loaded');
        } else {
            // Wird durch Hintergrundlader befüllt
            weightCell.textContent = '⏳';
        }

        // --- Datum (4. Spalte) ---
        const dateCell = document.createElement('td');
        dateCell.style.cssText = 'padding:6px 8px; text-align:right; width:110px; color:var(--text-dim); font-size:11px; white-space:nowrap;';
        const dtStr = fileInfo.mtime_str || '—';
        dateCell.textContent = _formatFtpDate(dtStr);

        // --- Job ID (3. Spalte, zwischen Name und Gewicht) ---
        const jobIdCell = document.createElement('td');
        jobIdCell.className = 'gcode-jobid-cell';
        jobIdCell.style.cssText = 'padding:6px 8px; width:80px; font-size:10px; color:var(--text-dim); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;';
        jobIdCell.textContent = '…';

        row.appendChild(typeCell);
        row.appendChild(nameCell);
        row.appendChild(jobIdCell);
        row.appendChild(weightCell);
        row.appendChild(dateCell);
        tbody.appendChild(row);
    });
}

function filterGcodeOptions(query) {
    const q = (query || '').toLowerCase();
    if (!q) {
        // Kein Filter: Zeige alle Original-Dateien
        gcodeSelectionFiles = [...gcodeOriginalFiles];
        renderGcodeOptions(gcodeSelectionFiles);
        return;
    }
    // Filtere aus der ORIGINAL-Liste (nicht aus der aktuellen gefilterten)
    const filtered = gcodeOriginalFiles.filter(fileInfo => {
        const filename = typeof fileInfo === 'string' ? fileInfo : fileInfo.name;
        return filename.toLowerCase().includes(q);
    });
    gcodeSelectionFiles = filtered;
    renderGcodeOptions(filtered);
}

function applySortToGcodeFiles(files) {
    const multiplier = gcodeSortDirection === 'asc' ? 1 : -1;

    return [...files].sort((a, b) => {
        if (gcodeSortField === 'name') {
            const aName = (typeof a === 'string' ? a : a.name).toLowerCase();
            const bName = (typeof b === 'string' ? b : b.name).toLowerCase();
            return multiplier * aName.localeCompare(bName);
        } else {
            // date
            const aDate = (typeof a === 'object' && a.mtime_str) ? a.mtime_str : '';
            const bDate = (typeof b === 'object' && b.mtime_str) ? b.mtime_str : '';
            return multiplier * aDate.localeCompare(bDate);
        }
    });
}

function updateGcodeSortIndicators() {
    const nameIndicator = document.getElementById('sortIndicatorName');
    const dateIndicator = document.getElementById('sortIndicatorDate');

    if (nameIndicator) nameIndicator.textContent = '';
    if (dateIndicator) dateIndicator.textContent = '';

    if (gcodeSortField === 'name' && nameIndicator) {
        nameIndicator.textContent = gcodeSortDirection === 'asc' ? '▲' : '▼';
    } else if (gcodeSortField === 'date' && dateIndicator) {
        dateIndicator.textContent = gcodeSortDirection === 'asc' ? '▲' : '▼';
    }
}

window.sortGcodeFiles = function(field) {
    // Toggle direction wenn gleiches Feld, sonst auf desc setzen
    if (gcodeSortField === field) {
        gcodeSortDirection = gcodeSortDirection === 'asc' ? 'desc' : 'asc';
    } else {
        gcodeSortField = field;
        gcodeSortDirection = field === 'date' ? 'desc' : 'asc';  // Datum: neueste zuerst, Name: A-Z
    }

    updateGcodeSortIndicators();
    renderGcodeOptions(gcodeSelectionFiles);
};


// Close modal on ESC or background click
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeAddModal();
        closeDeleteModal();
        closeManualUsageModal();
        closeGcodeSelectionModal();
        if (typeof closeCloudJobsModal === 'function') closeCloudJobsModal();
        if (typeof closeCloudJobImportModal === 'function') closeCloudJobImportModal();
    }
});

document.getElementById('jobModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'jobModal') closeAddModal();
});

document.getElementById('deleteModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'deleteModal') closeDeleteModal();
});

document.getElementById('gcodeSelectionModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'gcodeSelectionModal') closeGcodeSelectionModal();
});

document.getElementById('gcodeFileSearch')?.addEventListener('input', (e) => {
    filterGcodeOptions(e.target.value);
});

document.getElementById('manualUsageModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'manualUsageModal') closeManualUsageModal();
});

// =============================================================================
// CLOUD DATA FETCH FOR EXISTING JOB (Multi-Spool Support)
// =============================================================================

let cloudMatchJobId = null;
let cloudFilamentUsage = [];

/**
 * Ruft Cloud-Daten für einen lokalen Job ab und füllt den Manual-Usage-Dialog vor.
 * Unterstützt Multi-Spool (z.B. Multicolor-Drucke).
 */
async function fetchCloudDataForJob(jobId) {
    const job = jobs.find(j => j.id === jobId);
    if (!job) {
        alert('Job nicht gefunden');
        return;
    }

    // Zeige Loading
    showNotification('☁️ Suche Cloud-Daten...', 'info');

    try {
        const response = await fetch(`/api/bambu-cloud/tasks/match/${jobId}`);
        const result = await response.json();

        if (result.status === 'matched') {
            // Cloud-Daten gefunden!
            cloudMatchJobId = jobId;
            cloudFilamentUsage = result.filament_usage || [];

            // Öffne den erweiterten Dialog mit vorausgefüllten Daten
            openCloudUsageModal(job, result);
        } else if (result.status === 'no_match') {
            // Kein Match gefunden
            showNotification(`⚠️ ${result.message}`, 'warning');
            // Öffne normalen Manual Usage Dialog als Fallback
            openManualUsageModal(jobId);
        } else {
            showNotification(`❌ Fehler: ${result.detail || 'Unbekannter Fehler'}`, 'error');
        }
    } catch (error) {
        console.error('Cloud-Fetch Error:', error);
        showNotification('❌ Verbindung zur Cloud fehlgeschlagen', 'error');
    }
}

/**
 * Öffnet den Cloud-Usage-Dialog mit vorausgefüllten Daten (Multi-Spool).
 */
function openCloudUsageModal(job, cloudData) {
    const filamentUsage = cloudData.filament_usage || [];

    // Falls nur eine Spule: Nutze den normalen Dialog mit vorausgefüllten Werten
    if (filamentUsage.length <= 1) {
        openManualUsageModalWithCloudData(job, filamentUsage[0] || null, cloudData.total_weight_g);
        return;
    }

    // Multi-Spool: Zeige erweiterten Dialog
    openMultiSpoolCloudModal(job, cloudData);
}

/**
 * Öffnet den normalen Manual-Usage-Dialog mit Cloud-Daten vorausgefüllt.
 */
function openManualUsageModalWithCloudData(job, filamentData, totalWeight) {
    manualUsageJobId = job.id;

    // Job-Name anzeigen
    document.getElementById('usageJobName').textContent = job.name;

    // Spulen-Dropdown befüllen
    const spoolSelect = document.getElementById('usageSpool');
    spoolSelect.innerHTML = '<option value="">-- Spule wählen --</option>';

    let matchedSpoolId = null;

    spools.forEach(spool => {
        const isAvailable = !spool.is_empty;
        if (isAvailable) {
            const name = spool.label || `AMS Slot ${spool.ams_slot !== undefined ? spool.ams_slot : '?'}`;
            const vendor = spool.vendor || 'Bambu Lab';
            const color = spool.tray_color ? ` (${spool.tray_color.substring(0, 6)})` : '';
            const displayName = `${name} - ${vendor}${color}`;
            spoolSelect.innerHTML += `<option value="${spool.id}">${displayName}</option>`;

            // Versuche Cloud-Spule zu matchen (über Farbe oder AMS-Slot)
            if (filamentData && !matchedSpoolId) {
                const cloudColor = (filamentData.color || '').toLowerCase().replace('ff', '').substring(0, 6);
                const spoolColor = (spool.tray_color || '').toLowerCase().substring(0, 6);

                // Match über Farbe
                if (cloudColor && spoolColor && cloudColor === spoolColor) {
                    matchedSpoolId = spool.id;
                }
                // Match über AMS-Slot
                else if (filamentData.ams_slot !== undefined && spool.ams_slot === filamentData.ams_slot) {
                    matchedSpoolId = spool.id;
                }
            }
        }
    });

    // Spule vorauswählen wenn Match gefunden
    if (matchedSpoolId) {
        spoolSelect.value = matchedSpoolId;
    }

    // Gewicht vorausfüllen
    const weight = filamentData ? filamentData.weight_g : totalWeight;
    document.getElementById('usageGrams').value = weight ? weight.toFixed(2) : '';
    document.getElementById('usageMm').value = '';

    // Modal öffnen
    document.getElementById('manualUsageModal').style.display = 'flex';

    showNotification(`☁️ Cloud-Daten geladen: ${weight ? weight.toFixed(2) + 'g' : 'keine Gewichtsdaten'}`, 'success');
}

/**
 * Öffnet den Multi-Spool Dialog für Multicolor-Drucke.
 */
function openMultiSpoolCloudModal(job, cloudData) {
    const filamentUsage = cloudData.filament_usage || [];

    // Erstelle dynamischen Modal-Inhalt
    let spoolsHtml = '';
    let totalWeight = 0;

    filamentUsage.forEach((usage, index) => {
        const colorHex = (usage.color || '').substring(0, 6) || 'CCCCCC';
        const weight = usage.weight_g || 0;
        totalWeight += weight;

        // Finde passende lokale Spule
        let matchedSpoolId = '';
        let matchedSpoolName = `AMS Slot ${usage.ams_slot}`;

        for (const spool of spools) {
            if (spool.is_empty) continue;

            const spoolColor = (spool.tray_color || '').toLowerCase().substring(0, 6);
            const cloudColor = colorHex.toLowerCase();

            // Match über Farbe oder AMS-Slot
            if ((cloudColor && spoolColor && cloudColor === spoolColor) ||
                (spool.ams_slot !== undefined && spool.ams_slot === usage.ams_slot)) {
                matchedSpoolId = spool.id;
                matchedSpoolName = spool.label || `AMS Slot ${spool.ams_slot}`;
                break;
            }
        }

        spoolsHtml += `
            <div class="cloud-spool-item" data-slot="${usage.ams_slot}" style="display: flex; align-items: center; gap: 12px; padding: 12px; background: rgba(0,0,0,0.2); border-radius: 8px; margin-bottom: 8px;">
                <span class="color-preview" style="background: #${colorHex}; width: 24px; height: 24px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.3);"></span>
                <div style="flex: 1;">
                    <select id="cloudSpool_${index}" class="form-control" data-slot="${usage.ams_slot}" style="margin-bottom: 4px;">
                        <option value="">-- Spule wählen --</option>
                        ${spools.filter(s => !s.is_empty).map(s => {
                            const name = s.label || `AMS Slot ${s.ams_slot !== undefined ? s.ams_slot : '?'}`;
                            const vendor = s.vendor || 'Bambu Lab';
                            const color = s.tray_color ? ` (${s.tray_color.substring(0, 6)})` : '';
                            const selected = s.id === matchedSpoolId ? ' selected' : '';
                            return `<option value="${s.id}"${selected}>${name} - ${vendor}${color}</option>`;
                        }).join('')}
                    </select>
                    <small style="color: var(--text-dim);">${usage.filament_type || 'PLA'} | Slot ${usage.ams_slot}</small>
                </div>
                <div style="text-align: right; min-width: 70px;">
                    <input type="number" id="cloudWeight_${index}" class="form-control" value="${weight.toFixed(2)}" step="0.01" min="0" style="width: 80px; text-align: right;">
                    <small style="color: var(--text-dim);">Gramm</small>
                </div>
            </div>
        `;
    });

    // Erstelle Modal falls nicht vorhanden
    let modal = document.getElementById('cloudUsageModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'cloudUsageModal';
        modal.className = 'modal';
        modal.style.display = 'none';
        modal.innerHTML = `
            <div class="modal-content" style="max-width: 500px;">
                <div class="modal-header">
                    <h2>☁️ Cloud-Daten übernehmen</h2>
                    <button class="modal-close" onclick="closeCloudUsageModal()">✕</button>
                </div>
                <div id="cloudUsageContent"></div>
                <div class="form-actions">
                    <button type="button" class="btn btn-primary" onclick="saveCloudUsage()">Speichern</button>
                    <button type="button" class="btn btn-secondary" onclick="closeCloudUsageModal()">Abbrechen</button>
                </div>
            </div>
        `;
        document.body.appendChild(modal);

        // Click outside to close
        modal.addEventListener('click', (e) => {
            if (e.target.id === 'cloudUsageModal') closeCloudUsageModal();
        });
    }

    // Fülle Modal-Inhalt
    document.getElementById('cloudUsageContent').innerHTML = `
        <div class="info-box" style="margin-bottom: 16px;">
            <strong>✅ Cloud-Match gefunden!</strong><br>
            Job: <span style="font-weight: bold;">${job.name}</span><br>
            <small>Gesamtverbrauch: ${totalWeight.toFixed(2)}g | ${filamentUsage.length} Spule(n)</small>
        </div>
        <div style="margin-bottom: 16px;">
            <label style="font-weight: bold; margin-bottom: 8px; display: block;">Verwendete Spulen:</label>
            ${spoolsHtml}
        </div>
    `;

    // Speichere Job-ID und Anzahl der Spulen
    modal.dataset.jobId = job.id;
    modal.dataset.spoolCount = filamentUsage.length;

    // Zeige Modal
    modal.style.display = 'flex';
}

function closeCloudUsageModal() {
    const modal = document.getElementById('cloudUsageModal');
    if (modal) {
        modal.style.display = 'none';
    }
}

async function saveCloudUsage() {
    const modal = document.getElementById('cloudUsageModal');
    if (!modal) return;

    const jobId = modal.dataset.jobId;
    const spoolCount = parseInt(modal.dataset.spoolCount) || 0;

    // Sammle alle Spulen-Daten mit Slot-Info
    const usages = [];
    for (let i = 0; i < spoolCount; i++) {
        const selectElement = document.getElementById(`cloudSpool_${i}`);
        const spoolId = selectElement?.value;
        const weight = parseFloat(document.getElementById(`cloudWeight_${i}`)?.value) || 0;
        const slot = parseInt(selectElement?.dataset?.slot) || i;

        if (spoolId && weight > 0) {
            usages.push({ spool_id: spoolId, used_g: weight, slot: slot });
        }
    }

    if (usages.length === 0) {
        alert('Bitte wähle mindestens eine Spule aus!');
        return;
    }

    // Nutze den neuen cloud-usage Endpoint für Multi-Spool
    try {
        const response = await fetch(`/api/jobs/${jobId}/cloud-usage`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                usages: usages,
                source: 'bambu_cloud'
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Speichern fehlgeschlagen');
        }

        const result = await response.json();

        closeCloudUsageModal();
        clearFilters();
        await loadJobs();
        await loadStats();
        await loadSpools();
        showNotification(`✅ ${result.usages_created} Spulen-Verbrauch (${result.total_weight_g.toFixed(2)}g) erfolgreich nachgetragen!`, 'success');
    } catch (error) {
        console.error('Save Error:', error);
        alert(`Fehler: ${error.message}`);
    }
}


// =============================================================================
// CLOUD JOBS IMPORT
// =============================================================================

let cloudJobs = [];
let selectedCloudJob = null;

// Open Cloud Jobs Modal
function openCloudJobsModal() {
    document.getElementById('cloudJobsModal').style.display = 'flex';
    loadCloudJobs();
}

// Close Cloud Jobs Modal
function closeCloudJobsModal() {
    document.getElementById('cloudJobsModal').style.display = 'none';
}

// Load Cloud Jobs from API
async function loadCloudJobs() {
    const loading = document.getElementById('cloudJobsLoading');
    const error = document.getElementById('cloudJobsError');
    const list = document.getElementById('cloudJobsList');

    loading.style.display = 'block';
    error.style.display = 'none';
    list.style.display = 'none';

    try {
        const res = await fetch('/api/bambu-cloud/tasks?limit=50');

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'API-Fehler');
        }

        const data = await res.json();
        cloudJobs = data.tasks || [];

        // Prüfe für jeden Cloud-Job ob ein lokaler Job existiert
        cloudJobs.forEach(cloudJob => {
            const matchingLocalJob = findMatchingLocalJob(cloudJob);
            cloudJob._localMatch = matchingLocalJob;
        });

        // Drucker-Filter befüllen
        const printerFilter = document.getElementById('cloudJobPrinterFilter');
        const uniquePrinters = [...new Set(cloudJobs.map(j => j.device_name || j.device_id).filter(Boolean))];
        printerFilter.innerHTML = '<option value="">Alle Drucker</option>';
        uniquePrinters.forEach(p => {
            printerFilter.innerHTML += `<option value="${p}">${p}</option>`;
        });

        renderCloudJobs(cloudJobs);

        loading.style.display = 'none';
        list.style.display = 'block';

    } catch (e) {
        console.error('Cloud Jobs Error:', e);
        loading.style.display = 'none';
        error.style.display = 'block';
        document.getElementById('cloudJobsErrorText').textContent = e.message || 'Fehler beim Laden';
    }
}

/**
 * Findet einen lokalen Job der zum Cloud-Job passt.
 * Matching über: Name (ähnlich) + Drucker + Datum (±24h)
 */
function findMatchingLocalJob(cloudJob) {
    const cloudTitle = (cloudJob.title || '').toLowerCase();
    const cloudDevice = (cloudJob.device_name || cloudJob.device_id || '').toLowerCase();
    const cloudStart = cloudJob.start_time ? new Date(cloudJob.start_time) : null;

    for (const localJob of jobs) {
        const localName = (localJob.name || '').toLowerCase();
        const localPrinter = printers.find(p => p.id === localJob.printer_id);
        const localPrinterName = (localPrinter?.name || '').toLowerCase();
        const localStart = localJob.started_at ? new Date(localJob.started_at) : null;

        // 1. Name-Match (gleich oder ähnlich)
        const nameMatch = cloudTitle === localName ||
                         cloudTitle.includes(localName) ||
                         localName.includes(cloudTitle);

        // 2. Drucker-Match
        const printerMatch = localPrinterName.includes(cloudDevice) ||
                            cloudDevice.includes(localPrinterName);

        // 3. Zeit-Match (±24h)
        let timeMatch = false;
        if (cloudStart && localStart) {
            const timeDiff = Math.abs(cloudStart - localStart) / 1000;
            timeMatch = timeDiff < 86400; // 24 Stunden
        }

        // Mindestens Name + (Drucker ODER Zeit) müssen matchen
        if (nameMatch && (printerMatch || timeMatch)) {
            return localJob;
        }
    }

    return null;
}

// Render Cloud Jobs Table
function renderCloudJobs(jobsToRender) {
    const tbody = document.getElementById('cloudJobsTableBody');

    if (jobsToRender.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" style="text-align: center; padding: 40px; color: var(--text-dim);">
                    Keine Cloud-Jobs gefunden
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = jobsToRender.map(job => {
        const statusColors = {
            'finished': '#2ecc71',
            'failed': '#e74c3c',
            'running': '#3498db',
            'pending': '#f39c12',
            'cancelled': '#95a5a6'
        };
        const statusColor = statusColors[job.status] || '#95a5a6';
        const statusText = {
            'finished': '✅ Fertig',
            'failed': '❌ Fehlgeschlagen',
            'running': '🔄 Läuft',
            'pending': '⏳ Wartend',
            'cancelled': '🚫 Abgebrochen'
        }[job.status] || job.status;

        const date = job.start_time ? new Date(job.start_time).toLocaleDateString('de-DE') : '-';
        const weight = job.weight_g ? `${job.weight_g.toFixed(1)}g` : '-';
        const duration = job.cost_time_formatted || '-';

        // Prüfe ob lokaler Job existiert
        const localMatch = job._localMatch;
        const hasLocalMatch = !!localMatch;
        const localNeedsData = hasLocalMatch && (!localMatch.filament_used_g || localMatch.filament_used_g === 0);

        // Button-Logik
        let actionButton = '';
        if (hasLocalMatch && localNeedsData) {
            // Job existiert aber hat keinen Verbrauch → Daten ergänzen
            actionButton = `
                <button class="btn btn-info" style="padding: 6px 12px; font-size: 12px;"
                        onclick="supplementCloudData('${job.id}', '${localMatch.id}')">
                    ☁️ Ergänzen
                </button>
            `;
        } else if (hasLocalMatch) {
            // Job existiert und hat Verbrauch → Bereits importiert
            actionButton = `
                <span style="color: #2ecc71; font-size: 12px;">✅ Vorhanden</span>
            `;
        } else {
            // Neuer Job → Importieren
            actionButton = `
                <button class="btn btn-primary" style="padding: 6px 12px; font-size: 12px;"
                        onclick="openCloudJobImportModal('${job.id}')">
                    📥 Importieren
                </button>
            `;
        }

        return `
            <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                <td style="padding: 12px;">
                    <div style="font-weight: 500;">${job.title || 'Unbenannt'}</div>
                    <div style="font-size: 11px; color: var(--text-dim);">ID: ${job.id}</div>
                </td>
                <td style="padding: 12px; color: var(--text-dim);">${job.device_name || job.device_id || '-'}</td>
                <td style="padding: 12px; text-align: center; font-weight: 600; color: #2ecc71;">${weight}</td>
                <td style="padding: 12px; text-align: center;">${duration}</td>
                <td style="padding: 12px; text-align: center;">
                    <span style="color: ${statusColor}; font-size: 12px;">${statusText}</span>
                </td>
                <td style="padding: 12px; text-align: center; font-size: 12px; color: var(--text-dim);">${date}</td>
                <td style="padding: 12px; text-align: center;">
                    ${actionButton}
                </td>
            </tr>
        `;
    }).join('');
}

// Filter Cloud Jobs
function filterCloudJobs() {
    const search = document.getElementById('cloudJobSearch').value.toLowerCase();
    const printer = document.getElementById('cloudJobPrinterFilter').value;

    const filtered = cloudJobs.filter(job => {
        const matchesSearch = !search ||
            (job.title || '').toLowerCase().includes(search) ||
            (job.device_name || '').toLowerCase().includes(search);
        const matchesPrinter = !printer ||
            job.device_name === printer ||
            job.device_id === printer;
        return matchesSearch && matchesPrinter;
    });

    renderCloudJobs(filtered);
}

// Open Import Detail Modal
function openCloudJobImportModal(jobId) {
    selectedCloudJob = cloudJobs.find(j => j.id === jobId);
    if (!selectedCloudJob) {
        alert('Job nicht gefunden');
        return;
    }

    // Job-Infos anzeigen
    document.getElementById('importJobTitle').textContent = selectedCloudJob.title || 'Unbenannt';
    document.getElementById('importJobPrinter').textContent = selectedCloudJob.device_name || selectedCloudJob.device_id || '-';
    document.getElementById('importJobDate').textContent = selectedCloudJob.start_time
        ? new Date(selectedCloudJob.start_time).toLocaleString('de-DE')
        : '-';
    document.getElementById('importJobDuration').textContent = selectedCloudJob.cost_time_formatted || '-';

    const statusText = {
        'finished': '✅ Fertig',
        'failed': '❌ Fehlgeschlagen',
        'running': '🔄 Läuft'
    }[selectedCloudJob.status] || selectedCloudJob.status;
    document.getElementById('importJobStatus').textContent = statusText;

    // Filament-Verbrauch
    document.getElementById('importJobWeight').textContent = selectedCloudJob.weight_g?.toFixed(1) || '0';
    document.getElementById('importJobLength').textContent = selectedCloudJob.length_mm
        ? (selectedCloudJob.length_mm / 1000).toFixed(2)
        : '0';

    // Spulen-Dropdown befüllen
    const spoolSelect = document.getElementById('importSpoolSelect');
    spoolSelect.innerHTML = '<option value="">-- Spule wählen --</option>';
    spools.forEach(spool => {
        if (!spool.is_empty) {
            const name = spool.name || spool.label || `#${spool.spool_number || spool.id.substring(0, 6)}`;
            const vendor = spool.vendor || '';
            const color = spool.color || spool.tray_color || '';
            const colorPreview = color ? `<span style="display:inline-block;width:12px;height:12px;background:#${color.replace('#','')};border-radius:2px;margin-right:4px;"></span>` : '';
            const displayName = `${name}${vendor ? ' - ' + vendor : ''}${color ? ' (' + color.substring(0,6) + ')' : ''}`;
            spoolSelect.innerHTML += `<option value="${spool.id}">${displayName}</option>`;
        }
    });

    // Drucker-Dropdown befüllen
    const printerSelect = document.getElementById('importPrinterSelect');
    printerSelect.innerHTML = '<option value="">-- Drucker wählen --</option>';
    printers.forEach(printer => {
        // Versuche Cloud-Drucker zu matchen
        const isMatch = printer.device_id === selectedCloudJob.device_id ||
                       printer.name?.toLowerCase().includes(selectedCloudJob.device_name?.toLowerCase() || '');
        printerSelect.innerHTML += `<option value="${printer.id}" ${isMatch ? 'selected' : ''}>${printer.name}</option>`;
    });

    // Spulen-Suche
    const searchInput = document.getElementById('importSpoolSearch');
    searchInput.value = '';
    searchInput.oninput = () => {
        const search = searchInput.value.toLowerCase();
        const options = spoolSelect.querySelectorAll('option');
        options.forEach(opt => {
            if (opt.value === '') return;
            const text = opt.textContent.toLowerCase();
            opt.style.display = text.includes(search) ? '' : 'none';
        });
    };

    // Modal öffnen
    document.getElementById('cloudJobImportModal').style.display = 'flex';
}

// Close Import Detail Modal
function closeCloudJobImportModal() {
    document.getElementById('cloudJobImportModal').style.display = 'none';
    selectedCloudJob = null;
}

// Confirm Cloud Job Import
async function confirmCloudJobImport() {
    if (!selectedCloudJob) {
        alert('Kein Job ausgewählt');
        return;
    }

    const spoolId = document.getElementById('importSpoolSelect').value;
    const printerId = document.getElementById('importPrinterSelect').value;

    if (!spoolId) {
        alert('Bitte wähle eine Spule aus!');
        return;
    }

    if (!printerId) {
        alert('Bitte wähle einen Drucker aus!');
        return;
    }

    const weightG = selectedCloudJob.weight_g || 0;
    const lengthMm = selectedCloudJob.length_mm || 0;

    try {
        // 1. Job erstellen
        const jobData = {
            name: selectedCloudJob.title || 'Cloud Import',
            printer_id: printerId,
            spool_id: spoolId,
            started_at: selectedCloudJob.start_time || new Date().toISOString(),
            finished_at: selectedCloudJob.end_time || null,
            filament_used_g: weightG,
            filament_used_mm: lengthMm,
            status: selectedCloudJob.status === 'finished' ? 'completed' : 'active',
            source: 'bambu_cloud',
            cloud_task_id: selectedCloudJob.id
        };

        const res = await fetch('/api/jobs/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(jobData)
        });

        if (!res.ok) {
            const err = await res.json().catch(() => ({}));
            throw new Error(err.detail || 'Fehler beim Erstellen des Jobs');
        }

        // 2. Spulen-Gewicht aktualisieren (abziehen)
        if (weightG > 0) {
            const spool = spools.find(s => s.id === spoolId);
            if (spool) {
                const newWeight = Math.max(0, (spool.weight_current || spool.weight_full || 750) - weightG);
                await fetch(`/api/spools/${spoolId}`, {
                    method: 'PATCH',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        weight_current: newWeight,
                        weight_source: 'bambu_cloud_import'
                    })
                });
            }
        }

        showNotification(`Job "${selectedCloudJob.title}" importiert! ${weightG.toFixed(1)}g abgezogen.`, 'success');

        // Modals schließen und Daten neu laden
        closeCloudJobImportModal();
        closeCloudJobsModal();
        await loadJobs();
        await loadSpools();
        await loadStats();

    } catch (e) {
        console.error('Import Error:', e);
        alert('Fehler beim Importieren: ' + e.message);
    }
}

/**
 * Ergänzt einen existierenden lokalen Job mit Cloud-Daten.
 * Überträgt: Filament-Verbrauch (Multi-Spool), Dauer, Start-/Endzeit
 */
async function supplementCloudData(cloudJobId, localJobId) {
    const cloudJob = cloudJobs.find(j => j.id === cloudJobId);
    if (!cloudJob) {
        alert('Cloud-Job nicht gefunden');
        return;
    }

    showNotification('☁️ Übertrage Cloud-Daten...', 'info');

    try {
        // 1. Hole detaillierte Cloud-Daten (mit amsDetailMapping)
        const matchRes = await fetch(`/api/bambu-cloud/tasks/match/${localJobId}`);
        let filamentUsage = [];

        if (matchRes.ok) {
            const matchData = await matchRes.json();
            if (matchData.status === 'matched') {
                filamentUsage = matchData.filament_usage || [];
            }
        }

        // Falls kein Match, nutze Gesamtgewicht
        if (filamentUsage.length === 0 && cloudJob.weight_g > 0) {
            // Versuche erste passende Spule zu finden
            filamentUsage = [{
                spool_id: null, // Muss vom User gewählt werden
                weight_g: cloudJob.weight_g,
                slot: 0
            }];
        }

        // 2. Bereite Daten vor
        const updateData = {
            // Zeiten korrigieren
            started_at: cloudJob.start_time,
            finished_at: cloudJob.end_time,
            // Status
            status: cloudJob.status === 'finished' ? 'completed' : 'active'
        };

        // 3. Job-Zeiten aktualisieren
        const jobRes = await fetch(`/api/jobs/${localJobId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updateData)
        });

        if (!jobRes.ok) {
            throw new Error('Fehler beim Aktualisieren der Job-Daten');
        }

        // 4. Multi-Spool Verbrauch hinzufügen
        if (filamentUsage.length > 0) {
            // Finde passende lokale Spulen
            const usagesWithSpools = filamentUsage.map(usage => {
                let matchedSpoolId = usage.spool_id;

                if (!matchedSpoolId) {
                    // Versuche über Farbe oder Slot zu matchen
                    const colorHex = (usage.color || '').toLowerCase().substring(0, 6);

                    for (const spool of spools) {
                        if (spool.is_empty) continue;
                        const spoolColor = (spool.tray_color || '').toLowerCase().substring(0, 6);

                        if ((colorHex && spoolColor && colorHex === spoolColor) ||
                            (spool.ams_slot !== undefined && spool.ams_slot === usage.ams_slot)) {
                            matchedSpoolId = spool.id;
                            break;
                        }
                    }
                }

                return {
                    spool_id: matchedSpoolId,
                    used_g: usage.weight_g,
                    slot: usage.ams_slot || usage.slot || 0
                };
            }).filter(u => u.spool_id && u.used_g > 0);

            if (usagesWithSpools.length > 0) {
                const usageRes = await fetch(`/api/jobs/${localJobId}/cloud-usage`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        usages: usagesWithSpools,
                        source: 'bambu_cloud'
                    })
                });

                if (!usageRes.ok) {
                    console.warn('Warnung: Verbrauchsdaten konnten nicht gespeichert werden');
                }
            }
        }

        // 5. Erfolg!
        showNotification(`✅ Cloud-Daten übertragen: ${cloudJob.weight_g?.toFixed(1) || 0}g, Dauer: ${cloudJob.cost_time_formatted || '-'}`, 'success');

        // Daten neu laden
        closeCloudJobsModal();
        await loadJobs();
        await loadSpools();
        await loadStats();

    } catch (e) {
        console.error('Supplement Error:', e);
        alert('Fehler: ' + e.message);
    }
}

// Modal Event Listeners
document.getElementById('cloudJobsModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'cloudJobsModal') closeCloudJobsModal();
});

document.getElementById('cloudJobImportModal')?.addEventListener('click', (e) => {
    if (e.target.id === 'cloudJobImportModal') closeCloudJobImportModal();
});
