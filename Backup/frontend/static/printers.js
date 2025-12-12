// Printers Management JavaScript
// Notification-Box anzeigen
function showNotification(message, type = 'info') {
    const box = document.getElementById('notificationBox');
    if (!box) return;
    box.innerHTML = `<div class="notification notification-${type}" style="padding:12px 18px;margin-bottom:8px;border-radius:6px;background:${type==='success'?'#2ecc40':type==='error'?'#e74c3c':'#3498db'};color:white;font-size:1rem;box-shadow:0 2px 8px rgba(0,0,0,0.12);">${message}</div>`;
    box.style.display = 'block';
    setTimeout(() => { box.style.display = 'none'; }, 3000);
}

let printers = [];
let foundPrinters = [];
let currentPrinterId = null;
let deleteTargetId = null;

// === INIT ===
document.addEventListener('DOMContentLoaded', () => {
    loadPrinters();
    setupFormListeners();
    // Optional: Automatisch beim Laden scannen
    // scanForPrinters();
});

function setupFormListeners() {
    // Type change handler already set in HTML with onchange
}

// === LOAD PRINTERS ===
async function loadPrinters() {
    try {
        const response = await fetch('/api/printers/');
        
        if (!response.ok) {
            // If endpoint doesn't exist yet, show empty state
            if (response.status === 404) {
                printers = [];
                renderPrinters();
                return;
            }
            throw new Error('Laden fehlgeschlagen');
        }
        
        printers = await response.json();
        renderPrinters();
        
    } catch (error) {
        console.error('Fehler beim Laden der Drucker:', error);
        printers = [];
        renderPrinters();
    }
}

