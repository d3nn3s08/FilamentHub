// AMS Monitoring JavaScript

let amsData = [];
let spools = [];
let materials = [];
let liveState = {}; // Live-State von MQTT

let isLoading = false;
let singleAmsMode = true; // Single AMS Mode aktiviert

// === INIT ===
document.addEventListener('DOMContentLoaded', () => {
    // Check if multi-AMS mode was requested
    const urlParams = new URLSearchParams(window.location.search);
    if (urlParams.get('mode') === 'multi') {
        singleAmsMode = false;
        localStorage.setItem('amsMode', 'multi');
    } else if (urlParams.get('mode') === 'single') {
        singleAmsMode = true;
        localStorage.setItem('amsMode', 'single');
    } else {
        // Load from localStorage or default to single
        const savedMode = localStorage.getItem('amsMode');
        singleAmsMode = savedMode !== 'multi';
    }
    
    applySingleAmsMode();
    loadData();
    
    // Auto-refresh every 15 seconds (reduziert Server-Last)
    setInterval(() => {
        if (!isLoading) {
            loadData();
        }
    }, 15000);
    
    // Setup AMS mode toggle listeners
    setupAmsModeToogle();
});

// Apply Single AMS Mode styling
function applySingleAmsMode() {
    const amsGrid = document.querySelector('.ams-grid');
    if (amsGrid && singleAmsMode) {
        amsGrid.classList.add('single-mode');
    } else if (amsGrid) {
        amsGrid.classList.remove('single-mode');
    }
}

// Setup AMS Mode Toggle
function setupAmsModeToogle() {
    // Find Single AMS and Multi AMS radio buttons by name
    const amsRadios = document.querySelectorAll('input[name="ams_mode"]');
    
    amsRadios.forEach(radio => {
        // Set initial checked state
        if (radio.value === 'single' && singleAmsMode) {
            radio.checked = true;
        } else if (radio.value === 'multi' && !singleAmsMode) {
            radio.checked = true;
        }
        
        // Add change listener
        radio.addEventListener('change', () => {
            if (radio.checked) {
                const newMode = radio.value;
                localStorage.setItem('amsMode', newMode);
                // Reload page with new mode
                window.location.href = `/ams?mode=${newMode}`;
            }
        });
    });
}

// === LOAD DATA ===
async function loadData() {
    if (isLoading) return;
    
    isLoading = true;
    const loadingOverlay = document.getElementById('loadingOverlay');
    
    // Zeige Loading nur beim ersten Mal
    if (spools.length === 0 && loadingOverlay) {
        loadingOverlay.style.display = 'flex';
    }
    
    try {
        // Lade Spools, Materials und Live-State parallel (schneller)
        await Promise.all([
            loadSpools(),
            loadMaterials(),
            loadLiveState()
        ]);

        // Verarbeite AMS-Daten (basiert auf spools + live-state)
        loadAMSData();

        updateStats();
        renderAMSUnits();
        renderAlerts();
        
    } catch (error) {
        console.error('Fehler beim Laden der AMS-Daten:', error);
        showNotification('Fehler beim Laden der AMS-Daten', 'error');
    } finally {
        isLoading = false;
        if (loadingOverlay) {
            loadingOverlay.style.display = 'none';
        }
    }
}

