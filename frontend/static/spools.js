// Spools Management JavaScript - Modern Card Design

let spools = [];
let materials = [];
let currentSpoolId = null;
let deleteTargetId = null;
let viewMode = 'grid'; // 'grid' or 'table'
let selectedMaterial = null;
let pendingAmsAssignmentDetection = null;
const PENDING_AMS_CREATE_STORAGE_KEY = 'pending_manual_ams_create';
const AMS_CREATE_QUERY_FLAG = 'openAmsCreate';

// Material colors for chart
const MATERIAL_COLORS = [
    '#00d4aa', // Primary/Accent
    '#3498db', // Blue
    '#f1c40f', // Yellow
    '#9b59b6', // Purple
    '#e74c3c', // Red
    '#1abc9c', // Teal
    '#e67e22', // Orange
    '#95a5a6', // Gray
];

function toNumber(val) {
    const n = parseFloat(val);
    return isNaN(n) ? null : n;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function normalizeAmsHexColor(val) {
    const raw = String(val || '').replace('#', '').trim();
    if (raw.length >= 6) return `#${raw.substring(0, 6)}`;
    return '#ffffff';
}

function findMaterialForAmsDetection(detection) {
    if (!detection) return null;

    if (detection.material_id) {
        const byId = materials.find(m => m.id === detection.material_id);
        if (byId) return byId;
    }

    const traySubBrands = String(detection.tray_sub_brands || '').trim().toLowerCase();
    const trayType = String(detection.tray_type || '').trim().toLowerCase();
    const vendor = String(detection.vendor || '').trim().toLowerCase();

    return materials.find(m => {
        const name = String(m.name || '').trim().toLowerCase();
        const brand = String(m.brand || '').trim().toLowerCase();
        return (
            (traySubBrands && name === traySubBrands) ||
            (trayType && name === trayType) ||
            (vendor && trayType && brand === vendor && name === trayType)
        );
    }) || null;
}

function clearPendingAmsAssignmentStorage(detection) {
    if (!detection) return;
    try {
        let pending = JSON.parse(localStorage.getItem('pending_spool_assignments') || '[]');
        const key = detection.tray_uuid || detection.tag_uid;
        if (!key) return;
        pending = pending.filter(p => (p.tray_uuid || p.tag_uid) !== key);
        localStorage.setItem('pending_spool_assignments', JSON.stringify(pending));
    } catch (error) {
        console.error('Fehler beim Bereinigen der AMS-Pending-Daten:', error);
    }
}

function persistPendingAmsCreatePrefill(detection) {
    try {
        localStorage.setItem(PENDING_AMS_CREATE_STORAGE_KEY, JSON.stringify(detection || null));
    } catch (error) {
        console.error('Fehler beim Speichern der AMS-Prefill-Daten:', error);
    }
}

function restorePendingAmsCreatePrefill() {
    try {
        const params = new URLSearchParams(window.location.search);
        const shouldOpen = params.get(AMS_CREATE_QUERY_FLAG) === '1' || !!localStorage.getItem(PENDING_AMS_CREATE_STORAGE_KEY);
        if (!shouldOpen) return;

        const raw = localStorage.getItem(PENDING_AMS_CREATE_STORAGE_KEY);
        if (params.has(AMS_CREATE_QUERY_FLAG)) {
            params.delete(AMS_CREATE_QUERY_FLAG);
            const nextUrl = `${window.location.pathname}${params.toString() ? '?' + params.toString() : ''}${window.location.hash || ''}`;
            window.history.replaceState({}, '', nextUrl);
        }
        if (!raw) {
            openAddModal();
            return;
        }
        localStorage.removeItem(PENDING_AMS_CREATE_STORAGE_KEY);
        const detection = JSON.parse(raw);
        if (detection) {
            openAddModalFromAmsDetection(detection);
        }
    } catch (error) {
        console.error('Fehler beim Wiederherstellen der AMS-Prefill-Daten:', error);
        localStorage.removeItem(PENDING_AMS_CREATE_STORAGE_KEY);
    }
}

// Farbverlauf für Progress: Grün (100%) -> Gelb (50%) -> Rot (0%)
function getProgressColor(percentage) {
    // Clamp zwischen 0 und 100
    const p = Math.min(100, Math.max(0, percentage));

    let r, g, b;

    if (p >= 50) {
        // Grün zu Gelb (50-100%)
        const ratio = (p - 50) / 50;
        r = Math.round(255 * (1 - ratio)); // 255 -> 0
        g = 200; // Grün bleibt
        b = 50;
    } else {
        // Gelb zu Rot (0-50%)
        const ratio = p / 50;
        r = 255; // Rot bleibt
        g = Math.round(200 * ratio); // 200 -> 0
        b = 50;
    }

    return `rgb(${r}, ${g}, ${b})`;
}

// === INIT ===
document.addEventListener('DOMContentLoaded', () => {
    loadData().then(() => {
        restorePendingAmsCreatePrefill();
    });
    setupEventListeners();
});

function setupEventListeners() {
    // Search
    const searchInput = document.getElementById('searchInput');
    const searchColor = document.getElementById('searchColor');
    const filterStatus = document.getElementById('filterStatus');

    if (searchInput) searchInput.addEventListener('input', filterSpools);
    if (searchColor) searchColor.addEventListener('input', filterSpools);
    if (filterStatus) filterStatus.addEventListener('change', filterSpools);

    // Color picker sync
    const colorPicker = document.getElementById('spoolColor');
    const colorHex = document.getElementById('spoolColorHex');

    if (colorPicker && colorHex) {
        colorPicker.addEventListener('input', (e) => {
            colorHex.value = e.target.value;
        });
    }

    // Material selection auto-fill weight_empty
    const materialSelect = document.getElementById('spoolMaterial');
    if (materialSelect) {
        materialSelect.addEventListener('change', (e) => {
            const materialId = e.target.value;
            const material = materials.find(m => m.id === materialId);
            const weightEmptyField = document.getElementById('spoolWeightEmpty');

            if (material && material.spool_weight_empty != null && weightEmptyField) {
                weightEmptyField.value = material.spool_weight_empty;
            }
        });
    }

    // Modal backdrop click
    document.getElementById('spoolModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'spoolModal') closeModal();
    });

    document.getElementById('deleteModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'deleteModal') closeDeleteModal();
    });
}

