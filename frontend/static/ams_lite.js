/**
 * ============================================================================
 * AMS LITE - Dedicated Module for A1/A1 Mini External Spool Handling
 * ============================================================================
 * 
 * AUSGELAGERT aus ams.js am 16.01.2026
 * 
 * Dieses Modul behandelt speziell die AMS Lite Funktionalität:
 * - A1 Mini hat AMS Lite (1 externer Slot, Slot-ID = 254)
 * - X1C/P1P/P1S haben reguläres AMS (4 Slots, Slot-IDs = 0-3)
 * 
 * API Endpoints:
 * - /api/ams/lite     - Nur AMS Lite Einheiten
 * - /api/ams/regular  - Nur reguläre AMS Einheiten (in ams.js verwendet)
 * - /api/ams/         - Alle AMS Einheiten kombiniert
 * 
 * Slot-Konventionen:
 * - AMS Lite: slot = 254 (externer Filament-Halter)
 * - AMS Regular: slot = 0-3 (interne AMS Slots)
 * 
 * ============================================================================
 */

// AMS Lite Daten (separat von regulärem AMS)
let amsLiteDevices = [];

// === KONSTANTEN ===
const AMS_LITE_SLOT_ID = 254;  // Externe Spule bei A1/A1 Mini
const AMS_LITE_MAX_SLOTS = 4;  // AMS Lite hat nur 1 Slot

// === HELPER FUNKTIONEN ===

/**
 * Prüft ob ein AMS-Unit ein AMS Lite ist
 */
function isAmsLiteUnit(amsUnit) {
    return amsUnit && amsUnit.is_ams_lite === true;
}

/**
 * Gibt die Slot-ID für einen Index zurück
 * @param {boolean} isLite - Ist es ein AMS Lite?
 * @param {number} index - Der Slot-Index
 * @returns {number} Die Slot-ID (254 für AMS Lite, sonst index+1)
 */
function getSlotId(isLite, index) {
    return isLite ? AMS_LITE_SLOT_ID : (index + 1);
}

/**
 * Gibt das Label für einen Slot zurück
 * @param {boolean} isLite - Ist es ein AMS Lite?
 * @param {number} slotNumber - Die Slot-Nummer
 * @returns {string} Das Label (z.B. "⚪ External Slot" oder "Slot 1")
 */
function getSlotLabel(isLite, slotNumber) {
    return isLite ? '⚪ External Slot' : `Slot ${slotNumber}`;
}

/**
 * Gibt die maximale Slot-Anzahl zurück
 * @param {boolean} isLite - Ist es ein AMS Lite?
 * @returns {number} Anzahl der Slots (1 für AMS Lite, 4 für reguläres AMS)
 */
function getMaxSlots(isLite) {
    return isLite ? AMS_LITE_MAX_SLOTS : 4;
}

// === DATEN LADEN ===

/**
 * Lädt AMS Lite Daten von der API
 */
async function loadAmsLiteData() {
    try {
        const response = await fetch('/api/ams/lite');
        if (!response.ok) {
            console.warn('[AMS Lite] API nicht verfügbar');
            return [];
        }
        const data = await response.json();
        amsLiteDevices = Array.isArray(data.devices) ? data.devices : [];
        console.log('[AMS Lite] Geräte geladen:', amsLiteDevices.length);
        return amsLiteDevices;
    } catch (error) {
        console.error('[AMS Lite] Fehler beim Laden:', error);
        return [];
    }
}

// === RENDER FUNKTIONEN ===

/**
 * Rendert ein AMS Lite Gerät
 * @param {Object} device - Das AMS Lite Gerät
 * @param {Array} spools - Die Spulen-Liste für Matching
 * @param {Array} materials - Die Material-Liste für Matching
 * @returns {string} HTML String für das Gerät
 */
function renderAmsLiteDevice(device, spools = [], materials = []) {
    if (!device || !device.ams_units) return '';
    
    let html = '';
    
    device.ams_units.forEach((unit, unitIndex) => {
        if (!unit.is_ams_lite) return; // Nur AMS Lite Units
        
        const printerName = unit.printer_name || device.device_serial || 'Unbekannt';
        const isOnline = device.online;
        
        html += `
            <div class="ams-unit ams-lite" data-serial="${device.device_serial}" data-ams-id="${unit.ams_id}">
                <div class="ams-header">
                    <h3>AMS Lite</h3>
                    <span class="ams-serial">SN: ${device.device_serial || '–'}</span>
                    <div class="ams-status">
                        <span class="status-badge ${isOnline ? 'status-online' : 'status-offline'}">
                            ${isOnline ? 'ONLINE' : 'OFFLINE'}
                        </span>
                        <span class="printer-badge">${printerName}</span>
                    </div>
                </div>
                <div class="ams-slots ams-lite-slots">
                    ${renderAmsLiteSlots(unit, device.device_serial, spools, materials)}
                </div>
            </div>
        `;
    });
    
    return html;
}

