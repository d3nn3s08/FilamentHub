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
        <div class="printer-grid">
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
        <div class="printer-grid">
            ${foundPrinters.map(p => renderFoundPrinterCard(p)).join('')}
        </div>
    `;
}

function renderFoundPrinterCard(printer) {
    const typeIcons = {
        bambu: '🎯',
        klipper: '🛠️',
        unknown: '❓'
    };
    const typeNames = {
        bambu: 'Bambu Lab',
        klipper: 'Klipper',
        unknown: 'Unbekannt'
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
        bambu: '🎯',
        klipper: '🛠️',
        manual: '📝'
    };
    const typeNames = {
        bambu: 'Bambu Lab',
        klipper: 'Klipper',
        manual: 'Manuell'
    };
    const icon = typeIcons[printer.printer_type] || '🖨️';
    const typeName = typeNames[printer.printer_type] || printer.printer_type;
    const isOnline = printer.online === true || printer._online;
    const thumb = printer.image_url
        ? `<img src="${printer.image_url}" alt="${printer.name || 'Drucker'}" style="width:48px;height:48px;object-fit:cover;border-radius:6px;border:1px solid var(--border);">`
        : `<div class=\"printer-icon\">${icon}</div>`;

    return `
        <div class="printer-card">
            <div class="status-badge ${isOnline ? 'status-online' : 'status-offline'}">${isOnline ? 'Online' : 'Offline'}</div>
            <div class="printer-head">
                <div class="printer-icon">${thumb}</div>
                <div class="printer-title">${printer.name}</div>
            </div>
            <div class="info-group compact">
                <div class="info-item">
                    <span class="info-label">Typ</span>
                    <span class="info-value">${typeName}</span>
                </div>
                ${printer.ip_address ? `
                <div class="info-item">
                    <span class="info-label">IP-Adresse</span>
                    <span class="info-value">${printer.ip_address}${printer.port ? ':' + printer.port : ''}</span>
                </div>` : ''}
                ${printer.cloud_serial ? `
                <div class="info-item">
                    <span class="info-label">Seriennummer</span>
                    <span class="info-value" style="font-size:0.9rem;">${printer.cloud_serial}</span>
                </div>` : ''}
                <div class="info-item">
                    <span class="info-label">API konfiguriert</span>
                    <span class="info-value">${printer.api_key ? 'Ja' : 'Nein'}</span>
                </div>
            </div>
            <div class="card-actions">
                <button class="btn btn-secondary" onclick="openEditModal('${printer.id}')">✏️ Bearbeiten</button>
                <button class="btn btn-danger btn-icon" onclick="openDeleteModal('${printer.id}')">🗑️ Löschen</button>
            </div>
            ${printer.printer_type !== 'manual' ? `
            <div class="cta-row">
                <button class="btn btn-primary" onclick="testConnection('${printer.id}')">🔌 Verbindung testen</button>
            </div>` : ''}
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
    const autoConnectEl = document.getElementById('printerAutoConnect');
    if (autoConnectEl) autoConnectEl.checked = false;
    updateFormFields();
    document.getElementById('printerModal').classList.add('active');
    toggleImageSection(false);
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
    const autoConnectEl = document.getElementById('printerAutoConnect');
    if (autoConnectEl) autoConnectEl.checked = !!printer.auto_connect;
    toggleImageSection(true);
    setImagePreview(printer.image_url, printer.id);
    
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
    const p = printers.find(pr => pr.id === id);
    const nameEl = document.getElementById('deletePrinterName');
    if (p && nameEl) {
        nameEl.textContent = p.name || 'Name unbekannt';
    }
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
        api_key: apiKey,
        auto_connect: document.getElementById('printerAutoConnect')?.checked || false
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

// === IMAGE UPLOAD ===
function toggleImageSection(show) {
    const section = document.getElementById('printerImageSection');
    if (!section) return;
    section.style.display = show ? 'block' : 'none';
    if (!show) {
        setImagePreview(null, null);
    }
}

function setImagePreview(url, id) {
    const img = document.getElementById('printerImagePreview');
    const placeholder = document.getElementById('printerImagePlaceholder');
    if (!img || !placeholder) return;
    if (url) {
        img.src = url + (id ? `?cb=${Date.now()}` : '');
        img.style.display = 'block';
        placeholder.style.display = 'none';
    } else {
        img.src = '';
        img.style.display = 'none';
        placeholder.style.display = 'block';
    }
}

async function uploadPrinterImage() {
    if (!currentPrinterId) {
        showNotification('Bitte zuerst speichern, dann Bild hochladen.', 'warning');
        return;
    }
    const fileInput = document.getElementById('printerImageFile');
    if (!fileInput || !fileInput.files.length) {
        showNotification('Bitte Bild auswählen (PNG/JPG/WEBP, max 1 MB)', 'warning');
        return;
    }
    const file = fileInput.files[0];
    if (!['image/png', 'image/jpeg', 'image/webp'].includes(file.type)) {
        showNotification('Nur PNG/JPG/WEBP erlaubt', 'error');
        return;
    }
    if (file.size > 1_000_000) {
        showNotification('Bild zu groß (max 1 MB)', 'error');
        return;
    }
    const form = new FormData();
    form.append('file', file);
    try {
        const resp = await fetch(`/api/printers/${currentPrinterId}/image`, {
            method: 'POST',
            body: form
        });
        const data = await resp.json();
        if (!resp.ok || !data.success) {
            throw new Error(data.detail || data.message || 'Upload fehlgeschlagen');
        }
        setImagePreview(data.image_url, currentPrinterId);
        showNotification('Bild gespeichert', 'success');
    } catch (err) {
        showNotification(err.message || 'Upload fehlgeschlagen', 'error');
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