// === LOAD DATA ===
async function loadData() {
    try {
        await loadMaterials();
        await loadSpools();
    } catch (error) {
        console.error('Fehler beim Laden:', error);
    }
}

async function loadMaterials() {
    try {
        const response = await fetch('/api/materials/');
        materials = await response.json();
        updateMaterialSelect();
    } catch (error) {
        console.error('Fehler beim Laden der Materialien:', error);
    }
}

async function loadSpools() {
    try {
        const response = await fetch('/api/spools/');
        spools = await response.json();

        updateStats();
        updateMaterialChart();
        updateMaterialChips();
        renderSpools(spools);

    } catch (error) {
        console.error('Fehler beim Laden der Spulen:', error);
        showNotification('Fehler beim Laden der Spulen', 'error');
    }
}

function updateMaterialSelect() {
    const select = document.getElementById('spoolMaterial');
    if (!select) return;

    select.innerHTML = '<option value="">-- Material wählen --</option>';
    materials.forEach(m => {
        const option = document.createElement('option');
        option.value = m.id;
        option.textContent = `${m.name}${m.brand ? ' (' + m.brand + ')' : ''}`;
        select.appendChild(option);
    });
}

// === STATS ===
function updateStats() {
    const total = spools.length;
    const totalWeight = spools.reduce((sum, s) => {
        if (s.is_empty) return sum;
        const remaining = toNumber(s.remaining_weight_g);
        return sum + (remaining || 0);
    }, 0);

    // Calculate total value (use NET filament: weight_full - weight_empty)
    const totalValue = spools.reduce((sum, s) => {
        const price = toNumber(s.price);
        const remaining = toNumber(s.remaining_weight_g);
        const full = toNumber(s.weight_full);
        const empty = toNumber(s.weight_empty) || 0;
        const netFilament = (full && !isNaN(full)) ? (full - empty) : null;
        if (price && remaining != null && netFilament && netFilament > 0) {
            return sum + (price * (remaining / netFilament));
        }
        return sum;
    }, 0);

    // Count low stock spools
    const lowStock = spools.filter(s => {
        if (s.is_empty) return false;
        const percentage = toNumber(s.remaining_percent) ?? toNumber(s.remain_percent);
        if (percentage != null) return percentage <= 20;
        const remaining = toNumber(s.remaining_weight_g);
        if (remaining != null) return remaining < 200;
        return false;
    }).length;

    document.getElementById('statTotal').textContent = total;
    document.getElementById('statWeight').textContent = `${(totalWeight / 1000).toFixed(2)} kg`;
    document.getElementById('statValue').textContent = `€${totalValue.toFixed(2)}`;
    document.getElementById('warningCount').textContent = lowStock;
}

