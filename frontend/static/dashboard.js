// FilamentHub Dashboard JavaScript (clean icons + compact cards)

// === STATE ===
let dashboardData = {
    stats: {},
    materials: [],
    spools: [],
    printers: [],
    recentJobs: []
};

// === INIT ===
document.addEventListener('DOMContentLoaded', () => {
    console.log('[Dashboard] DOMContentLoaded - starting data load');
    loadDashboardData();
    setupNotificationWebSocket();
    // Auto-refresh every 10 seconds
    setInterval(loadDashboardData, 10000);
});

// === NOTIFICATION WEBSOCKET ===
function setupNotificationWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/notifications/ws`;
    
    let ws = null;
    let reconnectTimeout = null;
    
    function connect() {
        try {
            ws = new WebSocket(wsUrl);
            
            ws.onopen = () => {
                console.log('[Notifications] WebSocket connected');
            };
            
            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    console.log('[Notifications] Received:', data);
                    
                    // Backend sendet {event: "notification_trigger", payload: {...}}
                    if (data.event === 'notification_trigger' && data.payload) {
                        const notification = data.payload;
                        showNotification(
                            notification.message || 'Benachrichtigung',
                            notification.type || 'info'
                        );
                    }
                } catch (err) {
                    console.error('[Notifications] Parse error:', err);
                }
            };
            
            ws.onerror = (error) => {
                console.error('[Notifications] WebSocket error:', error);
            };
            
            ws.onclose = () => {
                console.log('[Notifications] WebSocket closed, reconnecting in 5s...');
                if (reconnectTimeout) clearTimeout(reconnectTimeout);
                reconnectTimeout = setTimeout(connect, 5000);
            };
        } catch (err) {
            console.error('[Notifications] Connection error:', err);
            if (reconnectTimeout) clearTimeout(reconnectTimeout);
            reconnectTimeout = setTimeout(connect, 5000);
        }
    }
    
    connect();
}

// === LOAD DATA ===
async function loadDashboardData() {
    try {
        console.log('[Dashboard] loadDashboardData started');
        // Alle Daten parallel laden für bessere Performance
        const [materials, spools, printers] = await Promise.all([
            fetch('/api/materials/').then(r => r.json()),
            fetch('/api/spools/').then(r => r.json()),
            fetch('/api/printers/').then(r => r.json())
        ]);
        
        dashboardData.materials = materials;
        dashboardData.spools = spools;
        dashboardData.printers = printers;
        
        // Jetzt alle UI-Updates mit den Daten
        updateStatsCards(materials, spools, printers);
        renderMaterialsList(materials.slice(0, 5));
        renderLowSpoolsList(spools.filter(s => {
            if (s.is_empty) return false;
            const remaining = s.weight_remaining || s.weight_full || 0;
            return remaining < 200;
        }).slice(0, 5));
        renderPrintersList(printers);
        
        console.log('[Dashboard] All data loaded successfully');
    } catch (error) {
        console.error('Fehler beim Laden der Dashboard-Daten:', error);
    }
}

function updateStatsCards(materials, spools, printers) {
    console.log('[Stats] Updating stat cards');
    
    // Materials
    const statMaterials = document.getElementById('statMaterials');
    if (statMaterials) statMaterials.textContent = materials.length;
    
    // Spools
    const statSpools = document.getElementById('statSpools');
    if (statSpools) statSpools.textContent = spools.length;
    
    // Active Spools
    const activeSpools = spools.filter(s => !s.is_empty);
    const statActiveSpools = document.getElementById('statActiveSpools');
    if (statActiveSpools) statActiveSpools.textContent = activeSpools.length;
    
    // Total Weight
    const totalWeight = spools.reduce((sum, s) => {
        return sum + (s.weight_remaining || s.weight_full || 0);
    }, 0);
    const statTotalWeight = document.getElementById('statTotalWeight');
    if (statTotalWeight) statTotalWeight.textContent = Math.round(totalWeight);
    
    // Printers
    const onlineCount = printers.filter(p => p.online).length;
    const totalCount = printers.length;
    const statPrinters = document.getElementById('statPrinters');
    if (statPrinters) statPrinters.textContent = `${onlineCount} / ${totalCount}`;
}

function renderMaterialsList(materials) {
    const container = document.getElementById('materialsList');
    if (!container) return;

    if (materials.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📦</div>
                <p>Keine Materialien vorhanden</p>
                <button class="btn btn-primary" onclick="window.location.href='/materials'">
                    📦 Material hinzufügen
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
                        <th>Name</th>
                        <th>Marke</th>
                        <th>Farbe</th>
                        <th>Durchmesser</th>
                    </tr>
                </thead>
                <tbody>
                    ${materials.map(m => `
                        <tr onclick="window.location.href='/materials'">
                            <td>${m.name}</td>
                            <td>${m.brand || '-'}</td>
                            <td>
                                ${m.color ? `
                                    <span style="display: inline-block; width: 20px; height: 20px; 
                                          background: ${m.color}; border-radius: 4px; 
                                          vertical-align: middle; margin-right: 8px;
                                          border: 1px solid var(--border);"></span>
                                    ${m.color}
                                ` : '-'}
                            </td>
                            <td>${m.diameter}mm</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
        ${materials.length >= 5 ? `
            <div style="margin-top: 15px; text-align: center;">
                <a href="/materials" class="btn btn-secondary">Alle Materialien anzeigen →</a>
            </div>
        ` : ''}
    `;
}

function renderLowSpoolsList(spools) {
    const container = document.getElementById('lowSpoolsList');
    if (!container) return;

    if (spools.length === 0) {
        container.innerHTML = `
            <div style="text-align: center; padding: 20px; color: var(--success);">
                ✔️ Alle Spulen haben ausreichend Filament
            </div>
        `;
        return;
    }

    container.innerHTML = `
        <div class="info-group">
            ${spools.map(s => {
                const remaining = s.weight_remaining || s.weight_full || 0;
                const percentage = s.weight_full ? (remaining / s.weight_full) * 100 : 0;

                return `
                    <div class="info-item" style="flex-direction: column; align-items: flex-start;">
                        <div style="display: flex; justify-content: space-between; width: 100%; margin-bottom: 8px;">
                            <span class="info-label">${s.label || 'Spule #' + s.id.substring(0, 8)}</span>
                            <span class="info-value">${Math.round(remaining)}g</span>
                        </div>
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${percentage}%; 
                                 background: ${percentage < 20 ? 'var(--error)' : 'var(--warning)'}"></div>
                        </div>
                    </div>
                `;
            }).join('')}
        </div>
    `;
}

function renderPrintersList(printers) {
    const container = document.getElementById('printersList');
    if (!container) return;
    if (!printers || printers.length === 0) {
        container.innerHTML = `<div class="empty-state"><div class="empty-state-icon">🖨️</div><p>Keine Drucker konfiguriert</p></div>`;
        return;
    }
    container.innerHTML = `<div class="grid grid-3col">${printers.map(p => `
        <div class="card" style="position:relative;">
            <div style="position:absolute;top:15px;right:15px;">${p.online ? '<span class="status-badge status-online">Online</span>' : '<span class="status-badge status-offline">Offline</span>'}</div>
            <div style="max-width: 720px; margin: 0 auto;">
                <div style="font-size:3rem;text-align:center;margin:14px 0;">${p.printer_type === 'bambu' || p.printer_type === 'bambu_lab' ? '🎯' : p.printer_type === 'klipper' ? '🛠️' : '🖨️'}</div>
                <h3 style="text-align:center;margin-bottom:12px;">${p.name}</h3>
                <div class="info-group">
                    <div class="info-item"><span class="info-label">Typ</span><span class="info-value">${p.printer_type}</span></div>
                    <div class="info-item"><span class="info-label">IP-Adresse</span><span class="info-value">${p.ip_address}${p.port ? ':' + p.port : ''}</span></div>
                </div>
            </div>
        </div>
    `).join('')}</div>`;
}

// === UTILITY ===
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        padding: 15px 25px;
        background: var(--bg-card);
        border: 1px solid var(--accent);
        border-radius: 8px;
        color: var(--text);
        z-index: 10000;
        box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        animation: slideIn 0.3s ease;
    `;
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}