async function loadSpools() {
    try {
        const response = await fetch('/api/spools/');
        spools = await response.json();
    } catch (error) {
        console.error('Fehler beim Laden der Spulen:', error);
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

async function loadLiveState() {
    try {
        const response = await fetch('/api/live-state/');
        if (response.ok) {
            liveState = await response.json();
            console.log('[AMS] Live-State geladen:', Object.keys(liveState).length, 'Geräte');
        }
    } catch (error) {
        console.error('Fehler beim Laden des Live-State:', error);
        liveState = {};
    }
}

function loadAMSData() {
    // Generate AMS structure based on spools with ams_slot
    // Single AMS Mode: Only create 1 AMS unit
    // Multi AMS Mode: Create 4 AMS units

    // Check Live-State für AMS-Status
    const hasLiveState = Object.keys(liveState).length > 0;
    let amsOnline = false;
    let amsInfo = null;
    let deviceSerial = null;
    let printerName = 'Kein Drucker';

    if (hasLiveState) {
        // Nehme den ersten Drucker aus Live-State
        const deviceKey = Object.keys(liveState)[0];
        const deviceData = liveState[deviceKey];
        deviceSerial = deviceKey; // z.B. "00M09A372601070"

        if (deviceData && deviceData.payload && deviceData.payload.print) {
            const ams = deviceData.payload.print.ams;
            if (ams && ams.ams && ams.ams.length > 0) {
                amsOnline = true;
                amsInfo = ams.ams[0]; // Erstes AMS
                console.log('[AMS] Online! Device:', deviceSerial, 'AMS ID:', amsInfo.id, 'Temp:', amsInfo.temp, 'Humidity:', amsInfo.humidity, 'Trays:', amsInfo.tray?.length || 0);
            }
        }
    }

    // Finde den Drucker-Namen aus der Spulen-Liste (Quick-Hack, sollte später aus Drucker-API kommen)
    const firstSpool = spools.find(s => s.ams_slot != null);
    if (firstSpool && firstSpool.printer_name) {
        printerName = firstSpool.printer_name;
    } else if (deviceSerial) {
        printerName = `Bambu ${deviceSerial.substring(0, 8)}...`;
    }

    if (singleAmsMode) {
        amsData = [
            {
                id: 1,
                online: amsOnline,
                slots: [],
                serial: deviceSerial || (amsInfo?.id ? `AMS-${amsInfo.id}` : 'AMS-001'),
                firmware: amsInfo?.info || 'v1.2.3',
                signal: '85%',
                printer: printerName,
                temp: amsInfo?.temp || null,
                humidity: amsInfo?.humidity || null
            }
        ];
    } else {
        amsData = [
            {
                id: 1,
                online: amsOnline,
                slots: [],
                serial: deviceSerial || (amsInfo?.id ? `AMS-${amsInfo.id}` : 'AMS-001'),
                firmware: amsInfo?.info || 'v1.2.3',
                signal: '85%',
                printer: printerName,
                temp: amsInfo?.temp || null,
                humidity: amsInfo?.humidity || null
            },
            { id: 2, online: false, slots: [], serial: 'AMS-002', firmware: 'v1.2.3', signal: '–', printer: null },
            { id: 3, online: false, slots: [], serial: 'AMS-003', firmware: 'v1.2.2', signal: '–', printer: null },
            { id: 4, online: false, slots: [], serial: 'AMS-004', firmware: 'v1.2.3', signal: '–', printer: null }
        ];
    }

    // Map spools to AMS #1 slots (or distribute across multiple AMS in multi mode)
    // Priorität: Live-State Spulen > Manuell zugewiesene Spulen

    // 1. Füge Live-State Spulen hinzu (wenn vorhanden)
    if (amsInfo && amsInfo.tray) {
        console.log('[AMS] Processing', amsInfo.tray.length, 'trays from live-state');
        amsInfo.tray.forEach((tray, index) => {
            if (tray && tray.tray_type && tray.tray_type !== '') {
                const ams = amsData[0];

                // Versuche eine passende Spule aus der DB zu finden
                const matchingSpool = spools.find(s =>
                    s.ams_slot === index ||
                    (s.rfid_uid && s.rfid_uid === tray.tag_uid)
                );

                const material = matchingSpool ? materials.find(m => m.id === matchingSpool.material_id) : null;

                console.log(`[AMS] Slot ${index + 1}:`, tray.tray_type, tray.tray_color, `${tray.remain}g`, matchingSpool ? '(DB Match)' : '(Live-State only)');

                ams.slots[index] = {
                    slot: index + 1,
                    spool: matchingSpool || {
                        id: null,
                        ams_slot: index,
                        material_type: tray.tray_type,
                        color: tray.tray_color?.substring(0, 6) || '000000',
                        weight_remaining: tray.remain || 0,
                        weight_total: tray.tray_weight || 1000,
                        rfid_uid: tray.tag_uid,
                        from_live_state: true
                    },
                    material: material,
                    liveData: tray
                };
            }
        });
    } else {
        console.log('[AMS] No trays found in live-state');
    }

    // 2. Ergänze manuell zugewiesene Spulen (wenn nicht schon durch Live-State besetzt)
    spools.forEach(spool => {
        if (spool.ams_slot != null && spool.ams_slot !== '') {
            const slotId = parseInt(spool.ams_slot);

            if (slotId >= 0 && slotId <= 3) {
                const ams = amsData[0];

                // Nur hinzufügen, wenn Slot noch leer ist
                if (!ams.slots[slotId]) {
                    const material = materials.find(m => m.id === spool.material_id);

                    ams.slots[slotId] = {
                        slot: slotId + 1,
                        spool: spool,
                        material: material
                    };
                }
            }
        }
    });
}

// === UPDATE STATS ===
function updateStats() {
    const onlineCount = amsData.filter(a => a.online).length;
    const activeSlots = amsData.reduce((sum, ams) => sum + ams.slots.filter(s => s).length, 0);
    
    // Calculate available filament (kg)
    let totalFilament = 0;
    amsData.forEach(ams => {
        ams.slots.forEach(slot => {
            if (slot && slot.spool) {
                totalFilament += getRemaining(slot.spool);
            }
        });
    });
    
    // Count warnings (low spools in AMS)
    let warnings = 0;
    amsData.forEach(ams => {
        ams.slots.forEach(slot => {
            if (slot && slot.spool) {
                const remaining = getRemaining(slot.spool);
                const percentage = getPercentage(slot.spool);
                if (percentage <= 20 || remaining < 200) {
                    warnings++;
                }
            }
        });
    });
    
    document.getElementById('amsOnlineCount').textContent = onlineCount;
    document.getElementById('amsActiveSlots').textContent = activeSlots;
    document.getElementById('amsAvailableFilament').textContent = (totalFilament / 1000).toFixed(2) + 'kg';
    
    // Update warning count in KPI card
    updateWarningCount();
}

// === RENDER AMS UNITS ===
function renderAMSUnits() {
    amsData.forEach((ams, index) => {
        const amsId = index + 1;
        const statusElement = document.getElementById(`amsStatus${amsId}`);
        const slotsContainer = document.getElementById(`amsSlots${amsId}`);
        
        // Update AMS device info
        const serialEl = document.getElementById(`amsSerial${amsId}`);
        const firmwareEl = document.getElementById(`amsFirmware${amsId}`);
        const connectionEl = document.getElementById(`amsConnection${amsId}`);
        const signalEl = document.getElementById(`amsSignal${amsId}`);
        const printerEl = document.getElementById(`amsPrinter${amsId}`);
        
        if (serialEl) serialEl.textContent = `SN: ${ams.serial || '–'}`;
        if (firmwareEl) firmwareEl.textContent = `FW: ${ams.firmware || '–'}`;
        if (signalEl) signalEl.textContent = ams.signal || '–';
        if (printerEl) {
            printerEl.innerHTML = ams.printer 
                ? `<span class="printer-badge">${ams.printer}</span>`
                : `<span class="printer-badge">Kein Drucker</span>`;
        }
        
        // Update status badge
        if (ams.online) {
            statusElement.innerHTML = '<span class="status-badge status-online">Online</span>';
        } else {
            statusElement.innerHTML = '<span class="status-badge status-offline">Offline</span>';
        }
        
        // Render slots
        let slotsHTML = '';
        for (let i = 0; i < 4; i++) {
            const slotNumber = i + 1;
            const slot = ams.slots[i];
            
            if (slot && slot.spool && slot.material) {
                const spool = slot.spool;
                const material = slot.material;
                const remaining = getRemaining(spool);
                const percentage = getPercentage(spool);
                const color = spool.tray_color ? `#${spool.tray_color.substring(0, 6)}` : '#999';
                
                const isLow = percentage <= 20 || remaining < 200;
                const progressClass = isLow ? 'low' : '';
                
                const spoolNumberDisplay = spool.spool_number ? `#${spool.spool_number} ` : '';

                slotsHTML += `
                    <div class="slot ${spool.is_empty ? 'slot-empty' : ''}">
                        <div class="slot-color" style="background: ${color};"></div>
                        <div class="slot-number">
                            Slot ${slotNumber}
                            ${spool.tray_uuid ? '<span class="slot-icon" title="RFID erkannt">🏷️</span>' : ''}
                        </div>
                        ${spoolNumberDisplay ? `<div class="slot-spool-number" style="font-weight: 600; color: var(--primary); margin: 4px 0;">${spoolNumberDisplay}</div>` : ''}
                        <div class="slot-material">${material.name}</div>
                        ${material.brand ? `<div class="slot-brand">${material.brand}</div>` : ''}
                        <div class="slot-weight">${Math.round(remaining)}g (${Math.round(percentage)}%)</div>
                        <div class="slot-progress">
                            <div class="slot-progress-bar ${progressClass}" style="width: ${percentage}%;"></div>
                        </div>
                        <div class="slot-actions">
                            <button class="slot-action-btn" onclick="event.stopPropagation(); goToSpool('${spool.id}')" title="Spule öffnen">
                                <span>📋</span>
                            </button>
                            <button class="slot-action-btn" onclick="event.stopPropagation(); unassignSpool('${spool.id}')" title="Spule entfernen">
                                <span>✖️</span>
                            </button>
                            <button class="slot-action-btn" onclick="event.stopPropagation(); refreshRFID(${amsId}, ${slotNumber})" title="RFID neu einlesen">
                                <span>🔄</span>
                            </button>
                        </div>
                    </div>
                `;
            } else {
                slotsHTML += `
                    <div class="slot-empty">
                        <div class="slot-number">Slot ${slotNumber}</div>
                        <div class="slot-label">Leer</div>
                        <button class="btn btn-sm btn-primary" onclick="openAssignModal('${ams.id}', ${slotNumber})" style="margin-top: 8px;">
                            + Zuweisen
                        </button>
                    </div>
                `;
            }
        }
        
        slotsContainer.innerHTML = slotsHTML;
    });
}

// === HELPER FUNCTIONS ===
function updateWarningCount() {
    const warningCountEl = document.getElementById('amsWarningCount');
    if (!warningCountEl) return;
    
    // Count warnings
    let warningCount = 0;
    amsData.forEach((ams) => {
        ams.slots.forEach((slot) => {
            if (slot && slot.spool) {
                const remaining = getRemaining(slot.spool);
                const percentage = getPercentage(slot.spool);
                if (percentage <= 20 || remaining < 200) {
                    warningCount++;
                }
            }
        });
    });
    
    warningCountEl.textContent = warningCount;
    
    // Create/update alerts dropdown
    createAlertsDropdown(warningCount);
}

function createAlertsDropdown(warningCount) {
    const alertCard = document.querySelector('.stat-card-alerts');
    if (!alertCard) return;
    
    // Remove existing dropdown
    let dropdown = alertCard.querySelector('.alerts-dropdown');
    if (!dropdown) {
        dropdown = document.createElement('div');
        dropdown.className = 'alerts-dropdown';
        alertCard.appendChild(dropdown);
    }
    
    if (warningCount === 0) {
        dropdown.innerHTML = `
            <div class="alerts-dropdown-header">System Status</div>
            <div class="alerts-dropdown-empty">
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">✅</div>
                Alle Slots haben ausreichend Filament
            </div>
        `;
        return;
    }
    
    // Collect warning items
    const items = [];
    amsData.forEach((ams, i) => {
        ams.slots.forEach((slot, idx) => {
            if (slot && slot.spool) {
                const remaining = getRemaining(slot.spool);
                const percentage = getPercentage(slot.spool);
                if (percentage <= 20 || remaining < 200) {
                    items.push({
                        ams: i + 1,
                        slot: idx + 1,
                        material: slot.material?.name || 'Unbekannt',
                        remaining: Math.round(remaining),
                        percent: Math.round(percentage),
                        spoolId: slot.spool.id,
                    });
                }
            }
        });
    });
    
    dropdown.innerHTML = `
        <div class="alerts-dropdown-header">Niedrige Füllstände</div>
        <div class="alerts-dropdown-list">
            ${items.map(it => `
                <div class="alert-item" onclick="goToSpool('${it.spoolId}')">
                    <div class="alert-dot"></div>
                    <div class="alert-text">AMS #${it.ams} · Slot ${it.slot} · ${it.material}</div>
                    <div class="alert-meta">${it.remaining}g (${it.percent}%)</div>
                </div>
            `).join('')}
        </div>
    `;
}

function renderAlerts() {
    // This function is now integrated into updateWarningCount
    // Keep it for compatibility but it does nothing
}

function getRemaining(spool) {
    const wf = parseFloat(spool.weight_full) || 0;
    const rp = parseFloat(spool.remain_percent);
    
    // Priorität: weight > weight_current > weight_remaining > berechnet aus remain_percent
    const remaining = parseFloat(spool.weight) ?? 
                     parseFloat(spool.weight_current) ?? 
                     parseFloat(spool.weight_remaining) ?? 
                     (rp != null && wf ? (rp / 100) * wf : wf);
    
    return remaining || 0;
}

function getPercentage(spool) {
    const wf = parseFloat(spool.weight_full) || 0;
    const rp = parseFloat(spool.remain_percent);
    
    if (rp != null) {
        return Math.max(0, Math.min(100, rp));
    }
    
    const remaining = getRemaining(spool);
    return wf ? Math.max(0, Math.min(100, (remaining / wf) * 100)) : 0;
}

function goToSpool(spoolId) {
    window.location.href = `/spools?highlight=${spoolId}`;
}

function showNotification(message, type = 'info') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification notification-${type} show`;
    
    setTimeout(() => {
        notification.classList.remove('show');
    }, 3000);
}

// === SLOT ACTIONS ===
function refreshRFID(amsId, slotNumber) {
    showNotification(`RFID-Scan für AMS #${amsId} Slot ${slotNumber} wird ausgeführt...`, 'info');
    // TODO: Backend-Call für RFID-Refresh
    setTimeout(() => {
        showNotification(`RFID erfolgreich aktualisiert`, 'success');
        loadData(); // Refresh data
    }, 1500);
}

function changeSpoolDialog(amsId, slotNumber) {
    const confirmed = confirm(`Spule in AMS #${amsId} Slot ${slotNumber} wechseln?\n\nDies öffnet die Spulenverwaltung.`);
    if (confirmed) {
        window.location.href = '/spools';
    }
}

// === QUICK-ASSIGN SYSTEM ===
let currentAssignPrinter = null;
let currentAssignSlot = null;
let searchTimeout = null;

function openAssignModal(printerId, slotNumber) {
    currentAssignPrinter = printerId;
    currentAssignSlot = slotNumber;

    document.getElementById('assignModalTitle').textContent = `Spule zuweisen - Slot ${slotNumber}`;
    document.getElementById('assignModal').classList.add('show');
    document.getElementById('spoolSearch').value = '';
    document.getElementById('spoolSearch').focus();

    // Initial load: Zeige alle freien Spulen
    searchSpools('');

    // Live-Suche
    document.getElementById('spoolSearch').oninput = (e) => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(() => {
            searchSpools(e.target.value);
        }, 300);
    };
}