// === MATERIAL CHART ===
function updateMaterialChart() {
    const canvas = document.getElementById('materialChart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const materialData = getMaterialDistribution();

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (materialData.length === 0) {
        // Draw empty state
        ctx.beginPath();
        ctx.arc(80, 80, 50, 0, 2 * Math.PI);
        ctx.strokeStyle = 'var(--border)';
        ctx.lineWidth = 20;
        ctx.stroke();
        return;
    }

    // Draw donut chart
    const centerX = 80;
    const centerY = 80;
    const radius = 50;
    const lineWidth = 20;
    let startAngle = -Math.PI / 2;

    const total = materialData.reduce((sum, d) => sum + d.count, 0);

    materialData.forEach((data, index) => {
        const sliceAngle = (data.count / total) * 2 * Math.PI;

        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, startAngle, startAngle + sliceAngle);
        ctx.strokeStyle = MATERIAL_COLORS[index % MATERIAL_COLORS.length];
        ctx.lineWidth = lineWidth;
        ctx.stroke();

        startAngle += sliceAngle;
    });

    // Update legend
    updateMaterialLegend(materialData);
    updateMaterialWeights(materialData);
}

function getMaterialDistribution() {
    const distribution = {};

    spools.forEach(s => {
        const material = materials.find(m => m.id === s.material_id);
        const materialName = material ? material.name : 'Unbekannt';

        if (!distribution[materialName]) {
            distribution[materialName] = { count: 0, weight: 0 };
        }
        distribution[materialName].count++;
        distribution[materialName].weight += toNumber(s.remaining_weight_g) || 0;
    });

    return Object.entries(distribution)
        .map(([name, data]) => ({ name, ...data }))
        .sort((a, b) => b.count - a.count);
}

function updateMaterialLegend(materialData) {
    const legend = document.getElementById('materialLegend');
    if (!legend) return;

    legend.innerHTML = materialData.map((data, index) => `
        <div class="legend-item">
            <span class="legend-dot" style="background: ${MATERIAL_COLORS[index % MATERIAL_COLORS.length]}"></span>
            <span class="legend-label">${data.name}</span>
            <span class="legend-count">(${data.count})</span>
        </div>
    `).join('');
}

function updateMaterialWeights(materialData) {
    const weights = document.getElementById('materialWeights');
    if (!weights) return;

    weights.innerHTML = materialData.map(data => `
        <div class="weight-item">${(data.weight / 1000).toFixed(2)} kg</div>
    `).join('');
}

// === MATERIAL CHIPS ===
function updateMaterialChips() {
    const container = document.getElementById('materialChips');
    if (!container) return;

    const materialCounts = {};
    spools.forEach(s => {
        const material = materials.find(m => m.id === s.material_id);
        const name = material ? material.name : 'Unbekannt';
        materialCounts[name] = (materialCounts[name] || 0) + 1;
    });

    const allChip = `<button class="chip ${selectedMaterial === null ? 'active' : ''}" onclick="setMaterialFilter(null)">Alle (${spools.length})</button>`;

    const materialChips = Object.entries(materialCounts)
        .sort((a, b) => b[1] - a[1])
        .map(([name, count]) => `
            <button class="chip ${selectedMaterial === name ? 'active' : ''}" onclick="setMaterialFilter('${name}')">${name} (${count})</button>
        `).join('');

    container.innerHTML = allChip + materialChips;
}

function setMaterialFilter(materialName) {
    selectedMaterial = materialName;
    updateMaterialChips();
    filterSpools();
}

// === VIEW MODE ===
function setViewMode(mode) {
    viewMode = mode;

    // Update buttons
    document.getElementById('viewCards')?.classList.toggle('active', mode === 'grid');
    document.getElementById('viewTable')?.classList.toggle('active', mode === 'table');

    // Show/hide sections
    document.getElementById('spoolGrid').style.display = mode === 'grid' ? 'grid' : 'none';
    document.getElementById('spoolTableSection').style.display = mode === 'table' ? 'block' : 'none';

    filterSpools();
}

function toggleFilterPanel() {
    const panel = document.getElementById('filterPanel');
    if (panel) {
        panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    }
}

// === RENDER SPOOLS ===
function renderSpools(spoolsToRender) {
    if (viewMode === 'grid') {
        renderSpoolCards(spoolsToRender);
    } else {
        renderSpoolTable(spoolsToRender);
    }
}

