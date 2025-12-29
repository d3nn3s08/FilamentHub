// Spools Management JavaScript

let spools = [];
let materials = [];
let currentSpoolId = null;
let deleteTargetId = null;

function toNumber(val) {
    const n = parseFloat(val);
    return isNaN(n) ? null : n;
}

// === INIT ===
document.addEventListener('DOMContentLoaded', () => {
    loadData();
    setupEventListeners();
});

function setupEventListeners() {
    // Search
    document.getElementById('searchInput').addEventListener('input', filterSpools);
    
    // Filters
    document.getElementById('filterMaterial').addEventListener('change', filterSpools);
    document.getElementById('filterStatus').addEventListener('change', filterSpools);
    
    // Color picker sync
    const colorPicker = document.getElementById('spoolColor');
    const colorHex = document.getElementById('spoolColorHex');
    
    if (colorPicker && colorHex) {
        colorPicker.addEventListener('input', (e) => {
            colorHex.value = e.target.value;
        });
    }
}

// === LOAD DATA ===
async function loadData() {
    try {
        // Lade Materials ZUERST, dann Spools (wichtig für korrekte Anzeige)
        await loadMaterials();
        await loadSpools();
        await checkUnnumberedSpools(); // Prüfe auf Spulen ohne Nummer
    } catch (error) {
        console.error('Fehler beim Laden:', error);
    }
}

async function loadMaterials() {
    try {
        const response = await fetch('/api/materials/');
        materials = await response.json();
        updateMaterialSelects();
    } catch (error) {
        console.error('Fehler beim Laden der Materialien:', error);
    }
}

async function loadSpools() {
    try {
        const response = await fetch('/api/spools/');
        spools = await response.json();
        
        updateStats();
        updateWarnings();
        renderSpools(spools);
        
    } catch (error) {
        console.error('Fehler beim Laden der Spulen:', error);
        showNotification('Fehler beim Laden der Spulen', 'error');
    }
}

function updateMaterialSelects() {
    const select = document.getElementById('spoolMaterial');
    const filter = document.getElementById('filterMaterial');
    
    // Form select
    select.innerHTML = '<option value="">-- Material wählen --</option>';
    materials.forEach(m => {
        const option = document.createElement('option');
        option.value = m.id;
        option.textContent = `${m.name}${m.brand ? ' (' + m.brand + ')' : ''}`;
        select.appendChild(option);
    });
    
    // Filter select
    filter.innerHTML = '<option value="">Alle Materialien</option>';
    materials.forEach(m => {
        const option = document.createElement('option');
        option.value = m.id;
        option.textContent = `${m.name}${m.brand ? ' (' + m.brand + ')' : ''}`;
        filter.appendChild(option);
    });
}

function updateStats() {
    // Statistiken nur für Nicht-AMS-Spulen
    const total = spools.length;
    const active = spools.filter(s => !s.is_empty).length;
    const empty = spools.filter(s => s.is_empty).length;
    const totalWeight = spools.reduce((sum, s) => {
        if (s.is_empty) return sum;
        const wf = toNumber(s.weight_full) || 0;
        const rp = toNumber(s.remain_percent);
        const remaining = (toNumber(s.weight) ?? toNumber(s.weight_current) ?? toNumber(s.weight_remaining) ?? (rp != null && wf ? (rp / 100) * wf : wf)) ?? 0;
        return sum + (remaining || 0);
    }, 0);
    
    document.getElementById('statTotal').textContent = total;
    document.getElementById('statActive').textContent = active;
    document.getElementById('statEmpty').textContent = empty;
    document.getElementById('statWeight').textContent = Math.round(totalWeight);
}

function toggleWarnings() {
    const details = document.getElementById('warningsDetails');
    const icon = document.getElementById('warningToggleIcon');
    const text = document.getElementById('warningToggleText');
    
    if (details.style.display === 'none') {
        details.style.display = 'block';
        icon.textContent = '▲';
        text.textContent = 'Verbergen';
    } else {
        details.style.display = 'none';
        icon.textContent = '▼';
        text.textContent = 'Details';
    }
}