function closeAssignModal() {
    document.getElementById('assignModal').classList.remove('show');
    currentAssignPrinter = null;
    currentAssignSlot = null;
}

async function searchSpools(searchTerm) {
    try {
        const response = await fetch('/api/spools/');
        if (!response.ok) throw new Error('Fehler beim Laden der Spulen');

        let allSpools = await response.json();

        // Filtere nur freie Spulen (nicht zugewiesen)
        let availableSpools = allSpools.filter(s => s.printer_id == null && s.ams_slot == null);

        // Suche filtern
        if (searchTerm) {
            const term = searchTerm.toLowerCase();
            availableSpools = availableSpools.filter(s => {
                const num = s.spool_number ? s.spool_number.toString() : '';
                const name = s.name || '';
                const vendor = s.vendor || '';
                const color = s.color || '';

                return num.includes(term) ||
                       name.toLowerCase().includes(term) ||
                       vendor.toLowerCase().includes(term) ||
                       color.toLowerCase().includes(term);
            });
        }

        renderSpoolSearchResults(availableSpools);
    } catch (error) {
        console.error('Fehler bei Spulen-Suche:', error);
        document.getElementById('spoolSearchResults').innerHTML = `
            <div style="padding: 16px; text-align: center; color: var(--error);">
                Fehler beim Laden der Spulen
            </div>
        `;
    }
}