function renderSpoolCards(spoolsToRender) {
    const container = document.getElementById('spoolGrid');
    if (!container) return;

    if (spoolsToRender.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="grid-column: 1 / -1;">
                <div class="empty-state-icon">📦</div>
                <h3>Keine Spulen gefunden</h3>
                <p>Fügen Sie Ihre erste Spule hinzu!</p>
                <button class="btn btn-primary" onclick="openAddModal()">
                    Spule hinzufügen
                </button>
            </div>
        `;
        return;
    }

    container.innerHTML = spoolsToRender.map(s => {
        const material = materials.find(m => m.id === s.material_id);
        const materialName = material ? material.name : 'Unbekannt';
        const vendor = material?.brand || s.vendor_id || '';

        // Color
        const color = s.tray_color ? `#${s.tray_color.substring(0, 6)}` : '#808080';

        // Progress - Netto-Filament berechnen (ohne Spulengewicht)
        const remaining = toNumber(s.remaining_weight_g) || 0;
        const weightFull = toNumber(s.weight_full) || 1000;
        const weightEmpty = toNumber(s.weight_empty) || 0;
        const netFilament = weightFull - weightEmpty; // Netto-Filament auf voller Spule
        const percentage = netFilament > 0 ? Math.min(100, Math.max(0, (remaining / netFilament) * 100)) : 0;

        // Farbverlauf basierend auf Prozent (Grün 100% -> Gelb 50% -> Rot 0%)
        const progressColor = getProgressColor(percentage);

        // Is low?
        const isLow = percentage < 25;

        // Value calculation
        const price = toNumber(s.price) || 0;
        const value = price > 0 && netFilament > 0 ? (price * (remaining / netFilament)).toFixed(2) : null;

        // Display name: label ist für manuell vergebene Namen (kein auto "AMS Slot X" mehr)
        const displayName = s.label || '';
        const isLocked = !!s.is_locked;
        const activeJobName = s.active_job_name || 'Aktiver Druck';

        return `
            <div class="spool-card ${isLow ? 'spool-card-low' : ''} ${isLocked ? 'spool-card-locked' : ''}">
                ${isLocked ? `
                    <div class="spool-lock-overlay">
                        <div class="spool-lock-badge">
                            <span class="spool-lock-icon">🔒</span>
                            <span>Im Druck gesperrt</span>
                        </div>
                        <div class="spool-lock-job">${escapeHtml(activeJobName)}</div>
                    </div>
                ` : ''}
                <div class="spool-card-actions">
                    ${isLocked ? `
                        <button class="card-action-btn disabled" title="Waehrend eines aktiven Drucks gesperrt" disabled>
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                            </svg>
                        </button>
                    ` : `
                        <button class="card-action-btn" onclick="openEditModal('${s.id}')" title="Bearbeiten">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                                <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                            </svg>
                        </button>
                    `}
                    <button class="card-action-btn delete" onclick="openDeleteModal('${s.id}')" title="Löschen">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                            <polyline points="3 6 5 6 21 6"/>
                            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                        </svg>
                    </button>
                </div>

                <div class="spool-card-header">
                    <div class="spool-color-indicator" style="background: ${color};"></div>
                    <div class="spool-info">
                        <div class="spool-header-top">
                            <div style="min-width: 0;">
                                <h4 class="spool-name">${displayName}</h4>
                                <p class="spool-vendor">${vendor}</p>
                            </div>
                            <span class="spool-material-badge">${materialName}</span>
                        </div>

                        <div class="spool-progress">
                            <div class="progress-label">
                                <span class="progress-label-text">Verbleibend</span>
                                <span class="progress-value ${isLow ? 'low' : ''}">${remaining.toFixed(0)}g / ${netFilament.toFixed(0)}g</span>
                            </div>
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${percentage}%; background: ${progressColor};"></div>
                            </div>
                        </div>

                        <div class="spool-footer">
                            <span class="spool-percentage">${percentage.toFixed(0)}%</span>
                            ${value ? `<span class="spool-value">~€${value} Wert</span>` : ''}
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

function renderSpoolTable(spoolsToRender) {
    const container = document.getElementById('spoolsTable');
    if (!container) return;

    if (spoolsToRender.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📦</div>
                <h3>Keine Spulen gefunden</h3>
                <p>Fügen Sie Ihre erste Spule hinzu!</p>
                <button class="btn btn-primary" onclick="openAddModal()">
                    Spule hinzufügen
                </button>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Name</th>
                        <th>Material</th>
                        <th>AMS</th>
                        <th>Restgewicht</th>
                        <th>Status</th>
                        <th>Aktionen</th>
                    </tr>
                </thead>
                <tbody>
                    ${spoolsToRender.map(s => {
                        const material = materials.find(m => m.id === s.material_id);
                        const remaining = toNumber(s.remaining_weight_g);
                        const trayColor = s.tray_color ? `#${s.tray_color.substring(0, 6)}` : null;

                        // Number display
                        const isRFID = s.tray_uuid != null;
                        const spoolNumber = s.spool_number;
                        let numberDisplay = '-';
                        if (isRFID && spoolNumber != null) {
                            numberDisplay = `<span class="spool-number-badge rfid-badge">RFID</span> <strong>${spoolNumber}</strong>`;
                        } else if (isRFID) {
                            numberDisplay = '<span class="spool-number-badge rfid-badge">RFID</span>';
                        } else if (spoolNumber != null) {
                            numberDisplay = `<strong>${spoolNumber}</strong>`;
                        }

                        // Status badges
                        const fillPercent = toNumber(s.remaining_percent) ?? toNumber(s.remain_percent);
                        let fillClass = 'status-online';
                        let fillText = 'OK';
                        if (s.is_empty || (fillPercent != null && fillPercent <= 5)) {
                            fillClass = 'status-offline';
                            fillText = 'LEER';
                        } else if (fillPercent != null && fillPercent <= 20) {
                            fillClass = 'status-low';
                            fillText = 'WENIG';
                        } else if (fillPercent != null && fillPercent >= 80) {
                            fillText = 'VOLL';
                        }

                        let locationText = 'LAGER';
                        let locationClass = 'status-secondary';
                        if (s.printer_id != null && s.ams_slot != null) {
                            locationText = 'AMS - AKTIV';
                            locationClass = 'status-online';
                        }

                        // AMS info
                        let amsDisplay = '-';
                        if (s.ams_slot != null) {
                            const slotNum = s.ams_slot + 1;
                            const amsLabel = s.ams_id === '254' ? 'AMS Lite' : s.ams_id ? `AMS ${s.ams_id}` : 'AMS';
                            const printerPart = s.printer_name ? `${s.printer_name} ` : '';
                            amsDisplay = `<strong>${amsLabel} ${printerPart}Slot ${slotNum}</strong>`;
                        }

                        return `
                            <tr>
                                <td>${numberDisplay}</td>
                                <td><strong>${s.label || ''}</strong></td>
                                <td>
                                    ${material ? `
                                        <div style="display: flex; align-items: center; gap: 8px;">
                                            ${trayColor ? `<span class="color-preview" style="background: ${trayColor};"></span>` : ''}
                                            <div>
                                                <strong>${material.name}</strong>
                                                ${material.brand ? `<br><small style="color: var(--text-dim);">${material.brand}</small>` : ''}
                                            </div>
                                        </div>
                                    ` : '<span style="color: var(--error);">Unbekannt</span>'}
                                </td>
                                <td>${amsDisplay}</td>
                                <td><strong>${remaining != null ? `${remaining.toFixed(2)}g` : 'N/A'}</strong></td>
                                <td>
                                    <div class="status-stack">
                                        <span class="status-badge ${locationClass}">${locationText}</span>
                                        <span class="status-badge ${fillClass}">${fillText}</span>
                                    </div>
                                </td>
                                <td>
                                    <div class="table-actions">
                                        <button class="btn-icon" onclick="openEditModal('${s.id}')" title="Bearbeiten">✏️</button>
                                        <button class="btn-icon btn-delete" onclick="openDeleteModal('${s.id}')" title="Löschen">🗑️</button>
                                    </div>
                                </td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        </div>
    `;
}

// === COLOR NAME HELPER ===
function getColorName(hexColor) {
    if (!hexColor || hexColor.length < 6) return '';

    const hex = hexColor.toUpperCase();
    const r = parseInt(hex.substring(0, 2), 16);
    const g = parseInt(hex.substring(2, 4), 16);
    const b = parseInt(hex.substring(4, 6), 16);

    // Grayscale
    if (Math.abs(r - g) < 30 && Math.abs(g - b) < 30 && Math.abs(r - b) < 30) {
        if (r < 50) return 'schwarz';
        if (r > 200) return 'weiß';
        return 'grau';
    }

    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);

    if (max - min < 50) return 'grau';

    if (r === max) {
        if (g > 150 && b < 100) return 'gelb';
        if (g > 100 && b > 100) return 'orange';
        if (g < 100 && b > 100) return 'magenta pink';
        return 'rot';
    }

    if (g === max) {
        if (r > 150) return 'gelb';
        if (b > 150) return 'cyan türkis';
        return 'grün';
    }

    if (b === max) {
        if (r > 150) return 'magenta lila';
        if (g > 150) return 'cyan türkis';
        return 'blau';
    }

    return '';
}

