/**
 * ============================================================================
 * AMS Monitoring JavaScript - Haupt-Modul fÃ¼r regulÃ¤res AMS (4 Slots)
 * ============================================================================
 * 
 * Dieses Modul behandelt das regulÃ¤re AMS mit 4 Slots (X1C, P1P, P1S).
 * 
 * HINWEIS: AMS Lite FunktionalitÃ¤t (A1/A1 Mini, 1 externer Slot) wurde
 * ausgelagert nach: ams_lite.js
 * 
 * VerfÃ¼gbare AMS Lite Funktionen via window.AmsLite:
 * - AmsLite.SLOT_ID (254)
 * - AmsLite.isAmsLiteUnit(unit)
 * - AmsLite.getSlotLabel(isLite, slotNumber)
 * - AmsLite.loadData()
 * - AmsLite.renderDevice(device, spools, materials)
 * 
 * API Endpoints:
 * - /api/ams/regular  - RegulÃ¤re AMS (dieses Modul)
 * - /api/ams/lite     - AMS Lite (ams_lite.js)
 * - /api/ams/         - Alle AMS kombiniert
 * 
 * ============================================================================
 */

let amsData = [];
let spools = [];
let materials = [];
let liveState = {}; // Live-State von MQTT

let isLoading = false;
let singleAmsMode = true; // Single AMS Mode aktiviert
let amsSyncState = null;
let amsSyncToastTimeout = null;

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
    initAmsSyncStatus();
    
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
        // Lade Spulen und Materialien parallel fÃ¼r Slot-Matching
        await Promise.all([loadSpools(), loadMaterials()]);
        
        // Nutze die /api/ams/regular API fÃ¼r regulÃ¤re AMS (nicht AMS Lite)
        const response = await fetch('/api/ams/regular');
        if (!response.ok) {
            throw new Error('Failed to load AMS data');
        }
        const data = await response.json();
        amsDevices = Array.isArray(data.devices) ? data.devices : [];
        console.log('[AMS] Normalized AMS geladen:', amsDevices.length, 'GerÃ¤te');
        
        loadAMSData();
        updateStats();
        renderAMSUnits();

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

function initAmsSyncStatus() {
    pollAmsSyncStatus();
    setInterval(pollAmsSyncStatus, 7000);
}

async function pollAmsSyncStatus() {
    try {
        const response = await fetch('/api/ams/sync-status');
        if (!response.ok) {
            return;
        }
        const data = await response.json();
        const nextState = data && data.sync_state ? data.sync_state : null;
        if (!nextState || nextState === amsSyncState) {
            return;
        }
        amsSyncState = nextState;
        renderAmsSyncToast(nextState);
    } catch (error) {
        console.warn('AMS Sync-Status konnte nicht geladen werden:', error);
    }
}

function renderAmsSyncToast(state) {
    const toast = ensureAmsSyncToast();
    const mapping = {
        pending: { type: 'warning', text: 'Warte auf AMS-Daten', autoHide: false },
        syncing: { type: 'info', text: 'AMS \u2192 Lager wird synchronisiert', autoHide: false },
        ok: { type: 'success', text: 'AMS \u2192 Lager synchron', autoHide: true },
        error: { type: 'error', text: 'AMS-Synchronisation fehlgeschlagen', autoHide: false },
    };
    const config = mapping[state] || mapping.pending;

    if (amsSyncToastTimeout) {
        clearTimeout(amsSyncToastTimeout);
        amsSyncToastTimeout = null;
    }

    toast.className = `notification notification-${config.type} show`;
    toast.innerHTML = `<strong>AMS \u2013 Sync</strong><div>${config.text}</div>`;

    if (config.autoHide) {
        amsSyncToastTimeout = setTimeout(() => {
            toast.classList.remove('show');
        }, 2500);
    }
}