function renderSpoolSearchResults(spools) {
    const container = document.getElementById('spoolSearchResults');

    if (spools.length === 0) {
        container.innerHTML = `
            <div style="
                padding: 40px 24px;
                text-align: center;
                background: var(--panel-2);
                border-radius: 12px;
                border: 2px dashed var(--border);
            ">
                <div style="font-size: 3rem; margin-bottom: 12px; opacity: 0.6;">📭</div>
                <div style="font-weight: 600; font-size: 1.1rem; color: var(--text); margin-bottom: 6px;">
                    Keine freien Spulen gefunden
                </div>
                <div style="font-size: 0.9rem; color: var(--text-dim);">
                    Alle Spulen sind bereits zugewiesen
                </div>
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div style="
            margin-bottom: 16px;
            padding: 10px 12px;
            background: var(--panel-2);
            border-radius: 8px;
            color: var(--text-dim);
            font-size: 0.9rem;
            font-weight: 500;
        ">
            🎯 ${spools.length} ${spools.length === 1 ? 'Spule' : 'Spulen'} verfügbar
        </div>
    ` + spools.map(s => {
        const numberDisplay = s.spool_number ? `#${s.spool_number}` : '–';
        const nameDisplay = s.name || 'Unbekannt';
        const vendorDisplay = s.vendor || '';
        const colorDisplay = s.color && s.color !== 'unknown' ? s.color : '';
        const weightDisplay = s.weight_current ? `${Math.round(s.weight_current)}g` : 'N/A';
        const percentDisplay = s.remain_percent != null ? Math.round(s.remain_percent) + '%' : '';

        // Farb-Badge falls Farbe bekannt
        const colorBadge = colorDisplay ? `<span style="
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: ${colorDisplay};
            border: 1px solid var(--border);
            margin-left: 6px;
            vertical-align: middle;
        "></span>` : '';

        return `
            <div class="spool-search-item" onclick="assignSpool('${s.id}')" style="
                padding: 18px;
                background: var(--panel-2);
                border: 2px solid var(--border);
                border-radius: 12px;
                cursor: pointer;
                margin-bottom: 12px;
                transition: all 0.15s ease;
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
            " onmouseover="this.style.borderColor='var(--accent)'; this.style.background='var(--panel)'; this.style.transform='translateY(-2px)'; this.style.boxShadow='0 4px 16px rgba(243, 156, 18, 0.2)'"
               onmouseout="this.style.borderColor='var(--border)'; this.style.background='var(--panel-2)'; this.style.transform='translateY(0)'; this.style.boxShadow='0 2px 8px rgba(0, 0, 0, 0.2)'">
                <div style="display: flex; justify-content: space-between; align-items: center; gap: 16px;">
                    <div style="flex: 1;">
                        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 8px;">
                            <span style="
                                font-size: 1.5rem;
                                font-weight: 700;
                                color: var(--accent);
                            ">${numberDisplay}</span>
                            ${s.tray_uuid ? '<span style="font-size: 1.1rem;" title="RFID erkannt">🏷️</span>' : ''}
                        </div>
                        <div style="font-weight: 600; color: var(--text); font-size: 1.05rem; margin-bottom: 6px;">
                            ${nameDisplay}
                        </div>
                        ${vendorDisplay || colorDisplay ? `
                            <div style="color: var(--text-secondary); font-size: 0.875rem; display: flex; align-items: center; gap: 4px;">
                                ${vendorDisplay}
                                ${colorDisplay ? `<span>${colorDisplay}${colorBadge}</span>` : ''}
                            </div>
                        ` : ''}
                    </div>
                    <div style="text-align: right; min-width: 90px;">
                        <div style="font-weight: 700; font-size: 1.25rem; color: var(--text);">
                            ${weightDisplay}
                        </div>
                        ${percentDisplay ? `
                            <div style="
                                font-size: 0.9rem;
                                color: var(--accent-2);
                                margin-top: 4px;
                                font-weight: 600;
                            ">
                                ${percentDisplay}
                            </div>
                        ` : ''}
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

async function assignSpool(spoolId) {
    try {
        const response = await fetch(
            `/api/spools/${spoolId}/assign?printer_id=${currentAssignPrinter}&slot_number=${currentAssignSlot}`,
            { method: 'POST' }
        );

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Zuweisung fehlgeschlagen');
        }

        const result = await response.json();

        showNotification(
            `Spule ${result.spool_number ? '#' + result.spool_number : ''} zu Slot ${currentAssignSlot} zugewiesen`,
            'success'
        );

        closeAssignModal();
        loadData(); // Refresh AMS view
    } catch (error) {
        console.error('Fehler bei Zuweisung:', error);
        showNotification(error.message, 'error');
    }
}

// Confirm Unassign Modal
let pendingUnassignSpoolId = null;

function unassignSpool(spoolId) {
    // Finde Spule für Anzeige im Modal
    const spool = spools.find(s => s.id === spoolId);
    const spoolName = spool ? (spool.spool_number ? `#${spool.spool_number}` : spool.name || 'diese Spule') : 'diese Spule';

    document.getElementById('confirmSpoolName').textContent = spoolName;
    pendingUnassignSpoolId = spoolId;
    document.getElementById('confirmUnassignModal').classList.add('show');
}

function closeConfirmUnassignModal() {
    document.getElementById('confirmUnassignModal').classList.remove('show');
    pendingUnassignSpoolId = null;
}

async function confirmUnassignSpool() {
    if (!pendingUnassignSpoolId) return;

    const spoolId = pendingUnassignSpoolId;
    closeConfirmUnassignModal();

    try {
        const response = await fetch(`/api/spools/${spoolId}/unassign`, {
            method: 'POST'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Entfernen fehlgeschlagen');
        }

        const result = await response.json();

        showNotification(
            `Spule ${result.spool_number ? '#' + result.spool_number : ''} entfernt`,
            'success'
        );

        loadData(); // Refresh AMS view
    } catch (error) {
        console.error('Fehler beim Entfernen:', error);
        showNotification(error.message, 'error');
    }
}

// Close modal on ESC
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeAssignModal();
        closeConfirmUnassignModal();
    }
});

// Close modal on background click
document.getElementById('assignModal').addEventListener('click', (e) => {
    if (e.target.id === 'assignModal') {
        closeAssignModal();
    }
});

document.getElementById('confirmUnassignModal').addEventListener('click', (e) => {
    if (e.target.id === 'confirmUnassignModal') {
        closeConfirmUnassignModal();
    }
});