// === FILTER ===
function filterSpools() {
    const searchTerm = document.getElementById('searchInput')?.value.toLowerCase() || '';
    const colorSearch = document.getElementById('searchColor')?.value.trim() || '';
    const statusFilter = document.getElementById('filterStatus')?.value || '';

    let filtered = spools;

    // Material filter
    if (selectedMaterial) {
        filtered = filtered.filter(s => {
            const material = materials.find(m => m.id === s.material_id);
            return material && material.name === selectedMaterial;
        });
    }

    // Search filter
    if (searchTerm) {
        filtered = filtered.filter(s => {
            const material = materials.find(m => m.id === s.material_id);
            return (s.label && s.label.toLowerCase().includes(searchTerm)) ||
                   (material && material.name.toLowerCase().includes(searchTerm)) ||
                   (s.manufacturer_spool_id && s.manufacturer_spool_id.toLowerCase().includes(searchTerm));
        });
    }

    // Color filter
    if (colorSearch) {
        filtered = filtered.filter(s => {
            const spoolColor = (s.tray_color || '').toUpperCase().substring(0, 6);
            const searchLower = colorSearch.toLowerCase();
            const isHexSearch = /^[A-F0-9]+$/i.test(colorSearch);

            if (isHexSearch) {
                return spoolColor.includes(colorSearch.toUpperCase());
            } else {
                const colorName = getColorName(spoolColor).toLowerCase();
                return colorName.includes(searchLower);
            }
        });
    }

    // Status filter
    if (statusFilter === 'active') {
        filtered = filtered.filter(s => !s.is_empty);
    } else if (statusFilter === 'empty') {
        filtered = filtered.filter(s => s.is_empty);
    } else if (statusFilter === 'low') {
        filtered = filtered.filter(s => {
            const remaining = toNumber(s.remaining_weight_g);
            const rp = toNumber(s.remaining_percent) ?? toNumber(s.remain_percent);
            if (rp != null) return !s.is_empty && rp <= 20;
            if (remaining != null) return !s.is_empty && remaining < 200;
            return false;
        });
    } else if (statusFilter === 'ams') {
        filtered = filtered.filter(s => s.ams_slot != null && s.printer_id);
    } else if (statusFilter === 'storage') {
        filtered = filtered.filter(s => s.status === 'Lager');
    }

    renderSpools(filtered);
}