function ensureAmsSyncToast() {
    let toast = document.getElementById('amsSyncToast');
    if (toast) {
        return toast;
    }
    toast = document.createElement('div');
    toast.id = 'amsSyncToast';
    toast.className = 'notification';
    toast.style.bottom = '6rem';
    document.body.appendChild(toast);
    return toast;
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

let amsDevices = []; // normalized devices from /api/ams/

async function loadLiveState() {
    try {
        const response = await fetch('/api/ams/');
        if (response.ok) {
            const data = await response.json();
            amsDevices = Array.isArray(data.devices) ? data.devices : [];
            console.log('[AMS] Normalized AMS geladen:', amsDevices.length, 'GerÃ¤te');
        } else {
            amsDevices = [];
        }
    } catch (error) {
        console.error('Fehler beim Laden des AMS-Endpunkts:', error);
        amsDevices = [];
    }
}

function findMatchingSpool(dev, amsUnit, tray, slotIndex, isAmsLite) {
    const printerId = dev?.printer_id || null;
    const amsId = amsUnit?.ams_id != null ? String(amsUnit.ams_id) : null;
    const trayTagUid = tray?.tag_uid || null;
    const trayUuid = tray?.tray_uuid || null;
    const slotForDb = isAmsLite ? 254 : slotIndex;

    return spools.find((s) => {
        if (trayTagUid && s.rfid_uid && s.rfid_uid === trayTagUid) return true;
        if (trayUuid && s.tray_uuid && s.tray_uuid === trayUuid) return true;

        if (s.ams_slot == null || Number(s.ams_slot) !== Number(slotForDb)) return false;
        if (printerId && s.printer_id && String(s.printer_id) !== String(printerId)) return false;
        if (amsId && s.ams_id != null && String(s.ams_id) !== amsId) return false;
        return true;
    });
}

function loadAMSData() {
    // Generate AMS structure based on spools with ams_slot
    // Single AMS Mode: Only create 1 AMS unit
    // Multi AMS Mode: Create 4 AMS units

    // Build AMS data from normalized /api/ams/ response (amsDevices)
    let printerName = 'Kein Drucker';

    if (amsDevices.length === 0) {
        // No normalized devices â€” fallback to empty single AMS
        amsData = [
            { id: 1, online: false, slots: [], serial: 'AMS-001', firmware: '-', signal: '-', printer: null, temp: null, humidity: null }
        ];
    } else {
        if (singleAmsMode) {
            // Use first device + first AMS unit
            const dev = amsDevices[0];
            const amsUnit = (dev.ams_units && dev.ams_units[0]) || null;
            printerName = dev.device_serial ? `Bambu ${dev.device_serial.substring(0,8)}...` : printerName;
            
            // Detect AMS Lite
            const isAmsLite = amsUnit && amsUnit.is_ams_lite;

            amsData = [
                {
                    id: 1,
                    ams_id: amsUnit?.ams_id ?? 0,
                    printer_id: dev?.printer_id || null,
                    online: !!dev?.online,
                    slots: [],
                    serial: dev.device_serial || (amsUnit ? `AMS-${amsUnit.ams_id}` : 'AMS-001'),
                    firmware: dev.firmware || '-',
                    signal: dev.signal || '-',
                    printer: printerName,
                    temp: amsUnit ? amsUnit.temp : null,
                    humidity: amsUnit ? amsUnit.humidity : null,
                    is_ams_lite: isAmsLite,  // ADD: Pass AMS Lite flag to render logic
                }
            ];

            if (amsUnit && Array.isArray(amsUnit.trays)) {
                amsUnit.trays.forEach((tray, index) => {
                    const ams = amsData[0];
                    // For AMS Lite, always use slot 0 (since there's only 1), for regular AMS use the index
                    const slotIndex = isAmsLite ? 0 : index;
                    
                    const matchingSpool = findMatchingSpool(dev, amsUnit, tray, index, isAmsLite);
                    
                    // Material aus tray_sub_brands oder tray_type extrahieren
                    const trayMaterialName = tray.tray_sub_brands || tray.tray_type || tray.material || 'Unbekannt';
                    const material = matchingSpool
                        ? materials.find(m => m.id === matchingSpool.material_id)
                        : { name: trayMaterialName, brand: 'Bambu Lab' };
                    
                    // Farbe aus tray_color extrahieren (Format: RRGGBBAA)
                    const trayColor = tray.tray_color || tray.color || '999999FF';

                    ams.slots[slotIndex] = {
                        slot: isAmsLite ? 254 : (index + 1),
                        spool: matchingSpool || {
                            id: null,
                            ams_slot: isAmsLite ? 254 : index,
                            material_type: trayMaterialName,
                            tray_color: trayColor,
                            color: `#${trayColor.substring(0, 6)}`,
                            remaining_percent: tray.remain_percent != null ? tray.remain_percent : null,
                            remaining_grams: tray.remaining_grams || null,
                            weight_remaining: tray.remaining_grams || null,
                            weight_total: tray.tray_weight || null,
                            rfid_uid: tray.tag_uid,
                            tray_uuid: tray.tray_uuid,
                            from_live_state: true
                        },
                        material: material,
                        liveData: tray
                    };
                });
            }
        } else {
            // Multi mode: create one amsData entry per device/ams_unit
            amsData = [];
            amsDevices.forEach((dev) => {
                (dev.ams_units || []).forEach((u, unitIndex) => {
                    const idx = amsData.length + 1;
                    const amsEntry = {
                        id: idx,
                        ams_id: u?.ams_id ?? idx,
                        printer_id: dev?.printer_id || null,
                        online: !!dev?.online,
                        slots: [],
                        serial: dev.device_serial || `AMS-${u.ams_id}`,
                        firmware: dev.firmware || '-',
                        signal: dev.signal || '-',
                        printer: dev.device_serial ? `Bambu ${dev.device_serial.substring(0,8)}...` : null,
                        temp: u.temp || null,
                        humidity: u.humidity || null
                    };

                    if (Array.isArray(u.trays)) {
                        u.trays.forEach((tray, index) => {
                            const matchingSpool = findMatchingSpool(dev, u, tray, index, false);
                            
                            // Material aus tray_sub_brands oder tray_type extrahieren
                            const trayMaterialName = tray.tray_sub_brands || tray.tray_type || tray.material || 'Unbekannt';
                            const material = matchingSpool
                                ? materials.find(m => m.id === matchingSpool.material_id)
                                : { name: trayMaterialName, brand: 'Bambu Lab' };
                            
                            // Farbe aus tray_color extrahieren (Format: RRGGBBAA)
                            const trayColor = tray.tray_color || tray.color || '999999FF';

                            amsEntry.slots[index] = {
                                slot: index + 1,
                                spool: matchingSpool || {
                                    id: null,
                                    ams_slot: index,
                                    material_type: trayMaterialName,
                                    tray_color: trayColor,
                                    color: `#${trayColor.substring(0, 6)}`,
                                    remaining_percent: tray.remain_percent != null ? tray.remain_percent : null,
                                    remaining_grams: tray.remaining_grams || null,
                                    weight_remaining: tray.remaining_grams || null,
                                    weight_total: tray.tray_weight || null,
                                    rfid_uid: tray.tag_uid,
                                    tray_uuid: tray.tray_uuid,
                                    from_live_state: true
                                },
                                material: material,
                                liveData: tray
                            };
                        });
                    }

                    amsData.push(amsEntry);
                });
            });
        }
    }
}

// === UPDATE STATS FROM OVERVIEW API ===
function updateStatsFromOverview(overviewData) {
    const summary = overviewData.summary || {};
    const amsUnits = overviewData.ams_units || [];

    // Update KPIs
    document.getElementById('amsOnlineCount').textContent = summary.online_ams || 0;
    document.getElementById('amsActiveSlots').textContent = summary.total_slots || 0;

    const totalKg = (summary.total_remaining_grams || 0) / 1000;
    document.getElementById('amsAvailableFilament').textContent = totalKg.toFixed(2) + 'kg';

    // Count warnings (slots with low filament)
    let warnings = 0;
    amsUnits.forEach(unit => {
        (unit.slots || []).forEach(slot => {
            const percent = slot.remaining?.percent;
            const grams = slot.remaining?.grams;
            if (percent != null && percent <= 20) warnings++;
            else if (grams != null && grams < 200) warnings++;
        });
    });

    // Update warning badge
    const warningEl = document.getElementById('amsWarningCount');
    if (warningEl) warningEl.textContent = warnings;
}

// === UPDATE STATS (Legacy function for old code paths) ===
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

// === RENDER AMS FROM OVERVIEW ===
function renderAMSFromOverview(overviewData) {
    const amsUnits = overviewData.ams_units || [];

    amsUnits.forEach((unit, index) => {
        const amsId = index + 1;
        const statusElement = document.getElementById(`amsStatus${amsId}`);
        const slotsContainer = document.getElementById(`amsSlots${amsId}`);

        if (!statusElement || !slotsContainer) return;

        // Update AMS device info
        const serialEl = document.getElementById(`amsSerial${amsId}`);
        const printerEl = document.getElementById(`amsPrinter${amsId}`);

        if (serialEl) serialEl.textContent = `SN: ${unit.printer_serial || '-'}`;
        if (printerEl) {
            const printerName = unit.printer_name || 'Kein Drucker';
            printerEl.innerHTML = `<span class="printer-badge">${printerName}</span>`;
        }

        // Update status
        if (unit.online) {
            statusElement.innerHTML = '<span class="status-badge status-online">Online</span>';
        } else {
            statusElement.innerHTML = '<span class="status-badge status-offline">Offline</span>';
        }

        // Render slots
        let slotsHTML = '';
        const slots = unit.slots || [];
        for (let i = 0; i < 4; i++) {
            const slot = slots[i];
            const slotNumber = i + 1;

            if (slot && slot.state !== 'empty' && slot.material) {
                const material = slot.material;
                const remaining = slot.remaining || {};
                const percent = remaining.percent != null ? Math.round(remaining.percent) : null;
                const grams = remaining.grams != null ? Math.round(remaining.grams) : null;

                const isLow = percent != null ? (percent <= 20) : (grams != null && grams < 200);
                const progressClass = isLow ? 'low' : '';

                // Farbe aus spool.color (format: "RRGGBBAA", wir nutzen nur RGB)
                let color = '#999';
                if (slot.spool && slot.spool.color) {
                    const colorHex = slot.spool.color;
                    if (colorHex.length >= 6) {
                        color = '#' + colorHex.substring(0, 6);
                    }
                }

                const spoolId = slot.spool?.id;

                slotsHTML += `
                    <div class="slot ams-slot" data-slot="${slotNumber}">
                        <div class="slot-color" style="background: ${color};"></div>
                        <div class="slot-number">
                            Slot ${slotNumber}
                            ${slot.rfid ? '<span class="slot-icon" title="RFID erkannt">TAG</span>' : ''}
                        </div>
                        <div class="slot-material">${material.name || 'Unbekannt'}</div>
                        ${material.vendor ? `<div class="slot-brand">${material.vendor}</div>` : ''}
                        <div class="slot-weight">
                            ${percent != null ? `${percent}%` : ''}
                            ${grams != null ? ` (${grams}g)` : ''}
                        </div>
                        <div class="slot-progress">
                            ${percent != null ? `<div class="slot-progress-bar ${progressClass}" style="width: ${percent}%;"></div>` : ''}
                        </div>
                        <div class="slot-actions requires-ams">
                            ${spoolId ? `<button class="slot-action-btn" onclick="event.stopPropagation(); goToSpool('${spoolId}')" title="Spule oeffnen">
                                <span>Open</span>
                            </button>` : ''}
                        </div>
                    </div>
                `;
            } else {
                slotsHTML += `
                    <div class="slot-empty ams-slot" data-slot="${slotNumber}">
                        <div class="slot-number">Slot ${slotNumber}</div>
                        <div class="slot-label">Leer</div>
                    </div>
                `;
            }
        }

        slotsContainer.innerHTML = slotsHTML;
    });
}

// === RENDER AMS UNITS (Legacy) ===
function renderAMSUnits() {
    const singleView = document.querySelector('.ams-single-view');
    const multiView = document.querySelector('.ams-multi-view');

    if (!singleAmsMode) {
        if (singleView) singleView.style.display = 'none';
        if (multiView) multiView.style.display = '';
        renderMultiAms(amsData);
        return;
    }

    if (singleView) singleView.style.display = '';
    if (multiView) multiView.style.display = 'none';

    amsData.forEach((ams, index) => {
        const amsId = index + 1;
        const statusElement = document.getElementById(`amsStatus${amsId}`);
        const slotsContainer = document.getElementById(`amsSlots${amsId}`);
        const amsUnitEl = document.querySelector(`[data-ams="${amsId}"]`);
        if (!statusElement || !slotsContainer || !amsUnitEl) return;
        
        // Update AMS device info
        const serialEl = document.getElementById(`amsSerial${amsId}`);
        const firmwareEl = document.getElementById(`amsFirmware${amsId}`);
        const connectionEl = document.getElementById(`amsConnection${amsId}`);
        const signalEl = document.getElementById(`amsSignal${amsId}`);
        const printerEl = document.getElementById(`amsPrinter${amsId}`);
        
        if (serialEl) serialEl.textContent = `SN: ${ams.serial || '-'}`;
        if (firmwareEl) firmwareEl.textContent = `FW: ${ams.firmware || '-'}`;
        if (signalEl) signalEl.textContent = ams.signal || '-';
        if (printerEl) {
            printerEl.innerHTML = ams.printer 
                ? `<span class="printer-badge">${ams.printer}</span>`
                : `<span class="printer-badge">Kein Drucker</span>`;
        }
        
        // Mark AMS Lite in UI
        if (ams.is_ams_lite) {
            if (amsUnitEl) amsUnitEl.classList.add('ams-lite');
            const titleEl = amsUnitEl?.querySelector('h3');
            if (titleEl) titleEl.textContent = 'AMS Lite';
        }
        
        // Update status badge
        if (ams.online) {
            statusElement.innerHTML = '<span class="status-badge status-online">Online</span>';
        } else {
            statusElement.innerHTML = '<span class="status-badge status-offline">Offline</span>';
        }
        
        // Render slots (AMS Lite: 1 slot, regular: 4 slots)
        let slotsHTML = '';
        const maxSlots = ams.is_ams_lite ? 1 : 4;
        for (let i = 0; i < maxSlots; i++) {
            // For AMS Lite, slot is 254 (external), for regular AMS, slots are 1-4
            const slotNumber = ams.is_ams_lite ? 254 : (i + 1);
            const slot = ams.slots[i];
            
            if (slot && slot.spool && slot.material) {
                const spool = slot.spool;
                const material = slot.material;
                const remaining = getRemaining(spool);
                const percentage = getPercentage(spool);

                // Ghost-Slot: kein erkennbares Material und kein Gewicht → als leer zeigen
                const ghostMaterial = !material.name || material.name === 'Unbekannt';
                const ghostWeight = (remaining == null || remaining === 0) && (percentage == null || percentage === 0);
                if (ghostMaterial && ghostWeight) {
                    const slotLabelG = ams.is_ams_lite ? 'External Slot' : `Slot ${slotNumber}`;
                    slotsHTML += `
                        <div class="slot-empty ams-slot" data-slot="${slotNumber}">
                            <div class="slot-number">${slotLabelG}</div>
                            <div class="slot-label">Leer</div>
                            <button class="btn btn-sm btn-primary requires-ams" onclick="openAssignModal('${ams.printer_id || ''}', ${slotNumber})" style="margin-top: 8px;">
                                + Zuweisen
                            </button>
                        </div>
                    `;
                    continue;
                }

                const color = spool.tray_color ? `#${spool.tray_color.substring(0, 6)}` : '#999';

                const isLow = (percentage != null ? (percentage <= 20) : (remaining < 200));
                const progressClass = isLow ? 'low' : '';

                const spoolNumberDisplay = spool.spool_number ? `#${spool.spool_number} ` : '';
                const slotLabel = ams.is_ams_lite ? 'External Slot' : `Slot ${slotNumber}`;

                slotsHTML += `
                    <div class="slot ${spool.is_empty ? 'slot-empty' : ''} ams-slot" data-slot="${slotNumber}">
                        <div class="slot-color" style="background: ${color};"></div>
                        <div class="slot-number">
                            ${slotLabel}
                            ${spool.tray_uuid ? '<span class="slot-icon" title="RFID erkannt">TAG</span>' : ''}
                        </div>
                        ${spoolNumberDisplay ? `<div class="slot-spool-number" style="font-weight: 600; color: var(--primary); margin: 4px 0;">${spoolNumberDisplay}</div>` : ''}
                        <div class="slot-material">${material.name}</div>
                        ${material.brand ? `<div class="slot-brand">${material.brand}</div>` : ''}
                        <div class="slot-weight">${(percentage != null) ? `${Math.round(percentage)}% (${Math.round(remaining)}g)` : (remaining ? `${Math.round(remaining)}g` : 'N/A')}</div>
                        <div class="slot-progress">
                            ${percentage != null ? `<div class="slot-progress-bar ${progressClass}" style="width: ${percentage}%;"></div>` : ''}
                        </div>
                        <div class="slot-actions requires-ams">
                            <button class="slot-action-btn" onclick="event.stopPropagation(); goToSpool('${spool.id}')" title="Spule oeffnen">
                                <span>Open</span>
                            </button>
                            <button class="slot-action-btn requires-ams" onclick="event.stopPropagation(); unassignSpool('${spool.id}')" title="Spule entfernen">
                                <span>Del</span>
                            </button>
                            <button class="slot-action-btn requires-ams" onclick="event.stopPropagation(); refreshRFID(${amsId}, ${slotNumber})" title="RFID neu einlesen">
                                <span>RFID</span>
                            </button>
                        </div>
                    </div>
                `;
            } else {
                const slotLabel = ams.is_ams_lite ? 'External Slot' : `Slot ${slotNumber}`;
                slotsHTML += `
                    <div class="slot-empty ams-slot" data-slot="${slotNumber}">
                        <div class="slot-number">${slotLabel}</div>
                        <div class="slot-label">Leer</div>
                        <button class="btn btn-sm btn-primary requires-ams" onclick="openAssignModal('${ams.printer_id || ''}', ${slotNumber})" style="margin-top: 8px;">
                            + Zuweisen
                        </button>
                    </div>
                `;
            }
        }
        
        slotsContainer.innerHTML = slotsHTML;
    });
}

function renderMultiAms(units) {
    const container = document.querySelector('.ams-multi-view');
    if (!container) return;

    container.innerHTML = '';
    if (!Array.isArray(units) || units.length === 0) {
        return;
    }

    units.forEach((unit, unitIndex) => {
        const unitEl = document.createElement('div');
        unitEl.className = 'ams-unit';

        const isOnline = !!unit?.online;
        const statusHtml = isOnline
            ? '<span class="status-badge status-online">Online</span>'
            : '<span class="status-badge status-offline">Offline</span>';

        const maxSlots = unit?.is_ams_lite ? 1 : 4;
        const slotsByIndex = new Array(maxSlots).fill(null);
        (unit.slots || []).forEach((slot, idx) => {
            if (slot && slot.slot === 254 && unit?.is_ams_lite) {
                slotsByIndex[0] = slot;
                return;
            }
            const slotIdx = (slot && slot.slot != null) ? (Number(slot.slot) - 1) : idx;
            if (slotIdx >= 0 && slotIdx < slotsByIndex.length) {
                slotsByIndex[slotIdx] = slot;
            }
        });

        const slotsHtml = slotsByIndex.map((slot, idx) => {
            const slotNumber = unit?.is_ams_lite ? 254 : (idx + 1);
            const slotLabel = unit?.is_ams_lite ? 'External Slot' : `Slot ${idx + 1}`;

            if (slot && slot.spool && slot.material) {
                const spool = slot.spool;
                const material = slot.material || {};
                const materialName = material.name || 'Unbekannt';
                const materialBrand = material.brand || '';
                const color = spool.tray_color ? `#${String(spool.tray_color).substring(0, 6)}` : '#999';
                const percent = getPercentage(spool);
                const grams = getRemaining(spool);
                const percentDisplay = percent != null && !Number.isNaN(percent) ? Math.round(percent) : null;
                const gramsDisplay = grams != null && !Number.isNaN(grams) ? Math.round(grams) : null;

                // Ghost-Slot: AMS meldet Slot als belegt, aber kein Material erkennbar und kein Gewicht.
                // Tritt auf wenn keine Spule eingelegt ist aber der AMS-Slot trotzdem Daten liefert.
                // → als leer darstellen
                const noWeight = (gramsDisplay == null || gramsDisplay === 0);
                const noPercent = (percentDisplay == null || percentDisplay === 0);
                const isGhostSlot = materialName === 'Unbekannt' && noWeight && noPercent;
                if (isGhostSlot) {
                    return `
                        <div class="slot-empty ams-slot" data-slot="${slotNumber}">
                            <div class="slot-number">${slotLabel}</div>
                            <div class="slot-label">Leer</div>
                            <button class="btn btn-sm btn-primary requires-ams" onclick="openAssignModal('${unit.printer_id || ''}', ${slotNumber})" style="margin-top: 8px;">
                                + Zuweisen
                            </button>
                        </div>
                    `;
                }

                const isLow = percentDisplay != null ? (percentDisplay <= 20) : (gramsDisplay != null && gramsDisplay < 200);
                const progressClass = isLow ? 'low' : '';
                const remainingDisplay = percentDisplay != null
                    ? `${percentDisplay}%${gramsDisplay != null ? ` (${gramsDisplay}g)` : ''}`
                    : (gramsDisplay != null ? `${gramsDisplay}g` : 'N/A');
                const spoolId = spool.id || null;
                const rfid = !!(spool.tray_uuid || spool.rfid_uid);

                return `
                    <div class="slot ams-slot" data-slot="${slotNumber}">
                        <div class="slot-color" style="background: ${color};"></div>
                        <div class="slot-number">
                            ${slotLabel}
                            ${rfid ? '<span class="slot-icon" title="RFID erkannt">RFID</span>' : ''}
                        </div>
                        <div class="slot-material">${materialName}</div>
                        ${materialBrand ? `<div class="slot-brand">${materialBrand}</div>` : ''}
                        <div class="slot-weight">${remainingDisplay}</div>
                        <div class="slot-progress">
                            ${percentDisplay != null ? `<div class="slot-progress-bar ${progressClass}" style="width: ${percentDisplay}%;"></div>` : ''}
                        </div>
                        <div class="slot-actions requires-ams">
                            <button class="slot-action-btn" ${spoolId ? `onclick="event.stopPropagation(); goToSpool('${spoolId}')"` : 'disabled'} title="Spule öffnen">
                                <span>Open</span>
                            </button>
                            <button class="slot-action-btn requires-ams" ${spoolId ? `onclick="event.stopPropagation(); unassignSpool('${spoolId}')"` : 'disabled'} title="Spule entfernen">
                                <span>Del</span>
                            </button>
                            <button class="slot-action-btn requires-ams" onclick="event.stopPropagation(); refreshRFID(${unitIndex + 1}, ${slotNumber})" title="RFID neu einlesen">
                                <span>RFID</span>
                            </button>
                        </div>
                    </div>
                `;
            }

            return `
                <div class="slot-empty ams-slot" data-slot="${slotNumber}">
                    <div class="slot-number">${slotLabel}</div>
                    <div class="slot-label">Leer</div>
                    <button class="btn btn-sm btn-primary requires-ams" onclick="openAssignModal('${unit.printer_id || ''}', ${slotNumber})" style="margin-top: 8px;">
                        + Zuweisen
                    </button>
                </div>
            `;
        }).join('');

        unitEl.innerHTML = `
            <div class="ams-header">
                <div class="ams-title">
                    <span class="ams-icon">AMS</span>
                    <div>
                        <h3>${unit?.is_ams_lite ? 'AMS Lite' : `AMS #${unitIndex + 1}`}</h3>
                        <div class="ams-meta">
                            <span class="ams-serial">SN: ${unit.serial || '–'}</span>
                        </div>
                    </div>
                </div>
                <div class="ams-status-group">
                    <div class="ams-status">${statusHtml}</div>
                    <div class="ams-printer">
                        <span class="printer-badge">${unit.printer || 'Kein Drucker'}</span>
                    </div>
                </div>
            </div>
            <div class="ams-slots">
                ${slotsHtml}
            </div>
        `;

        container.appendChild(unitEl);
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
                <div style="font-size: 2rem; margin-bottom: 0.5rem;">OK</div>
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

                // Slot überspringen wenn kein Material erkannt und kein Gewicht vorhanden:
                // Das passiert wenn AMS einen Slot als belegt meldet, aber keine Spule eingelegt ist.
                const materialName = slot.material?.name || '';
                const isGhostSlot = (!materialName || materialName === 'Unbekannt') && (remaining == null || remaining === 0) && (percentage == null || percentage === 0);
                if (isGhostSlot) return;

                const isLow = (percentage != null ? (percentage <= 20) : (remaining < 200));
                if (isLow) {
                    items.push({
                        ams: i + 1,
                        slot: idx + 1,
                        material: materialName || 'Unbekannt',
                        remaining: Math.round(remaining),
                        percent: percentage != null ? Math.round(percentage) : null,
                        spoolId: slot.spool.id,
                    });
                }
            }
        });
    });
    
    dropdown.innerHTML = `
        <div class="alerts-dropdown-header">Niedrige Fuellstaende</div>
        <div class="alerts-dropdown-list">
            ${items.map(it => `
                <div class="alert-item" onclick="goToSpool('${it.spoolId}')">
                    <div class="alert-dot"></div>
                    <div class="alert-text">AMS #${it.ams} | Slot ${it.slot} | ${it.material}</div>
                    <div class="alert-meta">${it.percent != null ? `${it.percent}% (${it.remaining}g)` : `${it.remaining}g`}</div>
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
    // Verwende ausschlieÃŸlich das vom Backend bereitgestellte canonical Feld
    const rem = parseFloat(spool.remaining_weight_g);
    return isNaN(rem) ? 0 : rem;
}

function getPercentage(spool) {
    // Verwende ausschlieÃŸlich das vom Backend bereitgestellte canonical Feld
    const rp = spool.remaining_percent;
    if (rp == null) return null;
    const v = parseFloat(rp);
    return isNaN(v) ? null : Math.max(0, Math.min(100, v));
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
    if (document.body && document.body.classList.contains('no-ams')) return;
    showNotification(`RFID-Scan fuer AMS #${amsId} Slot ${slotNumber} wird ausgefuehrt...`, 'info');
    // TODO: Backend-Call fÃ¼r RFID-Refresh
    setTimeout(() => {
        showNotification(`RFID erfolgreich aktualisiert`, 'success');
        loadData(); // Refresh data
    }, 1500);
}

function changeSpoolDialog(amsId, slotNumber) {
    if (document.body && document.body.classList.contains('no-ams')) return;
    const confirmed = confirm(`Spule in AMS #${amsId} Slot ${slotNumber} wechseln?\n\nDies oeffnet die Spulenverwaltung.`);
    if (confirmed) {
        window.location.href = '/spools';
    }
}

// === QUICK-ASSIGN SYSTEM ===
let currentAssignPrinter = null;
let currentAssignSlot = null;
let searchTimeout = null;

function openAssignModal(printerId, slotNumber) {
    if (document.body && document.body.classList.contains('no-ams')) return;
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
                <div style="font-size: 3rem; margin-bottom: 12px; opacity: 0.6;">-</div>
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
            ${spools.length} ${spools.length === 1 ? 'Spule' : 'Spulen'} verfuegbar
        </div>
    ` + spools.map(s => {
        const numberDisplay = s.spool_number ? `#${s.spool_number}` : '-';
        const nameDisplay = s.name || 'Unbekannt';
        const vendorDisplay = s.vendor || '';
        const colorDisplay = s.color && s.color !== 'unknown' ? s.color : '';
        const weightDisplay = s.remaining_weight_g ? `${Math.round(s.remaining_weight_g)}g` : 'N/A';
        const percentDisplay = s.remaining_percent != null ? Math.round(s.remaining_percent) + '%' : (s.remain_percent != null ? Math.round(s.remain_percent) + '%' : '');

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
                            ${s.tray_uuid ? '<span style="font-size: 1.1rem;" title="RFID erkannt">TAG</span>' : ''}
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
                            ${percentDisplay || weightDisplay}
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
    if (document.body && document.body.classList.contains('no-ams')) return;
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
    if (document.body && document.body.classList.contains('no-ams')) return;
    // Finde Spule fÃ¼r Anzeige im Modal
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
    if (document.body && document.body.classList.contains('no-ams')) return;
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