function updateWarnings() {
    // Zähle Spulen mit niedrigem Bestand (auch im AMS)
    const lowSpools = spools.filter(s => {
        if (s.is_empty) return false;
        const remaining = toNumber(s.weight) ?? toNumber(s.weight_current) ?? toNumber(s.weight_remaining) ?? 0;
        const percentage = toNumber(s.remain_percent) ?? 0;
        return percentage <= 20 || remaining < 200;
    });
    
    const warningCount = lowSpools.length;
    document.getElementById('warningCount').textContent = warningCount;
        // Zeige/Verstecke Warnungs-Card
    const warningCard = document.getElementById('warningCard');
    if (warningCount === 0) {
        warningCard.style.display = 'none';
    } else {
        warningCard.style.display = 'flex';
    }
        const warningList = document.getElementById('warningList');
    
    if (warningCount === 0) {
        warningList.innerHTML = '<p style="color: var(--text-dim); text-align: center; padding: 1rem;">Keine Warnungen \u2713</p>';
    } else {
        warningList.innerHTML = lowSpools.map(s => {
            const material = materials.find(m => m.id === s.material_id);
            const remaining = Math.round(toNumber(s.weight) ?? toNumber(s.weight_current) ?? toNumber(s.weight_remaining) ?? 0);
            const percentage = Math.round(toNumber(s.remain_percent) ?? 0);
            const displayName = s.label || `Spule #${s.id.substring(0, 8)}`;
            const location = s.ams_slot != null ? `AMS Slot ${s.ams_slot}` : 'Lager';
            
            return `
                <div class="warning-item">
                    <div class="warning-icon">⚠️</div>
                    <div class="warning-content">
                        <strong>${displayName}</strong>
                        <small>${material ? material.name : 'Unbekannt'} - ${location}</small>
                    </div>
                    <div class="warning-value">
                        <strong>${remaining}g</strong>
                        <small>${percentage}%</small>
                    </div>
                </div>
            `;
        }).join('');
    }
}