function clearFilters() {
    const searchInput = document.getElementById('searchInput');
    const searchColor = document.getElementById('searchColor');
    const filterStatus = document.getElementById('filterStatus');

    if (searchInput) searchInput.value = '';
    if (searchColor) searchColor.value = '';
    if (filterStatus) filterStatus.value = '';

    selectedMaterial = null;
    updateMaterialChips();
    renderSpools(spools);
}

// Zeigt nur Spulen mit niedrigem Bestand an
function showLowStockSpools() {
    // Filter zurücksetzen
    const searchInput = document.getElementById('searchInput');
    const searchColor = document.getElementById('searchColor');
    const filterStatus = document.getElementById('filterStatus');

    if (searchInput) searchInput.value = '';
    if (searchColor) searchColor.value = '';
    if (filterStatus) filterStatus.value = 'low';

    selectedMaterial = null;
    updateMaterialChips();

    // Filter anwenden
    filterSpools();

    // Filter-Panel öffnen damit der User sieht dass gefiltert wird
    const filterPanel = document.getElementById('filterPanel');
    if (filterPanel) filterPanel.style.display = 'block';

    showNotification('Zeige Spulen mit niedrigem Bestand', 'info');
}

// === MODAL MANAGEMENT ===
function openAddModal() {
    if (materials.length === 0) {
        showNotification('Bitte erst ein Material anlegen!', 'warning');
        setTimeout(() => window.location.href = '/materials', 2000);
        return;
    }

    pendingAmsAssignmentDetection = null;
    currentSpoolId = null;
    document.getElementById('modalTitle').textContent = 'Spule hinzufügen';
    document.getElementById('spoolForm').reset();
    document.getElementById('spoolId').value = '';
    document.getElementById('spoolColor').value = '#ffffff';
    document.getElementById('spoolColorHex').value = '#ffffff';
    document.getElementById('spoolStatus').value = 'Lager';
    document.getElementById('spoolSpoolmanId').value = '';

    document.getElementById('spoolModal').classList.add('active');
}

function openAddModalFromAmsDetection(detection) {
    if (!detection) return;

    openAddModal();
    pendingAmsAssignmentDetection = { ...detection };

    const material = findMaterialForAmsDetection(detection);
    const colorHex = normalizeAmsHexColor(detection.tray_color);
    const weightFull = toNumber(detection.weight_full);
    const weightEmpty = toNumber(detection.weight_empty);
    const weightCurrent = toNumber(detection.weight_current);

    document.getElementById('modalTitle').textContent = 'Spule aus AMS anlegen';
    document.getElementById('spoolColor').value = colorHex;
    document.getElementById('spoolColorHex').value = colorHex;
    document.getElementById('spoolStatus').value = 'Lager';
    document.getElementById('spoolLabel').value = '';
    document.getElementById('spoolManufacturerId').value = detection.tag_uid || detection.tray_uuid || '';

    if (material) {
        document.getElementById('spoolMaterial').value = material.id;
        if (material.spool_weight_empty != null) {
            document.getElementById('spoolWeightEmpty').value = material.spool_weight_empty;
        }
        if (material.brand) {
            document.getElementById('spoolVendor').value = material.brand;
        }
    }

    if (!document.getElementById('spoolVendor').value) {
        document.getElementById('spoolVendor').value = detection.vendor || '';
    }
    if (weightFull != null) {
        document.getElementById('spoolWeightFull').value = weightFull;
    }
    if (weightEmpty != null) {
        document.getElementById('spoolWeightEmpty').value = weightEmpty;
    }
    if (weightCurrent != null) {
        document.getElementById('spoolWeightRemaining').value = weightCurrent;
    }
}