/**
 * Rendert die Slots eines AMS Lite
 */
function renderAmsLiteSlots(unit, deviceSerial, spools = [], materials = []) {
    if (!unit.trays || !Array.isArray(unit.trays)) {
        return renderEmptyAmsLiteSlot(unit.ams_id);
    }
    
    // AMS Lite hat nur 1 Tray (externer Slot)
    const tray = unit.trays[0];
    if (!tray) {
        return renderEmptyAmsLiteSlot(unit.ams_id);
    }
    
    // Matching Spool finden
    const matchingSpool = spools.find(s => 
        s.ams_slot === AMS_LITE_SLOT_ID || 
        (s.rfid_uid && s.rfid_uid === tray.tag_uid) ||
        (s.tray_uuid && s.tray_uuid === tray.tray_uuid)
    );
    
    // Material bestimmen
    const materialName = tray.tray_sub_brands || tray.tray_type || 'Unbekannt';
    const material = matchingSpool 
        ? materials.find(m => m.id === matchingSpool.material_id)
        : { name: materialName, brand: 'Bambu Lab' };
    
    // Farbe extrahieren (Format: RRGGBBAA)
    const trayColor = tray.tray_color || '999999FF';
    const colorHex = `#${trayColor.substring(0, 6)}`;
    
    // Füllstand
    const remainPercent = tray.remain_percent != null ? tray.remain_percent : 0;
    const remainGrams = tray.remaining_grams || 0;
    const isLow = remainPercent <= 20;
    
    return `
        <div class="slot ams-lite-slot" data-slot="${AMS_LITE_SLOT_ID}">
            <div class="slot-color" style="background: ${colorHex};"></div>
            <div class="slot-number">
                \u25cb External Slot
                ${tray.tag_uid ? '<span class="slot-icon" title="RFID erkannt">TAG</span>' : ''}
            </div>
            <div class="slot-material">${material ? material.name : materialName}</div>
            ${material && material.brand ? `<div class="slot-brand">${material.brand}</div>` : ''}
            <div class="slot-weight">${Math.round(remainPercent)}% (${Math.round(remainGrams)}g)</div>
            <div class="slot-progress">
                <div class="slot-progress-bar ${isLow ? 'low' : ''}" style="width: ${remainPercent}%;"></div>
            </div>
            <div class="slot-actions">
                ${matchingSpool ? `
                    <button class="slot-action-btn" onclick="goToSpool('${matchingSpool.id}')" title="Spule \u00f6ffnen">
                        <span>Open</span>
                    </button>
                ` : ''}
            </div>
        </div>
    `;
}

/**
 * Rendert einen leeren AMS Lite Slot
 */
function renderEmptyAmsLiteSlot(amsId) {
    return `
        <div class="slot-empty ams-lite-slot" data-slot="${AMS_LITE_SLOT_ID}">
            <div class="slot-number">⚪ External Slot</div>
            <div class="slot-label">Leer</div>
            <div class="slot-hint">Keine externe Spule erkannt</div>
        </div>
    `;
}

// === STATISTIK FUNKTIONEN ===

/**
 * Berechnet AMS Lite Statistiken
 */
function getAmsLiteStats() {
    let onlineCount = 0;
    let totalSlots = 0;
    let totalRemainingGrams = 0;
    let lowFilamentCount = 0;
    
    amsLiteDevices.forEach(device => {
        if (device.online) onlineCount++;
        
        (device.ams_units || []).forEach(unit => {
            if (!unit.is_ams_lite) return;
            
            (unit.trays || []).forEach(tray => {
                totalSlots++;
                const grams = tray.remaining_grams || 0;
                totalRemainingGrams += grams;
                
                if (tray.remain_percent != null && tray.remain_percent <= 20) {
                    lowFilamentCount++;
                }
            });
        });
    });
    
    return {
        onlineCount,
        totalSlots,
        totalRemainingGrams,
        totalRemainingKg: (totalRemainingGrams / 1000).toFixed(2),
        lowFilamentCount
    };
}

// === EXPORT für Verwendung in ams.js ===
// Diese Funktionen können von ams.js aufgerufen werden

window.AmsLite = {
    // Konstanten
    SLOT_ID: AMS_LITE_SLOT_ID,
    MAX_SLOTS: AMS_LITE_MAX_SLOTS,
    
    // Helper
    isAmsLiteUnit,
    getSlotId,
    getSlotLabel,
    getMaxSlots,
    
    // Daten
    loadData: loadAmsLiteData,
    getDevices: () => amsLiteDevices,
    
    // Render
    renderDevice: renderAmsLiteDevice,
    renderSlots: renderAmsLiteSlots,
    renderEmptySlot: renderEmptyAmsLiteSlot,
    
    // Stats
    getStats: getAmsLiteStats
};

console.log('[AMS Lite] Modul geladen');