function renderSpools(spoolsToRender) {
    const container = document.getElementById('spoolsTable');
    document.getElementById('spoolCount').textContent = spoolsToRender.length;
    
    if (spoolsToRender.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🧵</div>
                <h3>Keine Spulen gefunden</h3>
                <p>Fügen Sie Ihre erste Spule hinzu!</p>
                <button class="btn btn-primary" onclick="openAddModal()">
                    ➕ Spule hinzufügen
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
                        <th>Material</th>
                        <th>Restgewicht</th>
                        <th>Status</th>
                        <th>Aktionen</th>
                    </tr>
                </thead>
                <tbody>
                    ${spoolsToRender.map(s => {
                        const material = materials.find(m => m.id === s.material_id);
                        const weightFull = toNumber(s.weight_full) ?? 0;
                        const remainPercent = toNumber(s.remain_percent);
                        const remaining = toNumber(s.weight) ?? toNumber(s.weight_current) ?? toNumber(s.weight_remaining) ?? ((remainPercent != null && weightFull) ? (remainPercent / 100) * weightFull : (weightFull || 0));
                        const trayColor = s.tray_color ? `#${s.tray_color.substring(0, 6)}` : null;

                        // NEU: Spulen-Nummern-System
                        const isRFID = s.tray_uuid != null;
                        const spoolNumber = s.spool_number;
                        let numberDisplay = '';

                        if (isRFID) {
                            numberDisplay = '<span class="spool-number-badge rfid-badge" title="RFID-Spule (Bambu)">📡 RFID</span>';
                        } else if (spoolNumber) {
                            numberDisplay = `<span class="spool-number-badge manual-badge" title="Manuelle Spule">#${spoolNumber}</span>`;
                        } else {
                            numberDisplay = '<span class="spool-number-badge" title="Keine Nummer">-</span>';
                        }

                        // Status anzeigen - Priorisiert manuellen Status, dann Leer-Status
                        let statusBadge = '';
                        let locationBadge = '';

                        // 1. Haupt-Status (Leer oder nicht)
                        if (remainPercent === 0 || (remaining || 0) <= 0 || s.is_empty) {
                            statusBadge = '<span class="status-badge status-offline">Leer</span>';
                        } else if (remainPercent != null && remainPercent <= 20) {
                            statusBadge = '<span class="status-badge" style="background: rgba(255, 167, 38, 0.2); color: var(--warning);">Fast leer</span>';
                        } else if (remaining < 200) {
                            statusBadge = '<span class="status-badge" style="background: rgba(255, 167, 38, 0.2); color: var(--warning);">Wenig</span>';
                        }

                        // 2. Lager-Status (wo ist die Spule?)
                        if (s.status === 'Lager') {
                            locationBadge = '<span class="status-badge" style="background: rgba(102, 187, 106, 0.2); color: #66BB6A;">🏪 Lager</span>';
                        } else if (s.status === 'AMS') {
                            locationBadge = '<span class="status-badge" style="background: rgba(66, 165, 245, 0.2); color: #42A5F5;">📦 AMS</span>';
                        } else if (s.status === 'In Benutzung') {
                            locationBadge = '<span class="status-badge status-printing">🖨️ In Benutzung</span>';
                        } else if (s.used_count && s.used_count > 0) {
                            locationBadge = '<span class="status-badge status-secondary">Gebraucht</span>';
                        } else if (s.is_open) {
                            locationBadge = '<span class="status-badge status-printing">Offen</span>';
                        } else {
                            locationBadge = '<span class="status-badge status-online">Neu</span>';
                        }

                        statusBadge = statusBadge || locationBadge;

                        return `
                            <tr>
                                <td>${numberDisplay}</td>
                                <td>
                                    ${material ? `
                                        <div style="display: flex; align-items: center; gap: 8px;">
                                            ${trayColor ? `<span class="color-preview" style="background: ${trayColor}; width: 24px; height: 24px;"></span>` : ''}
                                            <div>
                                                <strong>${material.name}</strong>
                                                ${material.brand ? `<br><small style="color: var(--text-dim);">${material.brand}</small>` : ''}
                                            </div>
                                        </div>
                                    ` : '<span style="color: var(--error);">Unbekannt</span>'}
                                </td>
                                <td>
                                    <strong>${(remaining || 0).toFixed(2)}g</strong>
                                    <small style="color: var(--text-dim);"> / ${weightFull}g</small>
                                </td>
                                <td>${statusBadge}</td>
                                <td>
                                    <div class="table-actions">
                                        <button class="btn-icon" onclick="openEditModal('${s.id}')" title="Bearbeiten">
                                            ✏️
                                        </button>
                                        <button class="btn-icon btn-delete" onclick="openDeleteModal('${s.id}')" title="Löschen">
                                            🗑️
                                        </button>
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

// === FILTER ===
function filterSpools() {
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    const materialFilter = document.getElementById('filterMaterial').value;
    const statusFilter = document.getElementById('filterStatus').value;
    
    let filtered = spools;
    
    // Search filter
    if (searchTerm) {
        filtered = filtered.filter(s => {
            const material = materials.find(m => m.id === s.material_id);
            return (s.label && s.label.toLowerCase().includes(searchTerm)) ||
                   (material && material.name.toLowerCase().includes(searchTerm)) ||
                   (s.manufacturer_spool_id && s.manufacturer_spool_id.toLowerCase().includes(searchTerm));
        });
    }
    
    // Material filter
    if (materialFilter) {
        filtered = filtered.filter(s => s.material_id === materialFilter);
    }
    
    // Status filter
    if (statusFilter === 'active') {
        filtered = filtered.filter(s => !s.is_empty);
    } else if (statusFilter === 'empty') {
        filtered = filtered.filter(s => s.is_empty);
    } else if (statusFilter === 'low') {
        filtered = filtered.filter(s => {
            const wf = toNumber(s.weight_full) || 0;
            const rp = toNumber(s.remain_percent);
            const remaining = toNumber(s.weight) ?? toNumber(s.weight_current) ?? toNumber(s.weight_remaining) ?? (rp != null && wf ? (rp / 100) * wf : wf);
            return (rp === 0) || (!s.is_empty && (remaining || 0) < 200);
        });
    } else if (statusFilter === 'ams') {
        // Filter: Nur Spulen im AMS
        filtered = filtered.filter(s => s.status === 'AMS' || (s.ams_slot != null && s.printer_id));
    } else if (statusFilter === 'in-use') {
        // Filter: In Benutzung (ohne AMS) - manuelle Verwendung
        filtered = filtered.filter(s => s.status === 'In Benutzung');
    } else if (statusFilter === 'storage') {
        // Filter: Im Lager
        filtered = filtered.filter(s => s.status === 'Lager');
    } else if (statusFilter === 'no-number') {
        // NEUE FILTER-OPTION: Spulen ohne Nummer (für Benachrichtigung)
        filtered = filtered.filter(s => s.spool_number == null);
    }

    renderSpools(filtered);
}

function clearFilters() {
    document.getElementById('searchInput').value = '';
    document.getElementById('filterMaterial').value = '';
    document.getElementById('filterStatus').value = '';
    renderSpools(spools);
}

// === MODAL MANAGEMENT ===
function openAddModal() {
    if (materials.length === 0) {
        showNotification('Bitte erst ein Material anlegen!', 'warning');
        setTimeout(() => window.location.href = '/materials', 2000);
        return;
    }
    
    currentSpoolId = null;
    document.getElementById('modalTitle').textContent = '➕ Spule hinzufügen';
    document.getElementById('spoolForm').reset();
    document.getElementById('spoolId').value = '';
    document.getElementById('spoolWeightFull').value = '1000';
    document.getElementById('spoolWeightEmpty').value = '250';
    document.getElementById('spoolColor').value = '#ffffff';
    document.getElementById('spoolColorHex').value = '#ffffff';
    document.getElementById('spoolStatus').value = 'Lager';  // Neue Spulen starten als "Lager"
    document.getElementById('spoolNumber').value = '';
    document.getElementById('spoolModal').classList.add('active');
}

function openEditModal(id) {
    const spool = spools.find(s => s.id === id);
    if (!spool) return;

    currentSpoolId = id;
    document.getElementById('modalTitle').textContent = '✏️ Spule bearbeiten';

    document.getElementById('spoolId').value = spool.id;
    document.getElementById('spoolMaterial').value = spool.material_id;
    document.getElementById('spoolVendor').value = spool.vendor_id || '';
    document.getElementById('spoolColor').value = spool.tray_color ? '#' + spool.tray_color : '#ffffff';
    document.getElementById('spoolColorHex').value = spool.tray_color ? '#' + spool.tray_color : '#ffffff';
    document.getElementById('spoolWeightFull').value = spool.weight_full;
    document.getElementById('spoolWeightEmpty').value = spool.weight_empty;
    document.getElementById('spoolWeightRemaining').value = (toNumber(spool.weight) ?? toNumber(spool.weight_current) ?? toNumber(spool.weight_remaining)) ?? '';
    document.getElementById('spoolManufacturerId').value = spool.manufacturer_spool_id || '';
    document.getElementById('spoolNumber').value = spool.spool_number || '';

    // Status setzen (basierend auf is_empty und status)
    let statusValue = spool.status || 'Lager';
    if (spool.is_empty) {
        statusValue = 'Leer';
    }
    document.getElementById('spoolStatus').value = statusValue;

    // Status-Dropdown sperren wenn Spule im AMS ist
    const statusDropdown = document.getElementById('spoolStatus');
    const statusHint = document.getElementById('spoolStatusHint');
    const isInAMS = spool.ams_slot != null && spool.printer_id != null;

    if (isInAMS) {
        statusDropdown.disabled = true;
        statusDropdown.style.opacity = '0.6';
        statusDropdown.style.cursor = 'not-allowed';
        statusHint.textContent = '🔒 Status kann nicht geändert werden (Spule ist im AMS)';
        statusHint.style.color = 'var(--warning)';
    } else {
        statusDropdown.disabled = false;
        statusDropdown.style.opacity = '1';
        statusDropdown.style.cursor = 'pointer';
        statusHint.textContent = '💡 Status wird bei AMS-Nutzung automatisch aktualisiert';
        statusHint.style.color = 'var(--text-dim)';
    }

    document.getElementById('spoolModal').classList.add('active');
}

function closeModal() {
    document.getElementById('spoolModal').classList.remove('active');
    currentSpoolId = null;
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

    // SICHERHEITSABFRAGE: Wenn Status auf "Leer" gesetzt wird
    if (status === 'Leer') {
        const confirmed = confirm(
            '⚠️ ACHTUNG: Spule als LEER markieren?\n\n' +
            'Diese Aktion setzt die Spule als aufgebraucht.\n' +
            'Möchten Sie fortfahren?'
        );

        if (!confirmed) {
            return; // Abbrechen
        }
    }

    const weightRemaining = document.getElementById('spoolWeightRemaining').value;
    const materialId = document.getElementById('spoolMaterial').value;
    const colorHex = document.getElementById('spoolColor').value;
    const trayColor = colorHex?.replace('#', '') || null;
    const spoolNumber = document.getElementById('spoolNumber').value;

    // Status-basierte Flags
    const is_empty = (status === 'Leer');
    const is_open = (status === 'Aktiv' || status === 'In Benutzung' || status === 'Leer');

    const data = {
        material_id: materialId,
        weight_full: parseFloat(document.getElementById('spoolWeightFull').value),
        weight_empty: parseFloat(document.getElementById('spoolWeightEmpty').value),
        weight_current: weightRemaining ? parseFloat(weightRemaining) : null,
        vendor_id: document.getElementById('spoolVendor').value || null,
        manufacturer_spool_id: document.getElementById('spoolManufacturerId').value || null,
        tray_color: trayColor,
        is_open: is_open,
        is_empty: is_empty,
        spool_number: spoolNumber ? parseInt(spoolNumber) : null,
        status: status || null
    };
    
    try {
        let response;
        
        if (currentSpoolId) {
            // Update existing
            response = await fetch(`/api/spools/${currentSpoolId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        } else {
            // Create new
            response = await fetch('/api/spools/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        }
        
        if (response.ok) {
            showNotification(
                currentSpoolId ? 'Spule aktualisiert!' : 'Spule erstellt!', 
                'success'
            );
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
        showNotification('Fehler beim Speichern', 'error');
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

// === BENACHRICHTIGUNGS-SYSTEM FÜR SPULEN OHNE NUMMER ===
async function checkUnnumberedSpools() {
    try {
        const response = await fetch('/api/spools/unnumbered');
        if (!response.ok) return;

        const unnumbered = await response.json();

        // Filtere nur RFID-Spulen (die vom AMS kommen)
        const rfidSpools = unnumbered.filter(s => s.tray_uuid != null);

        if (rfidSpools.length > 0) {
            showUnnumberedNotification(rfidSpools.length);
        }
    } catch (error) {
        console.error('Fehler beim Laden unnummerierter Spulen:', error);
    }
}

function showUnnumberedNotification(count) {
    // Prüfe ob bereits eine Benachrichtigung existiert
    if (document.getElementById('unnumberedNotification')) return;

    const notification = document.createElement('div');
    notification.id = 'unnumberedNotification';
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 16px 20px;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        z-index: 10000;
        max-width: 350px;
        cursor: pointer;
        animation: slideIn 0.3s ease-out;
    `;

    notification.innerHTML = `
        <div style="display: flex; align-items: center; gap: 12px;">
            <div style="font-size: 24px;">⚠️</div>
            <div style="flex: 1;">
                <strong style="display: block; margin-bottom: 4px;">
                    ${count} neue Spule${count > 1 ? 'n' : ''} ohne Nummer
                </strong>
                <small style="opacity: 0.9;">
                    Klicken zum Nummerieren
                </small>
            </div>
            <div style="font-size: 20px; opacity: 0.7;">→</div>
        </div>
    `;

    notification.addEventListener('click', () => {
        // Setze Filter auf "Keine Nummer" und schließe Benachrichtigung
        document.getElementById('filterStatus').value = 'no-number';
        filterSpools();
        notification.remove();
    });

    document.body.appendChild(notification);

    // Automatisch nach 10 Sekunden ausblenden
    setTimeout(() => {
        if (notification.parentElement) {
            notification.style.animation = 'slideOut 0.3s ease-in';
            setTimeout(() => notification.remove(), 300);
        }
    }, 10000);
}

// CSS Animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Close modals on ESC key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
        closeDeleteModal();
    }
});

// Close modals on background click
document.getElementById('spoolModal').addEventListener('click', (e) => {
    if (e.target.id === 'spoolModal') closeModal();
});

document.getElementById('deleteModal').addEventListener('click', (e) => {
    if (e.target.id === 'deleteModal') closeDeleteModal();
});