function openEditModal(id) {
    const spool = spools.find(s => s.id === id);
    if (!spool) return;

    currentSpoolId = id;
    document.getElementById('modalTitle').textContent = 'Spule bearbeiten';

    document.getElementById('spoolId').value = spool.id;
    document.getElementById('spoolMaterial').value = spool.material_id;
    document.getElementById('spoolVendor').value = spool.vendor_id || '';
    document.getElementById('spoolColor').value = spool.tray_color ? '#' + spool.tray_color.substring(0, 6) : '#ffffff';
    document.getElementById('spoolColorHex').value = spool.tray_color ? '#' + spool.tray_color.substring(0, 6) : '#ffffff';
    document.getElementById('spoolWeightFull').value = spool.weight_full || '';
    document.getElementById('spoolWeightEmpty').value = spool.weight_empty || '';

    const remainingForEdit = toNumber(spool.remaining_weight_g);
    document.getElementById('spoolWeightRemaining').value = remainingForEdit ?? '';
    document.getElementById('spoolManufacturerId').value = spool.manufacturer_spool_id || '';
    document.getElementById('spoolSpoolmanId').value = spool.external_id || '';
    document.getElementById('spoolNumber').value = spool.spool_number || '';

    const labelField = document.getElementById('spoolLabel');
    if (labelField) labelField.value = spool.label || '';

    const priceField = document.getElementById('spoolPrice');
    if (priceField) priceField.value = spool.price || '';

    // Status
    let statusValue = spool.status || 'Lager';
    if (spool.is_empty) statusValue = 'Leer';
    document.getElementById('spoolStatus').value = statusValue;

    // Lock status if in AMS
    const statusDropdown = document.getElementById('spoolStatus');
    const statusHint = document.getElementById('spoolStatusHint');
    const weightField = document.getElementById('spoolWeightRemaining');
    const isInAMS = spool.ams_slot != null && spool.printer_id != null;
    const isLocked = !!spool.is_locked;

    if (isLocked) {
        statusDropdown.disabled = true;
        statusDropdown.style.opacity = '0.6';
        if (weightField) {
            weightField.disabled = true;
            weightField.style.opacity = '0.6';
        }
        statusHint.textContent = `Spule ist waehrend des aktiven Drucks gesperrt${spool.active_job_name ? ': ' + spool.active_job_name : ''}`;
        statusHint.style.color = 'var(--warning)';
    } else if (isInAMS) {
        statusDropdown.disabled = true;
        statusDropdown.style.opacity = '0.6';
        if (weightField) {
            weightField.disabled = false;
            weightField.style.opacity = '1';
        }
        statusHint.textContent = 'Status kann nicht geändert werden (Spule ist im AMS)';
        statusHint.style.color = 'var(--warning)';
    } else {
        statusDropdown.disabled = false;
        statusDropdown.style.opacity = '1';
        if (weightField) {
            weightField.disabled = false;
            weightField.style.opacity = '1';
        }
        statusHint.textContent = 'Status wird bei AMS-Nutzung automatisch aktualisiert';
        statusHint.style.color = 'var(--text-dim)';
    }

    document.getElementById('spoolModal').classList.add('active');
}

function closeModal() {
    document.getElementById('spoolModal').classList.remove('active');
    currentSpoolId = null;
    pendingAmsAssignmentDetection = null;
}

async function assignNewSpoolToAms(spoolId, detection) {
    const response = await fetch(`/api/spools/${spoolId}/assign-from-ams`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            tray_uuid: detection.tray_uuid || null,
            tag_uid: detection.tag_uid || null,
            ams_slot: detection.ams_slot,
            ams_id: detection.ams_id || null,
            printer_id: detection.printer_id || null,
            remain_percent: detection.remain_percent,
            tray_type: detection.tray_type || null,
            tray_color: detection.tray_color || null,
            weight_current: detection.weight_current || null,
            weight_full: detection.weight_full || null,
            weight_empty: detection.weight_empty || null,
        })
    });

    if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || 'AMS-Zuordnung fehlgeschlagen');
    }

    return response.json();
}

function openDeleteModal(id) {
    deleteTargetId = id;
    document.getElementById('deleteModal').classList.add('active');
}