function renderPrinters() {
    const container = document.getElementById('printersGrid');
    if (printers.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🖨️</div>
                <h3>Keine Drucker konfiguriert</h3>
                <p>Fügen Sie Ihren ersten Drucker hinzu!</p>
                <button class="btn btn-primary" onclick="openAddModal()">
                    ➕ Drucker hinzufügen
                </button>
            </div>
        `;
        return;
    }
    container.innerHTML = `
        <div class="grid grid-3col">
            ${printers.map(p => renderPrinterCard(p)).join('')}
        </div>
    `;
    // Verbindungstest nur noch per Button, nicht automatisch
}

// === FOUND PRINTERS ===
function renderFoundPrinters() {
    const container = document.getElementById('foundPrintersGrid');
    if (!foundPrinters || foundPrinters.length === 0) {
        container.innerHTML = '';
        return;
    }
    container.innerHTML = `
        <h2 style="margin-bottom: 10px;">Gefundene Drucker im Netzwerk</h2>
        <div class="grid grid-3col">
            ${foundPrinters.map(p => renderFoundPrinterCard(p)).join('')}
        </div>
    `;
}

function renderFoundPrinterCard(printer) {
    const typeIcons = {
        'bambu': '🎯',
        'klipper': '⚙️',
        'unknown': '❓'
    };
    const typeNames = {
        'bambu': 'Bambu Lab',
        'klipper': 'Klipper',
        'unknown': 'Unbekannt'
    };
    const icon = typeIcons[printer.type] || '🖨️';
    const typeName = typeNames[printer.type] || printer.type;
    return `
        <div class="card" style="position: relative;">
            <div style="position: absolute; top: 15px; right: 15px;">
                <span class="status-badge status-offline">Nicht hinzugefügt</span>
            </div>
            <div style="font-size: 3rem; text-align: center; margin: 20px 0;">${icon}</div>
            <h3 style="text-align: center; margin-bottom: 20px;">${printer.hostname || printer.ip}</h3>
            <div class="info-group">
                <div class="info-item">
                    <span class="info-label">Typ</span>
                    <span class="info-value">${typeName}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">IP-Adresse</span>
                    <span class="info-value">${printer.ip}:${printer.port}</span>
                </div>
            </div>
            <button class="btn btn-primary" style="width: 100%; margin-top: 10px;" onclick="addFoundPrinter(${JSON.stringify(printer).replace(/"/g, '&quot;')})">
                ➕ Hinzufügen
            </button>
        </div>
    `;
}

async function scanForPrinters() {
    const btn = document.getElementById('scanPrintersBtn');
    if (btn) btn.disabled = true;
    const container = document.getElementById('foundPrintersGrid');
    container.innerHTML = '<div class="loader">Scan läuft...</div>';
    try {
        const response = await fetch('/api/scanner/scan/quick');
        if (!response.ok) throw new Error('Scan fehlgeschlagen');
        const result = await response.json();
        foundPrinters = result.printers || [];
        renderFoundPrinters();
    } catch (error) {
        container.innerHTML = '<div class="empty-state">Fehler beim Scan</div>';
    }
    if (btn) btn.disabled = false;
}

function addFoundPrinter(printer) {
    // Modal öffnen und Felder vorausfüllen
    currentPrinterId = null;
    document.getElementById('modalTitle').textContent = '➕ Gefundenen Drucker hinzufügen';
    document.getElementById('printerForm').reset();
    document.getElementById('printerId').value = '';
    document.getElementById('printerName').value = printer.hostname || printer.ip;
    document.getElementById('printerType').value = printer.type !== 'unknown' ? printer.type : '';
    updateFormFields();
    document.getElementById('printerIp').value = printer.ip;
    document.getElementById('printerPort').value = printer.port || '';
    document.getElementById('printerModal').classList.add('active');
}

function renderPrinterCard(printer) {
    const typeIcons = {
        'bambu': '🎯',
        'klipper': '⚙️',
        'manual': '✋'
    };
    
    const typeNames = {
        'bambu': 'Bambu Lab',
        'klipper': 'Klipper',
        'manual': 'Manuell'
    };
    
    const icon = typeIcons[printer.printer_type] || '🖨️';
    const typeName = typeNames[printer.printer_type] || printer.printer_type;
    
    // Status dynamisch anzeigen (Backend liefert Feld 'online')
    let statusBadge = '<span class="status-badge status-offline">Offline</span>';
    if (printer.online === true) {
        statusBadge = '<span class="status-badge status-online">Online</span>';
    }

    return `
        <div class="card" style="position: relative;">
            <div style="position: absolute; top: 15px; right: 15px;">
                ${statusBadge}
            </div>
            <div style="font-size: 3rem; text-align: center; margin: 20px 0;">
                ${icon}
            </div>
            <h3 style="text-align: center; margin-bottom: 20px;">${printer.name}</h3>
            <div class="info-group">
                <div class="info-item">
                    <span class="info-label">Typ</span>
                    <span class="info-value">${typeName}</span>
                </div>
                ${printer.ip_address ? `
                    <div class="info-item">
                        <span class="info-label">IP-Adresse</span>
                        <span class="info-value">${printer.ip_address}${printer.port ? ':' + printer.port : ''}</span>
                    </div>
                ` : ''}
                ${printer.cloud_serial ? `
                    <div class="info-item">
                        <span class="info-label">Seriennummer</span>
                        <span class="info-value" style="font-size: 0.85rem;">${printer.cloud_serial}</span>
                    </div>
                ` : ''}
                <div class="info-item">
                    <span class="info-label">API Konfiguriert</span>
                    <span class="info-value">${printer.api_key ? '✓ Ja' : '✗ Nein'}</span>
                </div>
            </div>
            <div style="display: flex; gap: 10px; margin-top: 20px;">
                <button class="btn btn-secondary" style="flex: 1;" onclick="openEditModal('${printer.id}')">
                    ✏️ Bearbeiten
                </button>
                <button class="btn btn-secondary btn-delete" onclick="openDeleteModal('${printer.id}')">
                    🗑️
                </button>
            </div>
            ${printer.printer_type !== 'manual' ? `
                <button class="btn btn-primary" style="width: 100%; margin-top: 10px;" 
                        onclick="testConnection('${printer.id}')">
                    🔌 Verbindung testen
                </button>
            ` : ''}
        </div>
    `;
}

// === FORM MANAGEMENT ===
function updateFormFields() {
    const type = document.getElementById('printerType').value;
    
    const networkFields = document.getElementById('networkFields');
    const bambuFields = document.getElementById('bambuFields');
    const klipperFields = document.getElementById('klipperFields');
    
    // Hide all optional fields
    networkFields.style.display = 'none';
    bambuFields.style.display = 'none';
    klipperFields.style.display = 'none';
    
    // Reset required attribute
    document.getElementById('printerIp').required = false;
    
    if (type === 'bambu') {
        networkFields.style.display = 'block';
        bambuFields.style.display = 'block';
        document.getElementById('printerIp').required = true;
        document.getElementById('printerPort').placeholder = '6000';
    } else if (type === 'klipper') {
        networkFields.style.display = 'block';
        klipperFields.style.display = 'block';
        document.getElementById('printerIp').required = true;
        document.getElementById('printerPort').placeholder = '7125';
    }
}

// === MODAL MANAGEMENT ===
function openAddModal() {
    currentPrinterId = null;
    document.getElementById('modalTitle').textContent = '➕ Drucker hinzufügen';
    document.getElementById('printerForm').reset();
    document.getElementById('printerId').value = '';
    updateFormFields();
    document.getElementById('printerModal').classList.add('active');
}

function openEditModal(id) {
    const printer = printers.find(p => p.id === id);
    if (!printer) return;
    
    currentPrinterId = id;
    document.getElementById('modalTitle').textContent = '✏️ Drucker bearbeiten';
    
    document.getElementById('printerId').value = printer.id;
    document.getElementById('printerName').value = printer.name;
    document.getElementById('printerType').value = printer.printer_type;
    
    updateFormFields();
    
    document.getElementById('printerIp').value = printer.ip_address || '';
    document.getElementById('printerPort').value = printer.port || '';
    document.getElementById('printerSerial').value = printer.cloud_serial || '';
    
    // Set API key in correct field based on type
    if (printer.printer_type === 'bambu') {
        document.getElementById('printerApiKey').value = printer.api_key || '';
    } else if (printer.printer_type === 'klipper') {
        document.getElementById('printerApiKeyKlipper').value = printer.api_key || '';
    }
    
    document.getElementById('printerModal').classList.add('active');
}

function closeModal() {
    document.getElementById('printerModal').classList.remove('active');
    currentPrinterId = null;
}

function openDeleteModal(id) {
    deleteTargetId = id;
    document.getElementById('deleteModal').classList.add('active');
}

function closeDeleteModal() {
    document.getElementById('deleteModal').classList.remove('active');
    deleteTargetId = null;
}

// === SAVE PRINTER ===
async function savePrinter(event) {
    event.preventDefault();
    
    const type = document.getElementById('printerType').value;
    const port = document.getElementById('printerPort').value;
    
    let apiKey = null;
    if (type === 'bambu') {
        apiKey = document.getElementById('printerApiKey').value || null;
    } else if (type === 'klipper') {
        apiKey = document.getElementById('printerApiKeyKlipper').value || null;
    }
    
    const data = {
        name: document.getElementById('printerName').value,
        printer_type: type,
        ip_address: document.getElementById('printerIp').value || null,
        port: port ? parseInt(port) : null,
        cloud_serial: document.getElementById('printerSerial').value || null,
        api_key: apiKey
    };
    
    try {
        let response;
        
        if (currentPrinterId) {
            // Update existing
            response = await fetch(`/api/printers/${currentPrinterId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        } else {
            // Create new
            response = await fetch('/api/printers/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        }
        
        if (response.ok) {
            showNotification(
                currentPrinterId ? 'Drucker aktualisiert!' : 'Drucker erstellt!', 
                'success'
            );
            closeModal();
            await loadPrinters();
        } else {
            throw new Error('Speichern fehlgeschlagen');
        }
        
    } catch (error) {
        console.error('Fehler beim Speichern:', error);
        showNotification('Fehler beim Speichern', 'error');
    }
}

