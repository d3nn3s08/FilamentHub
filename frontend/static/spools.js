// Spools Management JavaScript

let spools = [];

let materials = [];

let currentSpoolId = null;

let deleteTargetId = null;



function toNumber(val) {

    const n = parseFloat(val);

    return isNaN(n) ? null : n;

}

const LOCATION_LABELS = {

    IN_USE: '\u{1F5A8}\uFE0F In Benutzung',

    AMS_ACTIVE: '\u{1F4E6} AMS \u2013 Aktiv',

    EXTERN: '\u{1F50C} Extern',

    LAGER: '\u{1F3EA} Lager'

};

const FILL_STATE_LABELS = {

    empty: '\u{1F534} Leer',

    fast_empty: '\u{1F534} Fast leer',

    low: '\u{1F7E1} Wenig',

    ok: '\u{1F7E2} OK',

    full: '\u{1F535} Voll',

    unknown: '\u26AA Unbekannt'

};

const META_LABELS = {

    NEW: '\u{1F195} Neu',

    OPEN: '\u{1F4C2} Offen',

    USED: '\u267B\uFE0F Gebraucht'

};

function renderStatusBadge(text, className = '', styleText = '') {

    const classAttr = className ? ` ${className}` : '';

    const styleAttr = styleText ? ` style="${styleText}"` : '';

    return `<span class="status-badge${classAttr}"${styleAttr}>${text}</span>`;

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



    // Material selection auto-fill weight_empty from Material

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

        const remaining = toNumber(s.remaining_weight_g);

        if (remaining == null) return sum;

        return sum + remaining;

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

        const remaining = toNumber(s.remaining_weight_g);

        const percentage = toNumber(s.remaining_percent) ?? toNumber(s.remain_percent);

        if (percentage != null) {

            return percentage <= 20;

        }

        if (remaining != null) {

            return remaining < 200;

        }

        return false;

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

        warningList.innerHTML = '<p style="color: var(--text-dim); text-align: center; padding: 1rem;">Keine Warnungen ✓</p>';

    } else {

        warningList.innerHTML = lowSpools.map(s => {

            const material = materials.find(m => m.id === s.material_id);

            const remainingValue = toNumber(s.remaining_weight_g);

            const remaining = remainingValue != null ? Math.round(remainingValue) : null;

            const percentValue = toNumber(s.remaining_percent) ?? toNumber(s.remain_percent);

            const percentage = percentValue != null ? Math.round(percentValue) : null;

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

                        <strong>${remaining != null ? `${remaining}g` : 'N/A'}</strong>

                        <small>${percentage != null ? `${percentage}%` : ''}</small>

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

                <div class="empty-state-icon">➕</div>

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

                        const remainPercent = toNumber(s.remaining_percent) ?? toNumber(s.remain_percent);



                        const remaining = toNumber(s.remaining_weight_g);



                        const trayColor = s.tray_color ? `#${s.tray_color.substring(0, 6)}` : null;



                        // NEU: Spulen-Nummern-System

                        const isRFID = s.tray_uuid != null;

                        const spoolNumber = s.spool_number;

                        let numberDisplay = '';
                        if (isRFID) {

                            numberDisplay = '<span class="spool-number-badge rfid-badge" title="RFID-Spule (Bambu)">RFID</span>';

                        } else if (spoolNumber != null) {

                            numberDisplay = String(spoolNumber);

                        } else {

                            numberDisplay = '-';

                        }

                        // Status anzeigen - Ort/Nutzung, Fuellstand, Meta

                        const fillKey = s.fill_state;

                        const fillLabel = FILL_STATE_LABELS[fillKey] || FILL_STATE_LABELS.unknown;

                        let fillClass = 'status-secondary';

                        let fillStyle = '';

                        if (fillKey === 'empty' || fillKey === 'fast_empty') {

                            fillClass = 'status-offline';

                        } else if (fillKey === 'low') {

                            fillStyle = 'background: rgba(255, 167, 38, 0.2); color: var(--warning);';

                        } else if (fillKey === 'ok' || fillKey === 'full') {

                            fillClass = 'status-online';

                        }

                        let locationLabel = LOCATION_LABELS.LAGER;

                        let locationClass = 'status-secondary';

                        if (s.active_job === true) {

                            locationLabel = LOCATION_LABELS.IN_USE;

                            locationClass = 'status-printing';

                        } else if (s.location === 'external') {

                            locationLabel = LOCATION_LABELS.EXTERN;

                            locationClass = 'status-online';

                        } else if (s.printer_id != null && s.ams_slot != null) {

                            locationLabel = LOCATION_LABELS.AMS_ACTIVE;

                            locationClass = 'status-online';

                        }

                        const isInStorage = s.printer_id == null;

                        const metaLabels = [];

                        if (isInStorage && (s.used_count || 0) === 0 && s.is_open === false) {

                            metaLabels.push(META_LABELS.NEW);

                        }

                        if (isInStorage && s.is_open === true) {

                            metaLabels.push(META_LABELS.OPEN);

                        }

                        if (isInStorage && (s.used_count || 0) > 0) {

                            metaLabels.push(META_LABELS.USED);

                        }

                        const metaLabel = metaLabels.length ? metaLabels.join(' / ') : null;

                        const statusBadge = `

                            <div class="status-stack">

                                <div>${renderStatusBadge(locationLabel, locationClass)}</div>

                                <div>${renderStatusBadge(fillLabel, fillClass, fillStyle)}</div>

                                ${metaLabel ? `<div>${renderStatusBadge(metaLabel, 'status-secondary')}</div>` : ''}

                            </div>

                        `;



                        return `

                            <tr>

                                <td>${numberDisplay}</td>

                                <thead>
                                    <tr>
                                        <th>Nummer</th>
                                        <th>Slot</th>
                                        <th>Material</th>
                                        <th>Restgewicht</th>
                                        <th>Status</th>
                                        <th>Aktionen</th>
                                    </tr>
                                </thead>

                                                <strong>${material.name}</strong>

                                                ${material.brand ? `<br><small style="color: var(--text-dim);">${material.brand}</small>` : ''}

                                            </div>

                                        </div>

                                    ` : '<span style="color: var(--error);">Unbekannt</span>'}

                                </td>

                                <tr>
                                    <td style="white-space:nowrap;">${numberDisplay}</td>
                                    <td style="text-align:center;">${s.ams_slot != null ? s.ams_slot : '-'}</td>
                                    <strong>${remaining != null ? `${remaining.toFixed(2)}g` : 'N/A'}</strong>

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

            const remaining = toNumber(s.remaining_weight_g);

            const rp = toNumber(s.remaining_percent) ?? toNumber(s.remain_percent);

            if (rp != null) {

                return rp === 0 || (!s.is_empty && rp <= 20);

            }

            if (remaining != null) {

                return !s.is_empty && remaining < 200;

            }

            return false;

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

    document.getElementById('spoolWeightFull').value = '';

    document.getElementById('spoolWeightEmpty').value = '';

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



    // Restgewicht aus Backend (keine lokalen Fallbacks)

    const remainingForEdit = toNumber(spool.remaining_weight_g);

    document.getElementById('spoolWeightRemaining').value = remainingForEdit ?? '';

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



    // Berechne weight_current aus Restgewicht-Eingabe

    // weight_current = NUR das Filament (ohne Spule)

    const weightFull = toNumber(document.getElementById('spoolWeightFull').value);

    const weightEmpty = toNumber(document.getElementById('spoolWeightEmpty').value);

    let weightCurrent = null;

    if (weightRemaining) {

        // User gibt Restgewicht ein → weight_current ist dieses Restgewicht (nur Filament)

        weightCurrent = toNumber(weightRemaining);

    } else if (!currentSpoolId) {

        // Keine Annahme fuer neue Spulen ohne Restgewicht

        weightCurrent = null;

    }



    const data = {

        material_id: materialId,

        vendor_id: document.getElementById('spoolVendor').value || null,

        manufacturer_spool_id: document.getElementById('spoolManufacturerId').value || null,

        tray_color: trayColor,

        is_open: is_open,

        is_empty: is_empty,

        spool_number: spoolNumber ? parseInt(spoolNumber) : null,

        status: status || null

    };



    if (weightFull != null) {

        data.weight_full = weightFull;

    }

    if (weightEmpty != null) {

        data.weight_empty = weightEmpty;

    }

    if (weightCurrent != null) {

        data.weight_current = weightCurrent;

    }

    

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

        let message = (error && error.message) ? error.message : 'Fehler beim Speichern';
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



// === MODAL BACKDROP CLICK ===

document.getElementById('spoolModal').addEventListener('click', (e) => {

    if (e.target.id === 'spoolModal') closeModal();

});



document.getElementById('deleteModal').addEventListener('click', (e) => {

    if (e.target.id === 'deleteModal') closeDeleteModal();

});