function closeDeleteModal() {
    document.getElementById('deleteModal').classList.remove('active');
    deleteTargetId = null;
}

// === SAVE SPOOL ===
async function saveSpool(event) {
    event.preventDefault();

    const status = document.getElementById('spoolStatus').value;

    if (status === 'Leer') {
        const confirmed = confirm(
            'ACHTUNG: Spule als LEER markieren?\n\n' +
            'Diese Aktion setzt die Spule als aufgebraucht.\n' +
            'Möchten Sie fortfahren?'
        );
        if (!confirmed) return;
    }

    const weightRemaining = document.getElementById('spoolWeightRemaining').value;
    const materialId = document.getElementById('spoolMaterial').value;
    const colorHex = document.getElementById('spoolColor').value;
    const trayColor = colorHex?.replace('#', '') || null;
    const spoolNumber = document.getElementById('spoolNumber').value;
    const spoolmanId = document.getElementById('spoolSpoolmanId').value;
    const priceValue = document.getElementById('spoolPrice')?.value;

    const is_empty = (status === 'Leer');
    const is_open = (status === 'Aktiv' || status === 'In Benutzung' || status === 'Leer');

    const weightFull = toNumber(document.getElementById('spoolWeightFull').value);
    const weightEmpty = toNumber(document.getElementById('spoolWeightEmpty').value);
    let weightCurrent = null;
    if (weightRemaining) {
        weightCurrent = toNumber(weightRemaining);
    }

    const data = {
        label: document.getElementById('spoolLabel')?.value || null,
        material_id: materialId,
        vendor_id: document.getElementById('spoolVendor').value || null,
        manufacturer_spool_id: document.getElementById('spoolManufacturerId').value || null,
        external_id: spoolmanId ? String(parseInt(spoolmanId, 10)) : null,
        tray_color: trayColor,
        is_open: is_open,
        is_empty: is_empty,
        spool_number: spoolNumber ? parseInt(spoolNumber) : null,
        status: status || null,
        price: priceValue ? parseFloat(priceValue) : null
    };

    if (weightFull != null) data.weight_full = weightFull;
    if (weightEmpty != null) data.weight_empty = weightEmpty;
    if (weightCurrent != null) data.weight_current = weightCurrent;

    try {
        let response;
        const isCreate = !currentSpoolId;
        const detection = isCreate && pendingAmsAssignmentDetection
            ? { ...pendingAmsAssignmentDetection }
            : null;

        if (currentSpoolId) {
            response = await fetch(`/api/spools/${currentSpoolId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        } else {
            response = await fetch('/api/spools/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        }

        if (response.ok) {
            const savedSpool = await response.json();

            if (isCreate && detection && savedSpool?.id) {
                try {
                    await assignNewSpoolToAms(savedSpool.id, detection);
                    clearPendingAmsAssignmentStorage(detection);
                    pendingAmsAssignmentDetection = null;
                    showNotification('Spule erstellt und AMS-Slot zugewiesen!', 'success');
                } catch (assignError) {
                    console.error('Fehler bei AMS-Zuordnung nach dem Speichern:', assignError);
                    showNotification(`Spule erstellt, aber AMS-Zuordnung fehlgeschlagen: ${assignError.message}`, 'warning');
                }
            } else {
                showNotification(currentSpoolId ? 'Spule aktualisiert!' : 'Spule erstellt!', 'success');
            }

            closeModal();
            clearFilters();
            await loadSpools();
        } else {
            const errorData = await response.json().catch(() => ({}));
            const errorMsg = errorData.detail || 'Speichern fehlgeschlagen';
            throw new Error(errorMsg);
        }

    } catch (error) {
        console.error('Fehler beim Speichern:', error);
        let message = error?.message || 'Fehler beim Speichern';
        if (message.includes('UNIQUE constraint failed: spool.spool_number')) {
            message = 'Spulennummer bereits vergeben';
        }
        showNotification(message, 'error');
    }
}

// === DELETE SPOOL ===
async function confirmDelete() {
    if (!deleteTargetId) return;

    try {
        const response = await fetch(`/api/spools/${deleteTargetId}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            showNotification('Spule gelöscht', 'success');
            closeDeleteModal();
            clearFilters();
            await loadSpools();
        } else {
            throw new Error('Löschen fehlgeschlagen');
        }

    } catch (error) {
        console.error('Fehler beim Löschen:', error);
        showNotification('Fehler beim Löschen', 'error');
    }
}

// === NOTIFICATIONS ===
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => notification.classList.add('show'), 10);
    setTimeout(() => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

window.openAddModalFromAmsDetection = openAddModalFromAmsDetection;
window.persistPendingAmsCreatePrefill = persistPendingAmsCreatePrefill;