// === DELETE PRINTER ===
async function confirmDelete() {
    if (!deleteTargetId) return;
    
    try {
        const response = await fetch(`/api/printers/${deleteTargetId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showNotification('Drucker gelöscht', 'success');
            closeDeleteModal();
            await loadPrinters();
        } else {
            throw new Error('Löschen fehlgeschlagen');
        }
        
    } catch (error) {
        console.error('Fehler beim Löschen:', error);
        showNotification('Fehler beim Löschen', 'error');
    }
}

// === TEST CONNECTION ===
async function testConnection(id) {
    const printer = printers.find(p => p.id === id);
    if (!printer) return;
    showNotification('Teste Verbindung...', 'info');
    try {
        const response = await fetch(`/api/printers/${id}/test`, {
            method: 'POST'
        });
        if (response.ok) {
            const result = await response.json();
            if (result.status === 'success') {
                showNotification(result.message, 'success');
                printer._online = true;
            } else {
                showNotification(result.message, result.status);
                printer._online = false;
            }
            renderPrinters();
        } else {
            showNotification('Fehler beim Testen der Verbindung', 'error');
            printer._online = false;
            renderPrinters();
        }
    } catch (error) {
        console.error('Fehler beim Connection-Test:', error);
        showNotification('Verbindungsfehler', 'error');
        printer._online = false;
        renderPrinters();
    }
}

// Close modals on ESC key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
        closeDeleteModal();
    }
});

// Close modals on background click
document.getElementById('printerModal').addEventListener('click', (e) => {
    if (e.target.id === 'printerModal') closeModal();
});

document.getElementById('deleteModal').addEventListener('click', (e) => {
    if (e.target.id === 'deleteModal') closeDeleteModal();
});
