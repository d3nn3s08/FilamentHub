// Tab-Klick-Handler für Debug Center Tabs
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.debug-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const target = tab.dataset.tab;
            // Panel-Logik: alle Panels ausblenden, nur Zielpanel anzeigen
            document.querySelectorAll('.debug-panel').forEach(panel => {
                panel.style.display = 'none';
            });
            const panel = document.getElementById('panel-' + target);
            if (panel) panel.style.display = '';
            // active-Klasse setzen
            document.querySelectorAll('.debug-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
        });
    });
});
// === MIGRATION BUTTON + STATUS ===
document.addEventListener('DOMContentLoaded', () => {
    const migrateBtn = document.getElementById('migrateDb');
    const migrateOutput = document.getElementById('migrateOutput');
    if (migrateBtn) {
        migrateBtn.addEventListener('click', async () => {
            migrateBtn.disabled = true;
            migrateBtn.textContent = 'Migration lï¿½uft...';
            if (migrateOutput) migrateOutput.innerHTML = '?? Migration gestartet...';
            try {
                const response = await fetch('/api/database/migrate', { method: 'POST' });
                const result = await response.json();
                if (result.success) {
                    if (result.message === 'Datenbankspalte bereits vorhanden') {
                        showNotification('Datenbankspalte ist schon vorhanden!', 'info');
                        if (migrateOutput) migrateOutput.innerHTML = '?? ï¿½bersprungen, da bereits vorhanden.';
                    } else {
                        showNotification('Migration erfolgreich!', 'success');
                        if (migrateOutput) migrateOutput.innerHTML = '?? Migration durchgelaufen.';
                    }
                } else {
                    showNotification('Migration fehlgeschlagen: ' + (result.message || 'Unbekannter Fehler'), 'error');
                    if (migrateOutput) migrateOutput.innerHTML = '?? Fehler bei Migration.';
                }
            } catch (err) {
                showNotification('Migration Fehler: ' + err.message, 'error');
                if (migrateOutput) migrateOutput.innerHTML = '?? Migration Fehler: ' + err.message;
            }
            migrateBtn.disabled = false;
            migrateBtn.textContent = 'Migration starten';
        });
    }
});
// FilamentHub Debug Center JavaScript

// === STATE ===
let updateInterval = null;
let performanceInterval = null;
let backendStatusInterval = null;
const PERFORMANCE_LITE_INTERVAL_MS = 5000;
const PERFORMANCE_THRESHOLDS = {
    cpu: { warn: 60, error: 80 },
    ram: { warn: 70, error: 85 },
    disk: { warn: 80, error: 90 }
};
let debugCenterMode = "lite";
let lastSystemStatus = null;

function initSystemPanel() {
    const root = document.getElementById('panel-system');
    if (isNullElement(root)) {
        __logMissing('panel-system');
        return;
    }
    loadSystemStatus();
    loadBackendStatus();
    setupModeSwitch();
    initDebugCenterMode();
    if (!updateInterval) updateInterval = setInterval(loadSystemStatus, 3000);
    if (!backendStatusInterval) backendStatusInterval = setInterval(loadBackendStatus, 5000);
}

function initRuntimePanel() {
    const root = document.getElementById('panel-performance');
    if (isNullElement(root)) {
        __logMissing('panel-performance');
        return;
    }
    setupPerformanceListeners();
}

function initMQTTPanel() {
    const root = document.getElementById('panel-mqtt');
    if (isNullElement(root)) {
        __logMissing('panel-mqtt');
        return;
    }
    setupMqttListeners();
}

function initConfigPanel() {
    const root = document.getElementById('panel-config');
    if (isNullElement(root)) {
        __logMissing('panel-config');
        return;
    }
    loadConfigData();
    setupModeSwitch();
}

// MQTT Activity Monitoring
let lastMessageTimestamp = null;
let pingInterval = null;
let pongTimeout = null;
let sparklineData = [];
const SPARKLINE_MAX = 50; // 50 points in sparkline

function formatTimeAgo(ts) {
    if (!ts) return "—";
    const diff = (Date.now() - ts) / 1000;
    return diff.toFixed(2) + "s ago";
}

function renderSparkline() {
    const canvas = document.getElementById("activitySparkline");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    ctx.beginPath();
    ctx.strokeStyle = "#4caf50";
    ctx.lineWidth = 2;

    if (sparklineData.length === 0) return;

    const stepX = w / SPARKLINE_MAX;

    sparklineData.forEach((val, i) => {
        const x = i * stepX;
        const y = h - val * h;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    });

    ctx.stroke();
}

setInterval(() => {
    const elem = document.getElementById("lastMessageTime");
    if (elem) {
        elem.textContent = formatTimeAgo(lastMessageTimestamp);
    }
}, 500);

// === INIT ===
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    initSystemPanel();
    initRuntimePanel();
    initConfigPanel();
    initMQTTPanel();
    setupServiceListeners();
    setupDatabaseListeners();
    setupScannerListeners();
    setupDbEditorListeners();
    const amsBtn = document.getElementById('btn_sys_ams_inspect');
    if (amsBtn) {
        amsBtn.addEventListener('click', () => {
            if (lastSystemStatus?.printers) {
                console.info('AMS/Printer inspect', lastSystemStatus.printers);
            } else {
                console.info('Keine AMS-Daten verfügbar.');
            }
        });
    }
});
// === DB EDITOR ===
function setupDbEditorListeners() {
    const executeBtn = document.getElementById('dbEditorExecute');
    const clearBtn = document.getElementById('dbEditorClear');
    const queryBox = document.getElementById('dbEditorQuery');
    const outputBox = document.getElementById('dbEditorOutput');
    const tablesBox = document.getElementById('dbEditorTables');
    if (!executeBtn || !clearBtn || !queryBox || !outputBox || !tablesBox) return;
    // Tabellenstruktur laden
    fetch('/api/database/tables').then(r => r.json()).then(data => {
        if (!data.tables || !data.tables.length) {
            tablesBox.innerHTML = '<p style="color:var(--text-dim);">Keine Tabellen gefunden.</p>';
            return;
        }
        tablesBox.innerHTML = data.tables.map(table => `
            <div style="margin-bottom:12px;">
                <div style="font-weight:600;color:var(--accent);margin-bottom:2px;">${table.name} <span style='color:var(--text-dim);font-size:0.85em;'>(${table.row_count} Zeilen)</span></div>
                <div style="display:flex;flex-wrap:wrap;gap:6px;">
                    ${table.columns.map(col => `<span style='background:var(--bg-card-hover);border:1px solid var(--border);border-radius:4px;padding:2px 8px;font-size:0.85em;'>${col.name}<small style='color:var(--text-dim);'> (${col.type}${col.primary_key ? ', PK' : ''})</small></span>`).join('')}
                </div>
            </div>
        `).join('');
    });

    executeBtn.addEventListener('click', async () => {
        const sql = queryBox.value.trim();
        if (!sql) {
            outputBox.textContent = 'Bitte SQL-Befehl eingeben.';
            outputBox.classList.add('show');
            return;
        }
        outputBox.textContent = '? Wird ausgefï¿½hrt...';
        outputBox.classList.add('show');
        try {
            const response = await fetch(`/api/database/editor`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ sql })
            });
            const data = await response.json();
            if (data.success) {
                outputBox.textContent = data.message || 'Erfolgreich ausgefï¿½hrt.';
                if (data.data) {
                    outputBox.textContent += '\n' + JSON.stringify(data.data, null, 2);
                }
            } else {
                outputBox.textContent = 'Fehler: ' + (data.message || 'Unbekannter Fehler');
            }
        } catch (err) {
            outputBox.textContent = 'Fehler: ' + err.message;
        }
    });
    clearBtn.addEventListener('click', () => {
        queryBox.value = '';
        outputBox.textContent = '';
        outputBox.classList.remove('show');
    });
}

// === TAB SWITCHING ===
function initTabs() {
    const tabs = document.querySelectorAll('.tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active from all
            tabs.forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            // Add active to clicked
            tab.classList.add('active');
            const tabId = 'tab-' + tab.dataset.tab;
            document.getElementById(tabId).classList.add('active');
            
            // Load data when switching tabs
            const targetTab = tab.dataset.tab;
            if (targetTab === 'config') {
                loadConfigData();
            } else if (targetTab === 'services') {
                loadServicesData();
            } else if (targetTab === 'database') {
                loadDatabaseData();
            } else if (targetTab === 'scanner') {
                loadScannerData();
            } else if (targetTab === 'mqtt') {
                loadMqttTab();
            }

            if (targetTab === 'performance') {
                startPerformanceMonitoring();
            } else {
                stopPerformanceMonitoring();
            }
        });
    });
}

// === MODE SWITCH ===
function setupModeSwitch() {
    const btn = document.getElementById('modeUpdateBtn');
    if (!btn) return;
    btn.addEventListener('click', async () => {
        const select = document.getElementById('modeSelect');
        const mode = (select?.value || 'bambu').toLowerCase();
        try {
            const res = await fetch('/api/system/mode', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mode })
            });
            if (!res.ok) {
                console.error('Modus setzen fehlgeschlagen', await res.text());
                return;
            }
            loadSystemStatus();
        } catch (err) {
            console.error('Fehler beim Setzen des Modus', err);
        }
    });
}

// === CONFIG MANAGER ===
async function loadConfigData() {
    const panelRoot = document.getElementById('panel-config');
    if (isNullElement(panelRoot)) {
        __logMissing('panel-config');
        return;
    }
    try {
        // Load full config
        const configResponse = await fetch('/api/debug/config');
        const config = await configResponse.json();
        
        // Load as YAML string for editor
        const yamlResponse = await fetch('/api/debug/config/raw');
        let yamlText;
        if (yamlResponse.ok) {
            yamlText = await yamlResponse.text();
        } else {
            // Fallback: JSON to YAML-like format
            yamlText = JSON.stringify(config, null, 2);
        }
        
        const editor = document.getElementById('configEditor');
        editor.value = yamlText;
        editor.dataset.original = yamlText;
        
        // Load module status
        const statusResponse = await fetch('/api/debug/modules/status');
        const status = await statusResponse.json();
        
        // Update log level selector
        document.getElementById('logLevelSelect').value = status.global_level;
        
        // Create module toggles
        createModuleToggles(status.modules);
        
        // Load Python environment
        loadEnvironmentInfo();
        
        // Setup editor change detection
        setupConfigEditor();
        
    } catch (error) {
        console.error('Fehler beim Laden der Config:', error);
    }
}

function createModuleToggles(modules) {
    const container = document.getElementById('moduleToggles');
    container.innerHTML = '';
    
    for (const [name, info] of Object.entries(modules)) {
        const item = document.createElement('div');
        item.className = 'toggle-item';
        
        const label = document.createElement('span');
        label.textContent = name.charAt(0).toUpperCase() + name.slice(1);
        
        const toggle = document.createElement('div');
        toggle.className = 'toggle-switch' + (info.enabled ? ' active' : '');
        toggle.dataset.module = name;
        toggle.addEventListener('click', () => toggleModule(name, !info.enabled, toggle));
        
        item.appendChild(label);
        item.appendChild(toggle);
        container.appendChild(item);
    }
}

async function toggleModule(moduleName, enabled, toggleElement) {
    try {
        const response = await fetch('/api/debug/config/logging/toggle', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ module: moduleName, enabled: enabled })
        });
        
        const result = await response.json();
        
        if (result.success) {
            toggleElement.classList.toggle('active', enabled);
            showNotification(result.message, 'success');
        } else {
            showNotification('Fehler beim Umschalten', 'error');
        }
    } catch (error) {
        console.error('Toggle-Fehler:', error);
        showNotification('Netzwerkfehler', 'error');
    }
}

async function loadEnvironmentInfo() {
    try {
        const response = await fetch('/api/debug/environment');
        const env = await response.json();
        
        const container = document.getElementById('pythonInfo');
        container.innerHTML = `
            <div class="info-item">
                <span class="label">Version:</span>
                <span class="value">${env.python_version.split(' ')[0]}</span>
            </div>
            <div class="info-item">
                <span class="label">Platform:</span>
                <span class="value">${env.platform}</span>
            </div>
            <div class="info-item">
                <span class="label">Architecture:</span>
                <span class="value">${env.architecture}</span>
            </div>
            <div class="info-item">
                <span class="label">Processor:</span>
                <span class="value">${env.processor || 'N/A'}</span>
            </div>
        `;
    } catch (error) {
        console.error('Fehler beim Laden der Python-Info:', error);
    }
}

// === CONFIG EDITOR ===
function setupConfigEditor() {
    const editor = document.getElementById('configEditor');
    const saveBtn = document.getElementById('saveConfig');
    const status = document.getElementById('configStatus');
    
    editor.addEventListener('input', () => {
        const isModified = editor.value !== editor.dataset.original;
        editor.classList.toggle('modified', isModified);
        saveBtn.disabled = !isModified;
        
        if (isModified) {
            status.textContent = '?? Nicht gespeichert';
            status.className = 'config-status modified';
        } else {
            status.textContent = '?? Gespeichert';
            status.className = 'config-status saved';
        }
    });
}

async function saveConfigFile() {
    const editor = document.getElementById('configEditor');
    const saveBtn = document.getElementById('saveConfig');
    const status = document.getElementById('configStatus');
    
    try {
        saveBtn.disabled = true;
        status.textContent = ' Speichere...';
        status.className = 'config-status';
        
        const response = await fetch('/api/debug/config/save', {
            method: 'POST',
            headers: { 'Content-Type': 'text/plain' },
            body: editor.value
        });
        
        const result = await response.json();
        
        if (result.success) {
            editor.dataset.original = editor.value;
            editor.classList.remove('modified');
            status.textContent = '? Erfolgreich gespeichert';
            status.className = 'config-status saved';
            showNotification('Config erfolgreich gespeichert!', 'success');
            
            // Reload after 1 second
            setTimeout(() => {
                loadConfigData();
            }, 1000);
        } else {
            throw new Error(result.message || 'Speichern fehlgeschlagen');
        }
    } catch (error) {
        status.textContent = '? Fehler beim Speichern';
        status.className = 'config-status error';
        showNotification('Fehler: ' + error.message, 'error');
        saveBtn.disabled = false;
    }
}

// === EVENT LISTENERS ===
function setupEventListeners() {
    // Log Level Update
    document.getElementById('updateLogLevel').addEventListener('click', async () => {
        const level = document.getElementById('logLevelSelect').value;
        
        try {
            const response = await fetch('/api/debug/config/logging/level', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ level: level })
            });
            
            const result = await response.json();
            
            if (result.success) {
                showNotification(result.message, 'success');
                loadConfigData();
            }
        } catch (error) {
            showNotification('Fehler beim Aktualisieren', 'error');
        }
    });
    
    // Save Config
    document.getElementById('saveConfig').addEventListener('click', saveConfigFile);
    
    // Reload Config
    document.getElementById('reloadConfig').addEventListener('click', () => {
        if (confirm('Config neu laden? Nicht gespeicherte ï¿½nderungen gehen verloren.')) {
            loadConfigData();
            showNotification('Config neu geladen', 'success');
        }
    });
    
    // Format Config
    document.getElementById('formatConfig').addEventListener('click', () => {
        const editor = document.getElementById('configEditor');
        try {
            // Try to parse as JSON and format
            const config = JSON.parse(editor.value);
            editor.value = JSON.stringify(config, null, 2);
            showNotification('Formatierung erfolgreich', 'success');
        } catch (error) {
            showNotification('Konnte nicht formatieren (kein valides JSON)', 'error');
        }
    });
}

// === TOAST NOTIFICATIONS ===
function showNotification(message, type = 'info', duration = 3000) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const icon = {
        success: '?',
        error: '?',
        info: '??',
        warning: '??'
    }[type] || '??';
    
    toast.innerHTML = `
        <span class="toast-icon">${icon}</span>
        <span class="toast-message">${message}</span>
    `;
    
    // Container erstellen falls nicht vorhanden
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        document.body.appendChild(container);
    }
    
    container.appendChild(toast);
    
    // Animation
    setTimeout(() => toast.classList.add('show'), 10);
    
    // Auto-Remove
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// === SERVICES TAB ===
async function loadServicesData() {
    loadProcessInfo();
    loadServerStats();
    loadDockerStatus();
    loadLogsList();
}

async function loadProcessInfo() {
    try {
        const response = await fetch('/api/services/process/info');
        const data = await response.json();
        
        const container = document.getElementById('processInfo');
        container.innerHTML = `
            <div class="info-item">
                <span class="label">PID:</span>
                <span class="value">${data.pid}</span>
            </div>
            <div class="info-item">
                <span class="label">Status:</span>
                <span class="value">${data.status}</span>
            </div>
            <div class="info-item">
                <span class="label">CPU:</span>
                <span class="value">${data.cpu_percent.toFixed(1)}%</span>
            </div>
            <div class="info-item">
                <span class="label">Memory:</span>
                <span class="value">${data.memory_mb} MB</span>
            </div>
            <div class="info-item">
                <span class="label">Threads:</span>
                <span class="value">${data.num_threads}</span>
            </div>
        `;
    } catch (error) {
        console.error('Fehler beim Laden der Process Info:', error);
    }
}

async function loadServerStats() {
    try {
        const response = await fetch('/api/services/server/stats');
        const data = await response.json();
        
        const container = document.getElementById('serverStats');
        
        container.innerHTML = `
            <div class="info-item">
                <span class="label">Gestartet:</span>
                <span class="value">${data.start_time}</span>
            </div>
            <div class="info-item">
                <span class="label">Uptime:</span>
                <span class="value">${data.uptime_formatted}</span>
            </div>
            <div class="info-item">
                <span class="label">Platform:</span>
                <span class="value">${data.platform}</span>
            </div>
            <div class="info-item">
                <span class="label">Hostname:</span>
                <span class="value">${data.hostname}</span>
            </div>
            <div class="info-item">
                <span class="label">Python:</span>
                <span class="value">${data.python_version}</span>
            </div>
            <div class="info-item">
                <span class="label">Port:</span>
                <span class="value">${data.port}</span>
            </div>
            <div class="info-item">
                <span class="label">Connections:</span>
                <span class="value">${data.active_connections}</span>
            </div>
            <div class="info-item">
                <span class="label">Memory:</span>
                <span class="value">${data.memory_mb} MB</span>
            </div>
            <div class="info-item">
                <span class="label">Threads:</span>
                <span class="value">${data.threads}</span>
            </div>
        `;
    } catch (error) {
        console.error('Fehler beim Laden der Server Stats:', error);
    }
}

async function loadDockerStatus() {
    try {
        const response = await fetch('/api/services/docker/status');
        const data = await response.json();
        
        const container = document.getElementById('dockerStatus');
        
        if (data.available) {
            container.innerHTML = `
                <div class="info-item">
                    <span class="label">Status:</span>
                    <span class="value" style="color: var(--success)">?? Verfï¿½gbar</span>
                </div>
                <div class="info-item">
                    <span class="label">Version:</span>
                    <span class="value">${data.docker_version}</span>
                </div>
                <div class="info-item">
                    <span class="label">Compose:</span>
                    <span class="value">${data.compose_available ? '?? Ja' : '? Nein'}</span>
                </div>
            `;
        } else {
            container.innerHTML = `
                <div class="info-item">
                    <span class="label">Status:</span>
                    <span class="value" style="color: var(--error)">?? Nicht verfï¿½gbar</span>
                </div>
            `;
        }
    } catch (error) {
        console.error('Fehler beim Laden des Docker Status:', error);
    }
}

async function loadLogsList() {
    try {
        const response = await fetch('/api/services/logs/list');
        const data = await response.json();
        
        const container = document.getElementById('logsList');
        
        if (data.total === 0) {
            container.innerHTML = '<p>Keine Log-Dateien gefunden.</p>';
            return;
        }
        
        container.innerHTML = '';
        
        for (const [module, files] of Object.entries(data.log_files)) {
            const moduleDiv = document.createElement('div');
            moduleDiv.className = 'log-module';
            
            const totalSizeKB = files.reduce((sum, f) => sum + f.size_kb, 0);
            const totalSizeMB = (totalSizeKB / 1024).toFixed(2);
            
            moduleDiv.innerHTML = `
                <div class="log-module-header">
                    <span class="log-module-title">${module.toUpperCase()}</span>
                    <button class="btn btn-danger btn-small" onclick="clearModuleLogs('${module}')">
                        ??? Lï¿½schen
                    </button>
                </div>
                <div class="log-files">
                    ${files.map(f => `<div>${f.name} (${(f.size_kb / 1024).toFixed(2)} MB)</div>`).join('')}
                    <div style="margin-top: 4px; font-weight: 600;">Total: ${totalSizeMB} MB</div>
                </div>
            `;
            
            container.appendChild(moduleDiv);
        }
    } catch (error) {
        console.error('Fehler beim Laden der Logs:', error);
    }
}

async function clearModuleLogs(module) {
    if (!confirm(`Alle ${module.toUpperCase()}-Logs lï¿½schen?`)) return;
    
    try {
        const response = await fetch(`/api/services/logs/clear/${module}`, {
            method: 'POST'
        });
        const data = await response.json();
        
        if (data.success) {
            showNotification(data.message, 'success');
            loadLogsList();
        }
    } catch (error) {
        showNotification('Fehler beim Lï¿½schen', 'error');
    }
}

// Service Control Functions
async function executeServiceCommand(endpoint, method = 'POST') {
    try {
        const response = await fetch(endpoint, { method });
        const data = await response.json();
        return data;
    } catch (error) {
        return { success: false, message: error.message };
    }
}

function startRestartCountdown() {
    const countdownDiv = document.getElementById('restartCountdown');
    const timerSpan = document.getElementById('countdownTimer');
    const progressBar = document.getElementById('countdownBar');
    const restartBtn = document.getElementById('serverRestart');
    
    // Show countdown
    countdownDiv.style.display = 'block';
    restartBtn.disabled = true;
    
    let timeLeft = 15;  // 15 seconds
    const totalTime = 15;
    
    showNotification('Server wird neugestartet...', 'info', 3000);
    
    const countdownInterval = setInterval(() => {
        timeLeft--;
        timerSpan.textContent = timeLeft;
        
        // Update progress bar
        const progress = (timeLeft / totalTime) * 100;
        progressBar.style.width = progress + '%';
        
        if (timeLeft <= 0) {
            clearInterval(countdownInterval);
            
            // Hide countdown
            countdownDiv.style.display = 'none';
            restartBtn.disabled = false;
            
            // Reload page
            showNotification('Server wurde neugestartet! Seite wird neu geladen...', 'success', 2000);
            setTimeout(() => {
                window.location.reload();
            }, 2000);
        }
    }, 1000);
}

function setupServiceListeners() {
    const panelRoot = document.getElementById('panel-services');
    if (isNullElement(panelRoot)) {
        __logMissing('panel-services');
        return;
    }
    // Process
    document.getElementById('refreshProcess').addEventListener('click', loadProcessInfo);
    
    // Server
    document.getElementById('serverRestart').addEventListener('click', async () => {
        if (!confirm('Mï¿½chten Sie den Server wirklich neu starten?')) return;
        
        const result = await executeServiceCommand('/api/services/server/restart');
        
        if (result.success) {
            // Show countdown
            startRestartCountdown();
        } else {
            showNotification(result.message, 'error');
        }
    });
    
    // Dependencies
    document.getElementById('installDeps').addEventListener('click', async () => {
        showNotification('Installiere Dependencies...', 'info', 5000);
        const result = await executeServiceCommand('/api/services/dependencies/install');
        const output = document.getElementById('depsOutput');
        output.textContent = result.output || result.message;
        output.classList.add('show');
        showNotification(result.message, result.success ? 'success' : 'error');
    });
    
    document.getElementById('updateAllPackages').addEventListener('click', async () => {
        if (!confirm('Alle Packages auf die neueste Version aktualisieren?')) return;
        
        showNotification('Prï¿½fe Updates...', 'info');
        const output = document.getElementById('depsOutput');
        output.textContent = 'Aktualisiere alle Packages...\n';
        output.classList.add('show');
        
        const result = await executeServiceCommand('/api/services/dependencies/update-all');
        output.textContent += '\n' + (result.output || result.message);
        showNotification(result.message, result.success ? 'success' : 'error');
    });
    
    document.getElementById('listDeps').addEventListener('click', async () => {
        const result = await executeServiceCommand('/api/services/dependencies/list', 'GET');
        const output = document.getElementById('depsOutput');
        if (result.packages) {
            output.textContent = result.packages.map(p => `${p.name} ${p.version}`).join('\n');
            output.classList.add('show');
            showNotification(`${result.count} Packages gefunden`, 'success');
        }
    });
    
    document.getElementById('listOutdated').addEventListener('click', async () => {
        showNotification('Prï¿½fe veraltete Packages...', 'info');
        const result = await executeServiceCommand('/api/services/dependencies/outdated', 'GET');
        const output = document.getElementById('depsOutput');
        
        if (result.packages && result.packages.length > 0) {
            output.textContent = result.packages.map(p => 
                `${p.name}: ${p.version} ? ${p.latest_version}`
            ).join('\n');
            output.classList.add('show');
            showNotification(` ${result.count} Updates verfï¿½gbar!`, 'warning');
        } else {
            output.textContent = '? Alle Packages sind aktuell!';
            output.classList.add('show');
            showNotification('Alle Packages sind aktuell', 'success');
        }
    });
    
    // Docker
    document.getElementById('dockerUp').addEventListener('click', async () => {
        showNotification('Starte Docker Compose...', 'info');
        const result = await executeServiceCommand('/api/services/docker/compose/up');
        const output = document.getElementById('dockerOutput');
        output.textContent = result.output || result.message;
        output.classList.add('show');
        showNotification(result.message, result.success ? 'success' : 'error');
    });
    
    document.getElementById('dockerDown').addEventListener('click', async () => {
        showNotification('Stoppe Docker Compose...', 'info');
        const result = await executeServiceCommand('/api/services/docker/compose/down');
        const output = document.getElementById('dockerOutput');
        output.textContent = result.output || result.message;
        output.classList.add('show');
        showNotification(result.message, result.success ? 'success' : 'error');
    });
    
    document.getElementById('dockerPs').addEventListener('click', async () => {
        const result = await executeServiceCommand('/api/services/docker/compose/ps', 'GET');
        const output = document.getElementById('dockerOutput');
        output.textContent = result.output || 'Keine Container gefunden';
        output.classList.add('show');
    });
    
    // Tests
    const testsOutput = document.getElementById('testsOutput');
    const smokeBtn = document.getElementById('runTestsSmoke');
    const dbBtn = document.getElementById('runTestsDb');
    const allBtn = document.getElementById('runTestsAll');
    const covBtn = document.getElementById('runCoverage');

    const setBtnState = (btn, success) => {
        if (!btn) return;
        btn.classList.remove('btn-secondary', 'btn-success');
        btn.classList.add(success ? 'btn-success' : 'btn-secondary');
    };

    const runAndShow = async (endpoint, note, btn) => {
        showNotification(note, 'info', 5000);
        const result = await executeServiceCommand(endpoint);
        if (testsOutput) {
            testsOutput.textContent = result.output || result.message || '';
            testsOutput.classList.add('show');
        }
        setBtnState(btn, !!result.success);
        showNotification(result.message || 'Fertig', result.success ? 'success' : 'error');
    };

    smokeBtn?.addEventListener('click', () => runAndShow('/api/services/tests/smoke', 'Starte Smoke-Tests (Test-DB)...', smokeBtn));
    dbBtn?.addEventListener('click', () => runAndShow('/api/services/tests/db', 'Starte DB-Tests (Test-DB)...', dbBtn));
    allBtn?.addEventListener('click', () => runAndShow('/api/services/tests/all', 'Starte alle Tests (Test-DB)...', allBtn));
    covBtn?.addEventListener('click', async () => {
        showNotification('Fï¿½hre Tests mit Coverage aus...', 'info', 5000);
        const result = await executeServiceCommand('/api/services/tests/coverage', 'GET');
        if (testsOutput) {
            testsOutput.textContent = result.output || result.message || '';
            testsOutput.classList.add('show');
        }
        setBtnState(covBtn, !!result.success);
        showNotification(result.message || 'Fertig', result.success ? 'success' : 'error');
    });
}

// === DATABASE TAB ===
async function loadDatabaseData() {
    loadDatabaseInfo();
    loadDatabaseStats();
}

async function loadDatabaseInfo() {
    try {
        const response = await fetch('/api/database/info');
        const data = await response.json();
        
        const container = document.getElementById('dbInfo');
        
        if (!data.exists) {
            container.innerHTML = `
                <div class="info-item">
                    <span class="label">Status:</span>
                    <span class="value" style="color: var(--error)">? Nicht gefunden</span>
                </div>
                <div class="info-item">
                    <span class="label">Path:</span>
                    <span class="value">${data.path}</span>
                </div>
            `;
            return;
        }
        
        container.innerHTML = `
            <div class="info-item">
                <span class="label">Status:</span>
                <span class="value" style="color: var(--success)">?? Vorhanden</span>
            </div>
            <div class="info-item">
                <span class="label">Type:</span>
                <span class="value">SQLite</span>
            </div>
            <div class="info-item">
                <span class="label">Size:</span>
                <span class="value">${data.size_kb} KB</span>
            </div>
            <div class="info-item">
                <span class="label">Tables:</span>
                <span class="value">${data.table_count}</span>
            </div>
            <div class="info-item">
                <span class="label">Path:</span>
                <span class="value" style="font-size: 0.75rem; word-break: break-all;">${data.path}</span>
            </div>
        `;
    } catch (error) {
        console.error('Fehler beim Laden der DB Info:', error);
    }
}

async function loadDatabaseStats() {
    try {
        const response = await fetch('/api/database/stats');
        const data = await response.json();
        
        const container = document.getElementById('dbStats');
        
        container.innerHTML = `
            <div class="info-item">
                <span class="label">Materials:</span>
                <span class="value">${data.materials_count}</span>
            </div>
            <div class="info-item">
                <span class="label">Spools (Total):</span>
                <span class="value">${data.spools_count}</span>
            </div>
            <div class="info-item">
                <span class="label">Spools (Open):</span>
                <span class="value">${data.spools_open}</span>
            </div>
            <div class="info-item">
                <span class="label">Spools (Empty):</span>
                <span class="value">${data.spools_empty}</span>
            </div>
            <div class="info-item">
                <span class="label">Printers:</span>
                <span class="value">${data.printers_count}</span>
            </div>
            <div class="info-item">
                <span class="label">Jobs:</span>
                <span class="value">${data.jobs_count}</span>
            </div>
        `;
    } catch (error) {
        console.error('Fehler beim Laden der DB Stats:', error);
    }
}

async function loadDatabaseTables() {
    try {
        const response = await fetch('/api/database/tables');
        const data = await response.json();
        
        const container = document.getElementById('dbTables');
        if (!container) {
            // DB-Tab ausgeblendet/ausgelagert ï¿½ still aussteigen
            return;
        }
        
        if (data.tables.length === 0) {
            container.innerHTML = '<p>Keine Tabellen gefunden.</p>';
            return;
        }
        


        container.innerHTML = data.tables.map(table => {
            const hasRows = table.preview && Array.isArray(table.preview.rows) && table.preview.rows.length > 0;
            return `
                <div class="db-table">
                    <div class="db-table-header">
                        <span class="db-table-name">${table.name}</span>
                        <span class="db-table-info">${table.row_count} Zeilen ï¿½ ${table.column_count} Spalten</span>
                    </div>
                    <div class="db-columns">
                        ${table.columns.map(col => `
                            <span class="db-column">
                                ${col.name} <small>(${col.type})</small>
                                ${col.primary_key ? '<span class="badge" style="font-size: 0.7rem; padding: 2px 6px;">PK</span>' : ''}
                            </span>
                        `).join('')}
                    </div>
                    <div class="db-preview-table-wrapper">
                        <table class="db-preview-table" style="margin-top:10px;font-size:0.95rem;width:100%;border-collapse:collapse;">
                            <thead>
                                <tr>
                                    ${table.preview.headers.map(h => `<th style='border-bottom:1px solid #333;padding:4px 8px;text-align:left;'>${h}</th>`).join('')}
                                </tr>
                            </thead>
                            <tbody>
                                ${hasRows ? table.preview.rows.map(row => Array.isArray(row) ? `<tr>${row.map(cell => `<td style='padding:4px 8px;border-bottom:1px solid #222;'>${cell ?? ''}</td>`).join('')}</tr>` : '').join('')
                                : `<tr><td colspan='${table.preview.headers.length}' style='color:var(--text-dim);text-align:center;padding:8px;'>Keine Daten vorhanden</td></tr>`}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;
        }).join('');
        
    } catch (error) {
        console.error('Fehler beim Laden der Tabellen:', error);
    }
}

async function loadBackupsList() {
    try {
        const response = await fetch('/api/database/backups/list');
        const data = await response.json();
        
        const container = document.getElementById('backupsList');
        if (!container) {
            return;
        }
        
        if (data.count === 0) {
            container.innerHTML = '<p style="font-size: 0.85rem; color: var(--text-dim);">Keine Backups</p>';
            return;
        }
        
        container.innerHTML = `
            <div style="font-size: 0.85rem; color: var(--text);">
                ${data.backups.slice(0, 3).map(backup => `
                    <div style="padding: 4px 0; border-bottom: 1px solid var(--border);">
                        <div>${backup.filename}</div>
                        <small style="color: var(--text-dim);">${backup.size_mb} MB</small>
                    </div>
                `).join('')}
                ${data.count > 3 ? `<div style="margin-top: 8px; color: var(--accent);">+${data.count - 3} weitere</div>` : ''}
            </div>
        `;
    } catch (error) {
        console.error('Fehler beim Laden der Backups:', error);
    }
}

function setupDatabaseListeners() {
    // VACUUM
    const vacuumDbBtn = document.getElementById('vacuumDb');
    if (vacuumDbBtn) vacuumDbBtn.addEventListener('click', async () => {
        if (!confirm('Datenbank optimieren? Dies kann einen Moment dauern.')) return;
        
        showNotification('VACUUM wird ausgefï¿½hrt...', 'info');
        
        try {
            const response = await fetch('/api/database/vacuum', { method: 'POST' });
            const data = await response.json();
            
            const output = document.getElementById('vacuumOutput');
            output.textContent = `${data.message}\nVorher: ${data.size_before_mb} MB\nNachher: ${data.size_after_mb} MB\nGespart: ${data.saved_kb} KB`;
            output.classList.add('show');
            
            showNotification(data.message, 'success');
            loadDatabaseInfo();
        } catch (error) {
            showNotification('VACUUM Fehler: ' + error.message, 'error');
        }
    });
    
    // BACKUP
    const backupDbBtn = document.getElementById('backupDb');
    if (backupDbBtn) backupDbBtn.addEventListener('click', async () => {
        showNotification('Backup wird erstellt...', 'info');
        
        try {
            const response = await fetch('/api/database/backup', { method: 'POST' });
            const data = await response.json();
            
            const output = document.getElementById('backupOutput');
            output.textContent = `${data.message}\nDatei: ${data.backup_path}\nGrï¿½ï¿½e: ${data.backup_size_mb} MB`;
            output.classList.add('show');
            
            showNotification(data.message, 'success');
            loadBackupsList();
        } catch (error) {
            showNotification('Backup Fehler: ' + error.message, 'error');
        }
    });

    // MIGRATION (Alembic upgrade head)
    const migrateBtn = document.getElementById('migrateDb');
    if (migrateBtn) {
        migrateBtn.addEventListener('click', async () => {
            if (!confirm('Alembic Migration (upgrade head) jetzt ausfuehren?')) return;
            const out = document.getElementById('migrateOutput');
            const statusInitial = document.getElementById('statusInitial');
            const statusSkipped = document.getElementById('statusSkipped');
            if (out) out.textContent = 'Migration laeuft...';
            if (statusInitial) {
                statusInitial.textContent = '? Migration lï¿½uft...';
                statusInitial.style.color = 'var(--accent)';
            }
            if (statusSkipped) {
                statusSkipped.textContent = '?? ï¿½bersprungen (da vorhanden)';
                statusSkipped.style.color = 'var(--text-dim)';
            }
            showNotification('Migration gestartet...', 'info');
            try {
                const resp = await fetch('/api/database/migrate', { method: 'POST' });
                const data = await resp.json();
                if (!resp.ok) throw new Error(data.detail || data.message || 'Migration fehlgeschlagen');
                if (out) out.textContent = data.stdout || data.message || 'Migration erfolgreich';
                if (statusInitial) {
                    if (data.message && data.message.includes('bereits durchgefï¿½hrt')) {
                        statusInitial.textContent = '?? Bereits durchgefï¿½hrt';
                        statusInitial.style.color = 'var(--success)';
                    } else if (data.message && (
                        data.message.toLowerCase().includes('ï¿½bersprungen') ||
                        data.message.toLowerCase().includes('bereits vorhanden') ||
                        data.message.toLowerCase().includes('keine ï¿½nderungen')
                    )) {
                        statusInitial.textContent = '?? ï¿½bersprungen (da vorhanden)';
                        statusInitial.style.color = 'var(--accent)';
                        if (statusSkipped) {
                            statusSkipped.style.color = 'var(--accent)';
                        }
                    } else {
                        statusInitial.textContent = '? Migration erfolgreich';
                        statusInitial.style.color = 'var(--success)';
                    }
                }
                showNotification('Migration erfolgreich', 'success');
                loadDatabaseInfo();
            } catch (err) {
                if (out) out.textContent = String(err);
                if (statusList) {
                    statusList.innerHTML = '';
                    let li = document.createElement('li');
                    li.textContent = '? Fehler: ' + err.message;
                    li.style.color = 'var(--error)';
                    statusList.appendChild(li);
                }
                showNotification('Migration Fehler: ' + err.message, 'error');
            }
        });
    }
    
    // Delete row
    const deleteBtn = document.getElementById('deleteRowBtn');
    if (deleteBtn) {
        deleteBtn.addEventListener('click', async () => {
            const table = document.getElementById('deleteRowTable').value;
            const id = document.getElementById('deleteRowId').value.trim();
            const output = document.getElementById('deleteRowOutput');
            if (!table || !id) {
                showNotification('Bitte Tabelle und ID angeben', 'warning');
                return;
            }
            output.textContent = 'Loesche Eintrag...';
            try {
                const resp = await fetch(`/api/database/row?table=${encodeURIComponent(table)}&id=${encodeURIComponent(id)}`, {
                    method: 'DELETE'
                });
                const data = await resp.json();
                if (!resp.ok) throw new Error(data.detail || data.message || 'Loeschen fehlgeschlagen');
                output.textContent = data.message || 'Eintrag geloescht';
                showNotification(data.message || 'Eintrag geloescht', 'success');
                loadDatabaseInfo();
                loadDatabaseTables();
            } catch (err) {
                output.textContent = String(err);
                showNotification('Loeschen fehlgeschlagen: ' + err.message, 'error');
            }
        });
    }
    
    // Refresh Backups
    const refreshBackupsBtn = document.getElementById('refreshBackups');
    if (refreshBackupsBtn) refreshBackupsBtn.addEventListener('click', loadBackupsList);
    
    // SQL Query
    const executeQueryBtn = document.getElementById('executeQuery');
    if (executeQueryBtn) executeQueryBtn.addEventListener('click', async () => {
        const sql = document.getElementById('sqlQuery').value.trim();
        
        if (!sql) {
            showNotification('Bitte SQL Query eingeben', 'warning');
            return;
        }
        
        try {
            const response = await fetch(`/api/database/query?sql=${encodeURIComponent(sql)}`);
            const data = await response.json();
            
            const output = document.getElementById('queryOutput');
            output.textContent = JSON.stringify(data.data, null, 2);
            output.classList.add('show');
            
            showNotification(`${data.row_count} Zeilen gefunden`, 'success');
        } catch (error) {
            showNotification('Query Fehler: ' + error.message, 'error');
        }
    });
    
    const clearQueryBtn = document.getElementById('clearQuery');
    if (clearQueryBtn) clearQueryBtn.addEventListener('click', () => {
        const sqlQuery = document.getElementById('sqlQuery');
        const queryOutput = document.getElementById('queryOutput');
        if (sqlQuery) sqlQuery.value = '';
        if (queryOutput) {
            queryOutput.textContent = '';
            queryOutput.classList.remove('show');
        }
    });

    // Custom link adder
    const linkCard = document.querySelector('#tab-dbeditor .card');
    if (linkCard) {
        window.addCustomLink = function() {
            const url = prompt('Link-URL eingeben (z.B. http://localhost:8080/foo)');
            if (!url) return;
            const label = prompt('Label fï¿½r den Link:');
            if (!label) return;
            const container = linkCard.querySelector('div[style*=\"flex-direction:column\"]');
            if (container) {
                const a = document.createElement('a');
                a.className = 'btn btn-secondary';
                a.href = url;
                a.target = '_blank';
                a.textContent = label;
                container.appendChild(a);
            }
        }
    }
}

// =============================
// SCANNER TAB
// =============================

async function loadScannerData() {
    try {
        const response = await fetch('/api/scanner/network/info');
        const data = await response.json();
        
        document.getElementById('localIP').textContent = data.local_ip || 'Unbekannt';
        document.getElementById('localHostname').textContent = data.hostname || 'Unbekannt';
        document.getElementById('suggestedRange').textContent = data.default_scan_range || '192.168.1.0/24';
        document.getElementById('ipRange').value = data.default_scan_range || '192.168.1.0/24';
        
    } catch (error) {
        console.error('Fehler beim Laden der Netzwerkinfo:', error);
        showNotification('Fehler beim Laden der Netzwerkinfo', 'error');
    }
}

function setupScannerListeners() {
    const panelRoot = document.getElementById('panel-scanner');
    if (isNullElement(panelRoot)) {
        __logMissing('panel-scanner');
        return;
    }
    // Quick Scan Buttons
    document.getElementById('quickScan').addEventListener('click', () => quickScan());
    document.getElementById('scanBambu').addEventListener('click', () => scanBambu());
    document.getElementById('scanKlipper').addEventListener('click', () => scanKlipper());
    
    // Custom Scan
    document.getElementById('customScan').addEventListener('click', () => customScan());
    
    // Connection Tester
    // Button-ID im Template lautet "testConnection"
    document.getElementById('testConnection').addEventListener('click', () => testConnection());
    
    // Add Printer Button
    document.getElementById('addPrinter').addEventListener('click', () => openAddPrinterModal());
    
    // Config Generator
}

async function quickScan() {
    const resultsDiv = document.getElementById('foundPrinters');
    const progressDiv = document.getElementById('scanProgress');
    
    resultsDiv.innerHTML = '';
    progressDiv.innerHTML = `
        <div>Quick Scan lï¿½uft... (ï¿½berprï¿½fe hï¿½ufige IPs)</div>
        <div class="progress-bar">
            <div class="progress-fill" style="width: 0%"></div>
        </div>
    `;
    progressDiv.classList.add('show');
    
    // Fortschritt simulieren
    const progressFill = progressDiv.querySelector('.progress-fill');
    let progress = 0;
    const interval = setInterval(() => {
        progress += 5;
        if (progress <= 90) {
            progressFill.style.width = progress + '%';
        }
    }, 100);
    
    try {
        const response = await fetch('/api/scanner/scan/quick', {
            method: 'GET'
        });
        const data = await response.json();
        
        clearInterval(interval);
        progressFill.style.width = '100%';
        
        setTimeout(() => {
            progressDiv.classList.remove('show');
            displayFoundPrinters(data.printers);
            
            if (data.printers.length > 0) {
                showNotification(`${data.printers.length} Drucker gefunden!`, 'success');
            } else {
                showNotification('Keine Drucker gefunden', 'info');
            }
        }, 300);
    } catch (error) {
        clearInterval(interval);
        progressDiv.classList.remove('show');
        showNotification('Scan Fehler: ' + error.message, 'error');
    }
}

async function scanBambu() {
    const resultsDiv = document.getElementById('foundPrinters');
    const progressDiv = document.getElementById('scanProgress');
    
    resultsDiv.innerHTML = '';
    progressDiv.innerHTML = `
        <div>Bambu Lab Drucker scannen... (Ports 990, 8883, 322, 6000)</div>
        <div class="progress-bar">
            <div class="progress-fill" style="width: 0%"></div>
        </div>
    `;
    progressDiv.classList.add('show');
    
    // Fortschritt simulieren
    const progressFill = progressDiv.querySelector('.progress-fill');
    let progress = 0;
    const interval = setInterval(() => {
        progress += 2;
        if (progress <= 90) {
            progressFill.style.width = progress + '%';
        }
    }, 200);
    
    try {
        const ipRange = document.getElementById('ipRange').value || '192.168.1.0/24';
        const timeout = document.getElementById('scanTimeout').value || 2;
        
        const response = await fetch('/api/scanner/detect/bambu', {
            method: 'GET'
        });
        const data = await response.json();
        
        clearInterval(interval);
        progressFill.style.width = '100%';
        
        setTimeout(() => {
            progressDiv.classList.remove('show');
            displayFoundPrinters(data.printers);
            
            if (data.printers.length > 0) {
                showNotification(`${data.printers.length} Bambu Lab Drucker gefunden!`, 'success');
            } else {
                showNotification('Keine Bambu Lab Drucker gefunden', 'info');
            }
        }, 300);
    } catch (error) {
        clearInterval(interval);
        progressDiv.classList.remove('show');
        showNotification('Bambu Scan Fehler: ' + error.message, 'error');
    }
}

async function scanKlipper() {
    const resultsDiv = document.getElementById('foundPrinters');
    const progressDiv = document.getElementById('scanProgress');
    
    resultsDiv.innerHTML = '';
    progressDiv.innerHTML = `
        <div>Klipper Drucker scannen... (Port 7125)</div>
        <div class="progress-bar">
            <div class="progress-fill" style="width: 0%"></div>
        </div>
    `;
    progressDiv.classList.add('show');
    
    // Fortschritt simulieren
    const progressFill = progressDiv.querySelector('.progress-fill');
    let progress = 0;
    const interval = setInterval(() => {
        progress += 2;
        if (progress <= 90) {
            progressFill.style.width = progress + '%';
        }
    }, 200);
    
    try {
        const ipRange = document.getElementById('ipRange').value || '192.168.1.0/24';
        const timeout = document.getElementById('scanTimeout').value || 2;
        
        const response = await fetch('/api/scanner/detect/klipper', {
            method: 'GET'
        });
        const data = await response.json();
        
        clearInterval(interval);
        progressFill.style.width = '100%';
        
        setTimeout(() => {
            progressDiv.classList.remove('show');
            displayFoundPrinters(data.printers);
            
            if (data.printers.length > 0) {
                showNotification(`${data.printers.length} Klipper Drucker gefunden!`, 'success');
            } else {
                showNotification('Keine Klipper Drucker gefunden', 'info');
            }
        }, 300);
    } catch (error) {
        clearInterval(interval);
        progressDiv.classList.remove('show');
        showNotification('Klipper Scan Fehler: ' + error.message, 'error');
    }
}

async function customScan() {
    const resultsDiv = document.getElementById('foundPrinters');
    const progressDiv = document.getElementById('scanProgress');
    if (!resultsDiv || !progressDiv) {
        console.error('Scan UI Elemente fehlen');
        return;
    }
    
    const ipRangeEl = document.getElementById('ipRange');
    const timeoutEl = document.getElementById('scanTimeout');
    const portBambuEl = document.getElementById('portBambu');
    const portKlipperEl = document.getElementById('portKlipper');
    const customPortsEl = document.getElementById('customPorts');
    
    const ipRange = ipRangeEl ? ipRangeEl.value : '';
    const timeoutStr = (timeoutEl?.value || '0.5').replace(',', '.');
    const timeout = parseFloat(timeoutStr) || 0.5;
    const portBambu = portBambuEl ? portBambuEl.checked : false;
    const portKlipper = portKlipperEl ? portKlipperEl.checked : false;
    const customPorts = (customPortsEl?.value || '')
        .split(',')
        .map(p => parseInt(p.trim()))
        .filter(p => !isNaN(p));
    const defaultPorts = [6000, 7125, 990, 8883, 322, 80];
    
    let ports = [];
    if (portBambu) ports.push(6000);
    if (portKlipper) ports.push(7125);
    ports = [...ports, ...customPorts];
    if (ports.length === 0) {
        ports = defaultPorts.slice();
    }
    ports = Array.from(new Set(ports));
    
    // Host-Anzahl abschï¿½tzen (nur IPv4), max 254 wie Backend
    const estimateHostCount = (cidr) => {
        try {
            const [net, maskStr] = cidr.split('/');
            const mask = parseInt(maskStr, 10);
            if (isNaN(mask) || mask < 0 || mask > 32) return 254;
            const size = Math.pow(2, 32 - mask) - 2; // minus Netz/Broadcast
            return Math.min(Math.max(size, 1), 254);
        } catch (e) {
            return 254;
        }
    };
    const hostCount = estimateHostCount(ipRange || '192.168.1.0/24');

    resultsDiv.innerHTML = '';
    progressDiv.innerHTML = `
        <div>Custom Scan lï¿½uft... (${ipRange} | Ports: ${ports.join(', ')} | ~${hostCount} Hosts)</div>
        <div class="progress-bar">
            <div class="progress-fill" style="width: 0%"></div>
        </div>
    `;
    progressDiv.classList.add('show');
    const progressFill = progressDiv.querySelector('.progress-fill');

    // Approximate ETA: Hosts * Ports * Timeout / concurrency (50)
    const estSeconds = Math.max((hostCount * ports.length * timeout) / 50, 1);
    const estMs = estSeconds * 1000;
    const startTime = Date.now();
    const interval = setInterval(() => {
        const elapsed = Date.now() - startTime;
        let pct = Math.min((elapsed / estMs) * 95, 95); // bis 95% warten wir aufs echte Ergebnis
        if (progressFill) progressFill.style.width = `${pct}%`;
    }, 200);
    
    try {
        const response = await fetch('/api/scanner/scan/network', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                ip_range: ipRange, 
                ports: ports, 
                timeout: parseFloat(timeout) 
            })
        });
        const data = await response.json();
        const hosts = data.printers || data.hosts || [];
        
        clearInterval(interval);
        if (progressFill) progressFill.style.width = '100%';
        setTimeout(() => progressDiv.classList.remove('show'), 200);
        displayFoundPrinters(hosts);
        
        if (hosts.length > 0) {
            showNotification(`${hosts.length} Hosts gefunden!`, 'success');
        } else {
            showNotification('Keine Hosts gefunden', 'info');
        }
    } catch (error) {
        clearInterval(interval);
        if (progressFill) progressFill.style.width = '0%';
        progressDiv.classList.remove('show');
        showNotification('Scan Fehler: ' + error.message, 'error');
    }
}

async function testConnection() {
    const ip = document.getElementById('testIP').value;
    const port = document.getElementById('testPort').value;
    
    if (!ip || !port) {
        showNotification('Bitte IP und Port eingeben', 'warning');
        return;
    }
    
    try {
        const response = await fetch(`/api/scanner/test/connection?ip=${ip}&port=${port}`, {
            method: 'GET'
        });
        const data = await response.json();
        
        if (data.success) {
        showNotification(`? ${ip}:${port} ist erreichbar! (${data.response_time}ms) - ${data.type}`, 'success');
    } else {
        showNotification(`? ${data.message || 'Nicht erreichbar'}`, 'error');
        }
    } catch (error) {
        showNotification('Connection Test Fehler: ' + error.message, 'error');
    }
}

function displayFoundPrinters(printers) {
    const resultsDiv = document.getElementById('foundPrinters');
    resultsDiv.innerHTML = '';
    
    // DeAktiviere Config-Button bis Tests durchgefï¿½hrt wurden
    checkConfigButton();
    
    if (printers.length === 0) {
        resultsDiv.innerHTML = '<p style="color: var(--text-dim); text-align: center; padding: 20px;">Keine Drucker gefunden</p>';
        return;
    }
    
    printers.forEach(printer => {
        const card = document.createElement('div');
        card.className = 'printer-card';
        
        const printerType = printer.type || printer.printer_type || 'unknown';
        const port = printer.port || (printer.open_ports && printer.open_ports[0]) || 6000;
        const badgeClass = printerType === 'bambu' ? 'bambu' : 
                           printerType === 'klipper' ? 'klipper' : 'unknown';
        const displayType = printerType === 'bambu' ? 'Bambu Lab' : 
                           printerType === 'klipper' ? 'Klipper' : 'Unknown';
        
        card.innerHTML = `
            <div class="printer-info">
                <div class="printer-ip">${printer.ip}</div>
                <div class="printer-details">
                    <span class="printer-badge ${badgeClass}">${displayType}</span>
                    ${printer.hostname ? `<span>${printer.hostname}</span>` : ''}
                    <span> Port: ${port}</span>
                </div>
            </div>
            <div class="printer-actions">
                <button class="btn btn-secondary btn-sm" onclick="testSinglePrinter('${printer.ip}', ${port})">
                    Test
        </button>
        <button class="btn btn-primary btn-sm" onclick="savePrinterToDb('${printer.ip}', ${port}, '${printerType}', '${printer.hostname || ''}')">
                    Speichern
        </button>
        <button class="btn btn-danger btn-sm" onclick="this.closest('.printer-card').remove(); checkPrinterList()">
                    ?
        </button>
            </div>
        `;
        
        resultsDiv.appendChild(card);
    });
}

async function savePrinterToDb(ip, port, type, hostname) {
    try {
        if (type === 'bambu' || type === 'bambu_lab') {
            return openBambuSaveModal({ ip, port, type, hostname });
        }

        await postPrinterToApi({
            name: hostname || ip,
            printer_type: type,
            ip_address: ip,
            port: port,
            cloud_serial: null,
            api_key: null
        });
    } catch (error) {
        showNotification('Fehler beim Speichern: ' + error.message, 'error');
    }
}

async function postPrinterToApi(payload) {
    const response = await fetch('/api/printers/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (response.ok) {
        showNotification('Drucker gespeichert!', 'success');
        return;
    }
    let msg = 'Fehler beim Speichern!';
    try {
        const err = await response.json();
        if (err?.detail || err?.message) msg = err.detail || err.message;
    } catch (e) {
        // ignore json parse error
    }
    throw new Error(msg);
}

// ===== Bambu Save Modal (Serial + Access Code) =====
function ensureBambuModal() {
    if (document.getElementById('bambuSaveModal')) return;
    const modal = document.createElement('div');
    modal.id = 'bambuSaveModal';
    modal.className = 'modal';
    modal.innerHTML = `
        <div class="modal-content" style="max-width:520px;">
            <div class="modal-header">
                <h3>Bambu Drucker speichern</h3>
                <button class="modal-close" onclick="closeBambuSaveModal()">&times;</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>IP-Adresse</label>
                    <input type="text" id="bambuIp" class="select-input" readonly>
                </div>
                <div class="form-group">
                    <label>Port</label>
                    <input type="number" id="bambuPort" class="select-input" readonly>
                </div>
                <div class="form-group">
                    <label>Seriennummer (Cloud Serial)</label>
                    <input type="text" id="bambuSerial" class="select-input" placeholder="z.B. 00M09A372601070">
                    <small style="color: var(--text-dim);">Fï¿½r Bambu Cloud (optional, aber vom Backend gefordert)</small>
                </div>
                <div class="form-group">
                    <label>Access Code (LAN, 8-stellig)</label>
                    <input type="text" id="bambuAccessCode" class="select-input" placeholder="8-stelliger LAN Code">
                </div>
                <div class="form-group" style="display:flex;align-items:center;gap:10px;">
                    <input type="checkbox" id="bambuAutoConnect" style="width:18px;height:18px;">
                    <label for="bambuAutoConnect" style="margin:0;">Automatisch verbinden (MQTT)</label>
                </div>
            </div>
            <div class="modal-footer" style="display:flex;justify-content:flex-end;gap:10px;">
                <button class="btn btn-secondary" onclick="closeBambuSaveModal()">Abbrechen</button>
                <button class="btn btn-primary" id="bambuSaveConfirm">Speichern</button>
            </div>
        </div>
    `;
    document.body.appendChild(modal);
}

function openBambuSaveModal({ ip, port, type, hostname }) {
    ensureBambuModal();
    const modal = document.getElementById('bambuSaveModal');
    modal.style.display = 'flex';
    document.getElementById('bambuIp').value = ip;
    document.getElementById('bambuPort').value = port || 6000;
    document.getElementById('bambuSerial').value = '';
    document.getElementById('bambuAccessCode').value = '';
    const ac = document.getElementById('bambuAutoConnect');
    if (ac) ac.checked = false;

    const saveBtn = document.getElementById('bambuSaveConfirm');
    saveBtn.onclick = async () => {
        const serial = document.getElementById('bambuSerial').value.trim() || null;
        const accessCode = document.getElementById('bambuAccessCode').value.trim() || null;
        const autoConnect = document.getElementById('bambuAutoConnect')?.checked || false;
        try {
            await postPrinterToApi({
                name: hostname || ip,
                printer_type: type,
                ip_address: ip,
                port: port || 6000,
                cloud_serial: serial,
                api_key: accessCode,
                auto_connect: autoConnect
            });
            closeBambuSaveModal();
        } catch (err) {
            showNotification(err.message || 'Fehler beim Speichern', 'error');
        }
    };
}

function closeBambuSaveModal() {
    const modal = document.getElementById('bambuSaveModal');
    if (modal) modal.style.display = 'none';
}

async function testSinglePrinter(ip, port) {
    try {
        const response = await fetch(`/api/scanner/test/connection?ip=${ip}&port=${port}`);
        const data = await response.json();
        
        // Zeige Ergebnis im Modal
        showTestResult(ip, port, data);
        
        if (data.success) {
            showNotification(data.message, 'success');
            
            // Markiere Drucker als erfolgreich getestet
            const cards = document.querySelectorAll('.printer-card');
            cards.forEach(card => {
                const cardIp = card.querySelector('.printer-ip')?.textContent || card.querySelector('strong')?.textContent;
                if (cardIp === ip) {
                    card.setAttribute('data-tested', 'true');
                    card.style.borderLeft = '4px solid var(--success)';
                    
                    // Fï¿½ge Badge hinzu wenn noch nicht vorhanden
                    const badge = card.querySelector('.test-success-badge');
                    if (!badge) {
                        const actionsDiv = card.querySelector('.printer-actions') || card.querySelector('div:last-child');
                        const successBadge = document.createElement('span');
                        successBadge.className = 'test-success-badge';
                        successBadge.style.cssText = 'background: var(--success); color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; margin-right: 8px;';
                        successBadge.textContent = '? Getestet';
                        actionsDiv.insertBefore(successBadge, actionsDiv.firstChild);
                    }
                }
            });
            
            // Prï¿½fe ob Config-Button Aktiviert werden kann
            checkConfigButton();
        } else {
            showNotification(data.message, 'error');
        }
    } catch (error) {
        showNotification('Test Fehler: ' + error.message, 'error');
    }
}

function showTestResult(ip, port, data) {
    const modal = document.getElementById('testResultModal');
    const title = document.getElementById('testResultTitle');
    const content = document.getElementById('testResultContent');
    
    title.innerHTML = data.success ? '? Verbindung erfolgreich' : '? Verbindung fehlgeschlagen';
    
    let html = `
        <div class="info-group">
            <div class="info-item">
                <span class="label">IP-Adresse:</span>
                <span class="value" style="font-family: monospace;">${ip}</span>
            </div>
            <div class="info-item">
                <span class="label">Port:</span>
                <span class="value" style="font-family: monospace;">${port}</span>
            </div>
            ${data.hostname ? `
            <div class="info-item">
                <span class="label">Hostname:</span>
                <span class="value" style="font-family: monospace;">${data.hostname}</span>
            </div>
            ` : ''}
            <div class="info-item">
                <span class="label">Antwortzeit:</span>
                <span class="value">${(data.response_time * 1000).toFixed(0)} ms</span>
            </div>
            <div class="info-item">
                <span class="label">Status:</span>
                <span class="value" style="color: ${data.success ? 'var(--success)' : 'var(--error)'}; font-weight: bold;">
                    ${data.success ? ' Online' : ' Offline'}
                </span>
            </div>
            <div class="info-item">
                <span class="label">Drucker-Typ:</span>
                <span class="value badge">${data.type || 'unknown'}</span>
            </div>
        </div>
        <div style="margin-top: 20px; padding: 15px; background: var(--card-bg); border-left: 3px solid ${data.success ? 'var(--success)' : 'var(--error)'}; border-radius: 4px;">
            <strong> Nachricht:</strong><br>
            <span style="color: var(--text-dim); margin-top: 5px; display: block;">${data.message}</span>
        </div>
    `;
    
    content.innerHTML = html;
    modal.style.display = 'flex';
}

function closeTestResultModal() {
    const modal = document.getElementById('testResultModal');
    modal.style.display = 'none';
}

// =============================
// MQTT VIEWER TAB
// =============================

let mqttWebSocket = null;
let mqttConnected = false;
let mqttPaused = false;
let mqttMessageCount = 0;
let mqttSubscribedTopics = new Set();
let currentMqttPrinter = null; // aktuell ausgewï¿½hlter Drucker fï¿½r MQTT
let lastMqttRejected = false; // merkt letzten Verbindungsfehler
// Speichere letzte Nachricht pro Topic fï¿½r den JSON-Inspector
const lastMessageByTopic = new Map();
let lastAmsData = [];
let lastAmsMeta = { topic: '', timestamp: '' };
let lastJobData = null;
let lastJobMeta = { topic: '', timestamp: '' };

// Health & Aggregation Tracking
let mqttStartTime = null;
let mqttMessageRateQueue = [];
let mqttPayloadSizes = [];
const RATE_WINDOW = 60; // 60 Sekunden fï¿½r Rate-Berechnung

function loadMqttTab() {
    loadMqttStatus();
    loadPrinterDropdown();
}

async function loadMqttStatus() {
    try {
        const response = await fetch('/api/mqtt/status');
        const data = await response.json();
        
        document.getElementById('mqttActiveConnections').textContent = data.active_connections;
        document.getElementById('mqttSubscribedCount').textContent = data.subscribed_topics.length;
        // Wichtig: Top-Card IDs verwenden, Live-Rohdaten-IDs NICHT ï¿½berschreiben
        const msgCountEl = document.getElementById('mqttMessageCount');
        if (msgCountEl) msgCountEl.textContent = String(data.message_buffer_size);
        const bufferEl = document.getElementById('mqttBufferSize');
        if (bufferEl) bufferEl.textContent = String(data.message_buffer_size);
        
        if (data.active_connections > 0) {
            document.getElementById('mqttStatus').textContent = 'Verbunden';
            document.getElementById('mqttStatus').style.color = 'var(--success)';
            mqttConnected = true;
            enableMqttControls(true);
            lastMqttRejected = false;
        } else if (lastMqttRejected || data.last_connect_error !== null) {
            const rcText = data.last_connect_error !== null ? ` (rc=${data.last_connect_error})` : '';
            document.getElementById('mqttStatus').textContent = 'Abgelehnt' + rcText;
            document.getElementById('mqttStatus').style.color = 'var(--error)';
            mqttConnected = false;
            enableMqttControls(false);
        } else {
            document.getElementById('mqttStatus').textContent = 'Getrennt';
            document.getElementById('mqttStatus').style.color = 'var(--error)';
            mqttConnected = false;
            enableMqttControls(false);
        }
        
        // Update topic list
        updateTopicList(data.subscribed_topics);
        
    } catch (error) {
        console.error('Fehler beim Laden des MQTT-Status:', error);
    }
}

// loadMqttMessagesBuffer() removed - no longer needed without mqttMessageStream

function enableMqttControls(enabled) {
    document.getElementById('mqttConnect').disabled = enabled;
    document.getElementById('mqttDisconnect').disabled = !enabled;
    document.getElementById('mqttSubscribe').disabled = !enabled;
    document.getElementById('mqttPublish').disabled = !enabled;
    document.getElementById('mqttSubscribeDefaults').disabled = !enabled;
}

function setupMqttListeners() {
    const panelRoot = document.getElementById('panel-mqtt');
    if (isNullElement(panelRoot)) {
        __logMissing('panel-mqtt');
        return;
    }
    // Connection
    document.getElementById('mqttConnect').addEventListener('click', connectMqtt);
    document.getElementById('mqttDisconnect').addEventListener('click', disconnectMqtt);
    document.getElementById('mqttRefreshStatus').addEventListener('click', loadMqttStatus);
    document.getElementById('mqttSubscribeDefaults').addEventListener('click', subscribeDefaultTopics);
    
    // Subscription
    document.getElementById('mqttSubscribe').addEventListener('click', subscribeTopic);
    document.getElementById('mqttTopic').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') subscribeTopic();
    });
    // Passwort-Toggle
    const pwToggle = document.getElementById('mqttPasswordToggle');
    const pwInput = document.getElementById('mqttPassword');
    if (pwToggle && pwInput) {
        pwToggle.addEventListener('click', () => {
            const isPw = pwInput.type === 'password';
            pwInput.type = isPw ? 'text' : 'password';
        });
    }
    
    // Suggested topics
    document.querySelectorAll('.topic-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // Seriennummer aus ausgewï¿½hltem MQTT-Drucker
            let serial = currentMqttPrinter?.cloud_serial || 'device_serial';
            let topic = btn.dataset.topic;
            if (topic.includes('+')) {
                topic = topic.replace('+', serial);
            }
            document.getElementById('mqttTopic').value = topic;
            subscribeTopic();
        });
    });
    
    // Publish
    document.getElementById('mqttPublish').addEventListener('click', publishMessage);
}

// === MQTT PRINTER DROPDOWN ===
// === MQTT PUBLISH MESSAGE ===
async function publishMessage() {
    const topic = document.getElementById('mqttPublishTopic').value.trim();
    const payload = document.getElementById('mqttPublishPayload').value;
    const qos = parseInt(document.getElementById('mqttPublishQos').value) || 0;
    if (!topic) {
        showNotification('Bitte Topic eingeben', 'warning');
        return;
    }
    try {
        const response = await fetch('/api/mqtt/publish', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic, payload, qos })
        });
        const data = await response.json();
        if (data.success) {
            showNotification('Nachricht verï¿½ffentlicht!', 'success');
        } else {
            showNotification('Fehler: ' + (data.message || 'Unbekannter Fehler'), 'error');
        }
    } catch (error) {
        showNotification('Publish Fehler: ' + error.message, 'error');
    }
}
async function loadPrinterDropdown() {
    const response = await fetch('/api/printers');
    const printers = await response.json();
    const dropdown = document.getElementById('mqttPrinterDropdown');
    if (!dropdown) return;
    const activePrinters = printers.filter(p => p.active);
    if (activePrinters.length === 0) {
        dropdown.innerHTML = '<small style="color:var(--text-dim);">Keine aktiven Drucker gefunden</small>';
        return;
    }
    const selectId = 'mqttPrinterSelect';
    dropdown.innerHTML = `
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
            <select id="${selectId}" class="select-input" style="min-width:240px;">
                ${activePrinters.map(p => {
                    const label = (p.name || p.ip_address || 'Unbekannt').replace(/"/g, '');
                    return `<option value="${p.id}"
                        data-ip="${p.ip_address || ''}"
                        data-port="${p.port || ''}"
                        data-serial="${p.cloud_serial || ''}"
                        data-type="${p.printer_type || ''}"
                        data-api="${p.api_key || ''}"
                        data-name="${label}">
                        ${label} (${p.ip_address || '-'}:${p.port || ''})
                    </option>`;
                }).join('')}
            </select>
            <button class="btn btn-secondary btn-sm" id="mqttPrinterApply">Setzen</button>
        </div>
    `;
    const select = document.getElementById(selectId);
    const applyBtn = document.getElementById('mqttPrinterApply');
    const applySelection = () => {
        if (!select || !select.selectedOptions.length) return;
        const opt = select.selectedOptions[0];
        const ip = opt.dataset.ip || '';
        const port = opt.dataset.port || '';
        const serial = opt.dataset.serial || '';
        const ptype = (opt.dataset.type || '').toLowerCase();
        const name = opt.dataset.name || ip;
        const apiKey = opt.dataset.api || '';
        currentMqttPrinter = {
            id: opt.value,
            ip_address: ip,
            port: port,
            cloud_serial: serial,
            printer_type: ptype,
            name: name,
            api_key: apiKey
        };
        document.getElementById('mqttBroker').value = ip;
        if (ptype === 'bambu') {
            document.getElementById('mqttPort').value = '8883';
        } else {
            document.getElementById('mqttPort').value = port;
        }
        const cid = (name || ip).replace(/\s/g, '_').toLowerCase();
        document.getElementById('mqttClientId').value = cid || 'filamenthub_client';
        if (apiKey) document.getElementById('mqttPassword').value = apiKey;
        if (serial) {
            document.getElementById('mqttTopic').value = `device/${serial}/report`;
        }
    };
    if (select) {
        select.addEventListener('change', applySelection);
    }
    if (applyBtn) {
        applyBtn.addEventListener('click', applySelection);
    }
    // initial apply first
    applySelection();
}

// === LIVE RAW MQTT DATA ===
let rawMqttWebSocket = null;
let rawHandlerActive = false;
let rawMessagesReceived = 0;
let rawPaused = false; // Controls deAktiviert -> bleibt false
let rawPretty = true;  // Immer hï¿½bsche JSON-Darstellung
// Flood-Schutz: nur die letzte Nachricht zwischenspeichern und periodisch anzeigen
let rawBufferLast = null;
let rawFlushTimer = null;
const RAW_MAX_ENTRIES = 20;
const RAW_FLUSH_INTERVAL_MS = 500;

function renderParsedMessage(obj, streamDiv) {
    const wrapper = document.createElement('div');
    wrapper.style.borderBottom = '1px solid #222';
    wrapper.style.padding = '6px 0';
    const ts = new Date().toLocaleTimeString();
    const header = document.createElement('div');
    header.innerHTML = `<span style="color:#6cf;font-weight:600;">${ts}</span>`;
    try {
        const parts = [];
        if (obj.command) parts.push(`cmd=${obj.command}`);
        if (obj.percent !== undefined) parts.push(`pct=${obj.percent}`);
        if (obj.nozzle_temper !== undefined) parts.push(`nozzle=${obj.nozzle_temper}`);
        if (obj.bed_temper !== undefined) parts.push(`bed=${obj.bed_temper}`);
        if (parts.length) {
            header.innerHTML += ` <span style="color:#aaa;">${parts.join(' - ')}</span>`;
        }
    } catch {}
    wrapper.appendChild(header);
    const pre = document.createElement('pre');
    pre.style.color = '#ddd';
    pre.style.background = '#222';
    pre.style.padding = '6px';
    pre.style.borderRadius = '4px';
    pre.style.margin = '4px 0 0 0';
    pre.textContent = JSON.stringify(obj, null, 2);
    wrapper.appendChild(pre);
    streamDiv.appendChild(wrapper);
}

function findJsonObject(text) {
    let start = text.indexOf('{');
    if (start === -1) return null;
    let depth = 0;
    for (let i = start; i < text.length; i++) {
        const ch = text[i];
        if (ch === '{') depth++;
        else if (ch === '}') {
            depth--;
            if (depth === 0) {
                const candidate = text.slice(start, i + 1);
                try {
                    return JSON.parse(candidate);
                } catch (e) {
                    return null;
                }
            }
        }
    }
    return null;
}

function tryExtractJson(line) {
    const t = line.trim();
    // 1) Direktes JSON-Objekt
    if (t.startsWith('{') && t.endsWith('}')) {
        try { return JSON.parse(t); } catch {}
    }
    // 2) JSON-stringifizierter JSON-String: "{\"a\":1}"
    if ((t.startsWith('"') && t.endsWith('"')) || (t.startsWith("'") && t.endsWith("'"))) {
        try {
            const inner = JSON.parse(t);
            if (typeof inner === 'string') {
                const innerTrim = inner.trim();
                if (innerTrim.startsWith('{') && innerTrim.endsWith('}')) {
                    try { return JSON.parse(innerTrim); } catch {}
                }
                // 3) JSON innerhalb des Strings suchen
                const nested = findJsonObject(inner);
                if (nested) return nested;
            }
        } catch {}
    }
    // 4) JSON irgendwo in der Zeile suchen
    const nested = findJsonObject(t);
    if (nested) return nested;
    return null;
}

function connectRawMqttWebSocket() {
    if (rawMqttWebSocket) {
        try { rawMqttWebSocket.close(); } catch {}
    }
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/mqtt/ws/logs/mqtt?tail=0`;
    rawMqttWebSocket = new WebSocket(wsUrl);
    rawMqttWebSocket.onopen = () => {
        rawMessagesReceived = 0;
        rawHandlerActive = true;
        updateRawHandlerStatus();
        const streamDiv = document.getElementById('mqttLiveRaw');
        if (streamDiv) {
            streamDiv.innerHTML = '<p style="color: var(--text-dim); text-align: center; padding: 8px;">Letzte eingehende Nachricht wird hier angezeigt</p>';
        }
        // Starte periodisches Flush der letzten Nachricht
        if (rawFlushTimer) clearInterval(rawFlushTimer);
        rawFlushTimer = setInterval(() => {
            if (rawPaused) return;
            const streamDiv = document.getElementById('mqttLiveRaw');
            if (!streamDiv) return;
            const line = rawBufferLast;
            if (!line) return;
            // Entferne Platzhalter
            const ph = streamDiv.querySelector('p');
            if (ph) streamDiv.removeChild(ph);
            streamDiv.appendChild(line);
            // Begrenze Eintrï¿½ge
            while (streamDiv.children.length > RAW_MAX_ENTRIES) {
                streamDiv.removeChild(streamDiv.firstChild);
            }
            streamDiv.scrollTop = streamDiv.scrollHeight;
            rawBufferLast = null; // nach Anzeige zurï¿½cksetzen
        }, RAW_FLUSH_INTERVAL_MS);
    };
    rawMqttWebSocket.onmessage = (event) => {
        rawMessagesReceived++;
        updateRawHandlerStatus();
        if (rawPaused) return;
        const logLine = String(event.data ?? '');
        // Unescape, falls es ein JSON-String ist
        let display = logLine;
        try {
            const maybe = JSON.parse(logLine);
            if (typeof maybe === 'string') display = maybe;
        } catch {}
        const pre = document.createElement('pre');
        pre.style.color = '#ddd';
        pre.style.borderBottom = '1px solid #222';
        pre.style.margin = 0;
        // Nur eine kurze Vorschau: erste 400 Zeichen
        const preview = display.length > 400 ? display.slice(0, 400) + ' ï¿½' : display;
        // Zeit + ggf. Topic-Andeutung aus Inhalt
        const ts = new Date().toLocaleTimeString('de-DE');
        pre.textContent = `[${ts}] ${preview}`;
        // Puffer nur die letzte Zeile, ersetzt vorherige
        rawBufferLast = pre;
        
        // Auch direkt in Publish-Fenster spiegeln
        try {
            if (rawOutputPaused || !liveViewEnabled) return;
            const rawDivPublish = document.getElementById('mqttLiveRawPublish');
            if (rawDivPublish) {
                const ph = rawDivPublish.querySelector('p');
                if (ph) rawDivPublish.removeChild(ph);
                const line = document.createElement('pre');
                line.style.color = '#ddd';
                line.style.borderBottom = '1px solid #222';
                line.style.margin = 0;
                line.textContent = `[${ts}] ${preview}`;
                rawDivPublish.appendChild(line);
                while (rawDivPublish.children.length > 20) rawDivPublish.removeChild(rawDivPublish.firstChild);
                rawDivPublish.scrollTop = rawDivPublish.scrollHeight;
            }
        } catch {}
    };
    rawMqttWebSocket.onerror = () => {
        rawHandlerActive = false;
        updateRawHandlerStatus();
    };
    rawMqttWebSocket.onclose = () => {
        rawHandlerActive = false;
        updateRawHandlerStatus();
        if (rawFlushTimer) {
            clearInterval(rawFlushTimer);
            rawFlushTimer = null;
        }
    };
}

function updateRawHandlerStatus() {
    // Sichtbare Elemente im Card-Header
    const connEl = document.getElementById('mqttConnectionStatus');
    const handlersEl = document.getElementById('mqttHandlersActive');
    const msgsEl = document.getElementById('mqttMessagesReceived');

    if (connEl) {
        connEl.textContent = rawHandlerActive ? 'Connected' : 'Disconnected';
        connEl.style.color = rawHandlerActive ? 'var(--success)' : 'var(--error)';
        connEl.style.fontWeight = 'bold';
    }
    if (handlersEl) {
        handlersEl.textContent = rawHandlerActive ? '1' : '0';
    }
    if (msgsEl) {
        msgsEl.textContent = String(rawMessagesReceived);
    }

    // Fallback: alte Debug-Elemente
    let rawHandlerStatus = document.getElementById('rawHandlerStatus');
    let liveRawStatus = document.getElementById('liveRawStatus');
    if (rawHandlerStatus) {
        rawHandlerStatus.textContent = `Handler Aktiv: ${rawHandlerActive ? 1 : 0}`;
        rawHandlerStatus.style.color = rawHandlerActive ? 'orange' : 'gray';
    }
    if (liveRawStatus) {
        liveRawStatus.textContent = rawHandlerActive ? 'Verbunden' : 'Disconnected';
        liveRawStatus.style.color = rawHandlerActive ? 'var(--success)' : 'var(--error)';
    }
}

// Eigene Pause-Variable fï¿½r Live Raw Output
let rawOutputPaused = false;
let liveViewEnabled = true;

function toggleLiveView(enabled) {
    liveViewEnabled = enabled;
    const btnOn = document.getElementById('liveViewOn');
    const btnOff = document.getElementById('liveViewOff');
    const rawPublish = document.getElementById('mqttLiveRawPublish');
    
    if (enabled) {
        if (btnOn && btnOff) {
            btnOn.classList.remove('btn-secondary');
            btnOn.classList.add('btn-success');
            btnOff.classList.remove('btn-danger');
            btnOff.classList.add('btn-secondary');
        }
        if (rawPublish) {
            rawPublish.style.opacity = '1';
            rawPublish.style.filter = 'none';
            rawPublish.innerHTML = '<p class="liveview-placeholder" style="color:#00ff00; text-align:center; padding:12px;"> Live-Ansicht AN - warte auf Daten</p>';
        }
        console.log(' Live-Ansicht AktivIERT');
    } else {
        if (btnOn && btnOff) {
            btnOn.classList.remove('btn-success');
            btnOn.classList.add('btn-secondary');
            btnOff.classList.remove('btn-secondary');
            btnOff.classList.add('btn-danger');
        }
        if (rawPublish) {
            rawPublish.style.opacity = '0.8';
            rawPublish.style.filter = 'grayscale(0.4)';
            rawPublish.innerHTML = '<p class="liveview-placeholder" style="color:#888; text-align:center; padding:12px;"> Live-Ansicht AUS - keine neuen Zeilen</p>';
        }
        console.log(' Live-Ansicht DEAktivIERT');
    }
}

function toggleRawOutputPause() {
    rawOutputPaused = !rawOutputPaused;
    console.log(' Raw Output Pause:', rawOutputPaused);
    const btn = document.getElementById('rawOutputPause');
    if (!btn) return;
    if (rawOutputPaused) {
        btn.textContent = ' Resume';
        btn.classList.remove('btn-secondary');
        btn.classList.add('btn-success');
        console.log('? PAUSIERT - Keine neuen Zeilen werden angezeigt');
    } else {
        btn.textContent = ' Pause';
        btn.classList.remove('btn-success');
        btn.classList.add('btn-secondary');
        console.log(' Aktiv - Zeilen werden wieder angezeigt');
    }
}

// Einfache Funktion zum Schreiben ins Live Raw Output
function addToLiveRawOutput(text) {
    // Prï¿½fe Live-Ansicht-Status
    if (!liveViewEnabled) {
        console.log(' IGNORIERT (Live-Ansicht aus):', text.substring(0, 50));
        return;
    }
    
    // Prï¿½fe Pause-Status
    if (rawOutputPaused) {
        console.log(' IGNORIERT (pausiert):', text.substring(0, 50));
        return;
    }
    
    const div = document.getElementById('mqttLiveRawPublish');
    if (!div) {
        console.error('mqttLiveRawPublish nicht gefunden!');
        return;
    }
    // Entferne Platzhalter nur bei grï¿½nem "AN"-Text
    const ph = div.querySelector('p.liveview-placeholder');
    if (ph && ph.textContent.includes('AN')) {
        div.innerHTML = '';
    }
    
    const line = document.createElement('div');
    line.style.cssText = 'color: #0f0; font-size: 0.85rem; padding: 4px; border-bottom: 1px solid #333;';
    line.textContent = text;
    div.appendChild(line);
    
    // Limit auf 30 Zeilen
    while (div.children.length > 30) {
        div.removeChild(div.firstChild);
    }
    div.scrollTop = div.scrollHeight;
    console.log('? Geschrieben:', text);
}

// Filter-Funktion fï¿½r Live Raw Output
function filterRawOutput() {
    const searchInput = document.getElementById('rawOutputSearch');
    const container = document.getElementById('mqttLiveRawPublish');
    if (!searchInput || !container) return;
    const searchTerm = searchInput.value.toLowerCase();
    const lines = container.querySelectorAll('div, pre');
    lines.forEach(line => {
        line.style.display = line.textContent.toLowerCase().includes(searchTerm) ? '' : 'none';
    });
}

// Starte die Verbindung beim Laden des MQTT-Tabs
document.addEventListener('DOMContentLoaded', () => {
    connectRawMqttWebSocket();
    
    // Test-Nachricht
    setTimeout(() => {
        addToLiveRawOutput(' Live Raw Output Aktiv - Warte auf Daten...');
    }, 500);
});
// Modernes Cleanup beim Seitenwechsel/Neuladen/Tabwechsel
window.addEventListener("pagehide", () => {
    if (!mqttConnected) return;

    const brokerElem = document.getElementById('mqttBroker');
    const portElem = document.getElementById('mqttPort');

    if (brokerElem && portElem) {
        const broker = brokerElem.value;
        const port = parseInt(portElem.value);
        navigator.sendBeacon(
            `/api/mqtt/disconnect?broker=${encodeURIComponent(broker)}&port=${port}`
        );
    }

    if (mqttWebSocket) {
        try { mqttWebSocket.close(); } catch (e) {}
    }
});

// Fallback fÃ¼r Browser, die pagehide nicht vollstÃ¤ndig unterstÃ¼tzen
document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "hidden") return;
    if (!mqttConnected) return;

    const brokerElem = document.getElementById('mqttBroker');
    const portElem = document.getElementById('mqttPort');

    if (brokerElem && portElem) {
        const broker = brokerElem.value;
        const port = parseInt(portElem.value);
        navigator.sendBeacon(
            `/api/mqtt/disconnect?broker=${encodeURIComponent(broker)}&port=${port}`
        );
    }

    if (mqttWebSocket) {
        try { mqttWebSocket.close(); } catch (e) {}
    }
});
const DEFAULT_BAMBU_TOPICS = [
    'device/+/report',
    'device/+/print',
    'device/+/camera',
    'device/+/ams',
    'device/+/temperature',
    'device/+/speed',
    'device/+/layer',
    '#'
];

async function subscribeDefaultTopics() {
    let serial = '00M09A372601070';
    let serialElem = document.getElementById('printerSerial');
    if (serialElem && serialElem.value) {
        serial = serialElem.value;
    } else {
        // Fallback: Suche nach Seriennummer in gespeicherten Druckern
        const printerCards = document.querySelectorAll('.printer-card');
        for (let card of printerCards) {
            const sn = card.getAttribute('data-serial');
            if (sn) { serial = sn; break; }
        }
    }
    for (let topic of DEFAULT_BAMBU_TOPICS) {
        if (topic.includes('+')) {
            topic = topic.replace('+', serial);
        }
        try {
            const response = await fetch('/api/mqtt/subscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic })
            });
            const data = await response.json();
            if (data.success) {
                mqttSubscribedTopics.add(topic);
                activateRawHandler();
            } else {
                showNotification(`Subscribe fehlgeschlagen fï¿½r ${topic}: ${data.message || 'Unbekannter Fehler'}`, 'error');
            }
        } catch (error) {
            showNotification(`Subscribe Fehler fï¿½r ${topic}: ${error.message}`, 'error');
        }
    }
    // Dummy-Funktion: Raw-Handler Aktivieren (UI-Update)
    function activateRawHandler() {
        // Stelle sicher, dass die Status-Elemente existieren
        let rawHandlerStatus = document.getElementById('rawHandlerStatus');
        if (!rawHandlerStatus) {
            rawHandlerStatus = document.createElement('span');
            rawHandlerStatus.id = 'rawHandlerStatus';
            rawHandlerStatus.style.marginLeft = '10px';
            const rawStatusDiv = document.getElementById('liveRawStatusDiv') || document.body;
            rawStatusDiv.appendChild(rawHandlerStatus);
        }
        let liveRawStatus = document.getElementById('liveRawStatus');
        if (!liveRawStatus) {
            liveRawStatus = document.createElement('span');
            liveRawStatus.id = 'liveRawStatus';
            liveRawStatus.style.marginLeft = '10px';
            const rawStatusDiv = document.getElementById('liveRawStatusDiv') || document.body;
            rawStatusDiv.appendChild(liveRawStatus);
        }
        rawHandlerStatus.textContent = 'Handler Aktiv: 1';
        liveRawStatus.textContent = 'Verbunden';
    }
    updateTopicList(Array.from(mqttSubscribedTopics));
    showNotification('Bambu-Topics abonniert', 'success');
}

async function connectMqtt() {
    const broker = document.getElementById('mqttBroker').value;
    const port = parseInt(document.getElementById('mqttPort').value);
    const clientId = document.getElementById('mqttClientId').value;
    const username = document.getElementById('mqttUsername').value || null;
    const password = document.getElementById('mqttPassword').value || null;
    const cloudSerial = currentMqttPrinter?.cloud_serial || null;
    const use_tls = port === 8883; // Bambu nutzt i.d.R. TLS auf 8883
    const tls_insecure = true;     // Zertifikat nicht prï¿½fen (Drucker-CA)
    
    if (!broker) {
        showNotification('Bitte Broker-Adresse eingeben', 'warning');
        return;
    }
    
    try {
        const response = await fetch('/api/mqtt/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ broker, port, client_id: clientId, cloud_serial: cloudSerial, username, password, use_tls, tls_insecure })
        });
        let data = null;
        try { data = await response.json(); } catch {}
        if (response.ok && data && data.success) {
            showNotification(`Verbunden mit ${broker}:${port}`, 'success');
            mqttConnected = true;
            lastMqttRejected = false;
            enableMqttControls(true);
            const statusEl = document.getElementById('mqttStatus');
            if (statusEl) {
                statusEl.textContent = 'Verbunden';
                statusEl.style.color = 'var(--success)';
            }
            
            // Connect WebSocket for live streaming
            connectMqttWebSocket();
            
            // Reset Health Tracking
            mqttStartTime = Date.now();
            mqttMessageRateQueue = [];
            mqttPayloadSizes = [];
            
            // Refresh status
            setTimeout(loadMqttStatus, 500);
        } else {
            const msg = (data && (data.detail || data.message)) || `HTTP ${response.status}`;
            showNotification(`MQTT Verbindung fehlgeschlagen: ${msg}`, 'error');
            const statusEl = document.getElementById('mqttStatus');
            if (statusEl) {
                statusEl.textContent = 'Abgelehnt';
                statusEl.style.color = 'var(--error)';
            }
            mqttConnected = false;
            lastMqttRejected = true;
            enableMqttControls(false);
        }
    } catch (error) {
        showNotification('Verbindungsfehler: ' + error.message, 'error');
        const statusEl = document.getElementById('mqttStatus');
        if (statusEl) {
            statusEl.textContent = 'Abgelehnt';
            statusEl.style.color = 'var(--error)';
        }
        mqttConnected = false;
        lastMqttRejected = true;
        enableMqttControls(false);
    }
}

async function disconnectMqtt() {
    const broker = document.getElementById('mqttBroker').value;
    const port = parseInt(document.getElementById('mqttPort').value);

    if (!broker || Number.isNaN(port)) {
        showNotification('Bitte Broker und Port angeben', 'warning');
        return;
    }

    // UI sofort umschalten
    const statusEl = document.getElementById('mqttStatus');
    if (statusEl) {
        statusEl.textContent = 'Trennen...';
        statusEl.style.color = 'var(--text-dim)';
    }
    showNotification('MQTT wird getrennt...', 'info');

    try {
        // Query-Parameter statt JSON-Body!
        const url = `/api/mqtt/disconnect?broker=${encodeURIComponent(broker)}&port=${port}`;
        const response = await fetch(url, { method: 'POST' });
        let result = {};
        try { result = await response.json(); } catch {}
        if (!response.ok || result.success === false) {
            const msg = result.detail || result.message || `HTTP ${response.status}`;
            showNotification('Fehler beim Trennen: ' + msg, 'error');
        } else {
            showNotification('MQTT Verbindung getrennt', 'success');
        }
        mqttConnected = false;
        lastMqttRejected = false;
        enableMqttControls(false);
        const statusEl = document.getElementById('mqttStatus');
        if (statusEl) {
            statusEl.textContent = 'Getrennt';
            statusEl.style.color = 'var(--error)';
        }
        if (mqttWebSocket) {
            try { mqttWebSocket.close(); } catch {}
            mqttWebSocket = null;
        }
        mqttSubscribedTopics.clear();
        updateTopicList([]);
        setTimeout(loadMqttStatus, 500);
    } catch (error) {
        showNotification('Netzwerkfehler beim Trennen', 'error');
    }
}

function connectMqttWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/mqtt/ws`;

    if (mqttWebSocket) {
        mqttWebSocket.close();
    }
    if (pingInterval) {
        clearInterval(pingInterval);
        pingInterval = null;
    }
    if (pongTimeout) {
        clearTimeout(pongTimeout);
        pongTimeout = null;
    }

    mqttWebSocket = new WebSocket(wsUrl);

    setStatusPending();

    mqttWebSocket.onopen = () => {
        if (mqttWebSocket && mqttWebSocket.readyState === WebSocket.OPEN) {
            console.log('?' + ' MQTT WebSocket connected');
            const statusEl = document.getElementById('mqttStatus');
            if (statusEl) statusEl.textContent = 'Verbunden';
            setStatusConnected();
        }

        pingInterval = setInterval(() => {
            if (!mqttWebSocket || mqttWebSocket.readyState !== WebSocket.OPEN) return;
            mqttWebSocket.send(JSON.stringify({ type: "ping" }));
            const pingEl = document.getElementById("pingStatus");
            if (pingEl) pingEl.textContent = "Ping...";
            if (pongTimeout) clearTimeout(pongTimeout);
            pongTimeout = setTimeout(() => {
                const pingElTimeout = document.getElementById("pingStatus");
                if (pingElTimeout) pingElTimeout.textContent = "No Pong";
                setStatusDisconnected();
            }, 3000);
        }, 5000);
    };

    mqttWebSocket.onmessage = (event) => {
        setStatusConnected();

        lastMessageTimestamp = Date.now();
        const lastMsgEl = document.getElementById("lastMessageTime");
        if (lastMsgEl) lastMsgEl.textContent = formatTimeAgo(lastMessageTimestamp);
        sparklineData.push(1);
        if (sparklineData.length > SPARKLINE_MAX) sparklineData.shift();
        renderSparkline();

        let parsed = null;
        try {
            parsed = JSON.parse(event.data);
            if (parsed && parsed.type === "pong") {
                const pingEl = document.getElementById("pingStatus");
                if (pingEl) pingEl.textContent = "Pong";
                if (pongTimeout) clearTimeout(pongTimeout);
                setTimeout(() => {
                    sparklineData.push(0);
                    if (sparklineData.length > SPARKLINE_MAX) sparklineData.shift();
                    renderSparkline();
                }, 200);
                return;
            }
        } catch {
            parsed = null;
        }

        if (mqttPaused) {
            setTimeout(() => {
                sparklineData.push(0);
                if (sparklineData.length > SPARKLINE_MAX) sparklineData.shift();
                renderSparkline();
            }, 200);
            return;
        }

        try {
            const rawDiv = document.getElementById('mqttLiveRaw');
            const rawDivPublish = document.getElementById('mqttLiveRawPublish');
            const ts = new Date().toLocaleTimeString('de-DE');
            const preview = String(event.data).length > 400 ? String(event.data).slice(0, 400) + ' ...' : String(event.data);
            const displayPayload2 = String(event.data);

            if (rawDiv) {
                const ph = rawDiv.querySelector('p');
                if (ph) rawDiv.removeChild(ph);
                const line = document.createElement('pre');
                line.style.color = '#ddd';
                line.style.borderBottom = '1px solid #222';
                line.style.margin = 0;
                line.textContent = `[${ts}] ${preview}`;
                rawDiv.appendChild(line);
                while (rawDiv.children.length > 200) rawDiv.removeChild(rawDiv.firstChild);
                rawDiv.scrollTop = rawDiv.scrollHeight;
            }
            if (rawDivPublish && !rawOutputPaused && liveViewEnabled) {
                const ph2 = rawDivPublish.querySelector('p');
                if (ph2) rawDivPublish.removeChild(ph2);
                const line2 = document.createElement('pre');
                line2.style.color = '#ddd';
                line2.style.borderBottom = '1px solid #222';
                line2.style.margin = 0;
                const ts2 = new Date().toLocaleTimeString('de-DE');
                const preview2 = displayPayload2.length > 400 ? displayPayload2.slice(0, 400) + ' ...' : displayPayload2;
                line2.textContent = `[${ts2}] ${preview2}`;
                rawDivPublish.appendChild(line2);
                while (rawDivPublish.children.length > 20) rawDivPublish.removeChild(rawDivPublish.firstChild);
                rawDivPublish.scrollTop = rawDivPublish.scrollHeight;
            }
        } catch {}

        if (!parsed) {
            setTimeout(() => {
                sparklineData.push(0);
                if (sparklineData.length > SPARKLINE_MAX) sparklineData.shift();
                renderSparkline();
            }, 200);
            return;
        }

        if (parsed.type === 'status') {
            setTimeout(() => {
                sparklineData.push(0);
                if (sparklineData.length > SPARKLINE_MAX) sparklineData.shift();
                renderSparkline();
            }, 200);
            return;
        }

        displayMqttMessage(parsed);
        mqttMessageCount++;
        document.getElementById('mqttMessageCount').textContent = mqttMessageCount;
        addToLiveRawOutput(`[${new Date().toLocaleTimeString('de-DE')}] ${parsed.topic || 'unknown'}: ${String(parsed.payload || '').substring(0, 200)}`);

        setTimeout(() => {
            sparklineData.push(0);
            if (sparklineData.length > SPARKLINE_MAX) sparklineData.shift();
            renderSparkline();
        }, 200);
    };

    mqttWebSocket.onerror = (error) => {
        console.error('?' + ' MQTT WebSocket error:', error);
        document.getElementById('mqttStatus').textContent = 'Fehler';
        setStatusDisconnected();
        const pingEl = document.getElementById("pingStatus");
        if (pingEl) pingEl.textContent = "Disconnected";
        if (pingInterval) {
            clearInterval(pingInterval);
            pingInterval = null;
        }
        if (pongTimeout) {
            clearTimeout(pongTimeout);
            pongTimeout = null;
        }
    };

    mqttWebSocket.onclose = () => {
        console.log(' MQTT WebSocket closed');
        document.getElementById('mqttStatus').textContent = 'Getrennt';
        setStatusDisconnected();
        const pingEl = document.getElementById("pingStatus");
        if (pingEl) pingEl.textContent = "Disconnected";
        if (pingInterval) {
            clearInterval(pingInterval);
            pingInterval = null;
        }
        if (pongTimeout) {
            clearTimeout(pongTimeout);
            pongTimeout = null;
        }
    };
}async function subscribeTopic() {
    const topic = document.getElementById('mqttTopic').value.trim();
    
    if (!topic) {
        showNotification('Bitte Topic eingeben', 'warning');
        return;
    }
    
    if (mqttSubscribedTopics.has(topic)) {
        showNotification('Topic bereits abonniert', 'info');
        return;
    }
    
    try {
        const response = await fetch('/api/mqtt/subscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`Abonniert: ${topic}`, 'success');
            mqttSubscribedTopics.add(topic);
            updateTopicList(Array.from(mqttSubscribedTopics));
            document.getElementById('mqttTopic').value = '';
        }
    } catch (error) {
        showNotification('Subscribe Fehler: ' + error.message, 'error');
    }
}

async function unsubscribeTopic(topic) {
    try {
        const response = await fetch('/api/mqtt/unsubscribe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ topic })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`Abgemeldet: ${topic}`, 'info');
            mqttSubscribedTopics.delete(topic);
            updateTopicList(Array.from(mqttSubscribedTopics));
        }
    } catch (error) {
        showNotification('Unsubscribe Fehler: ' + error.message, 'error');
    }
}

function updateTopicList(topics) {
    const listDiv = document.getElementById('mqttTopicList');
    
    if (topics.length === 0) {
        listDiv.innerHTML = '<p style="color: var(--text-dim); text-align: center; padding: 10px;">No subscriptions yet</p>';
        return;
    }
    
    listDiv.innerHTML = '';
    topics.forEach(topic => {
        const item = document.createElement('div');
        item.className = 'topic-item';
        item.innerHTML = `
            <span class="topic-name">${topic}</span>
            <button class="btn btn-danger btn-sm" onclick="unsubscribeTopic('${topic}')">
                ï¿½
            </button>
        `;
        // Klick auf Topic ï¿½ffnet JSON-Inspector (letzte bekannte Nachricht)
        const nameEl = item.querySelector('.topic-name');
        if (nameEl) {
            nameEl.style.cursor = 'pointer';
            nameEl.title = 'Im JSON-Inspector anzeigen';
            nameEl.addEventListener('click', () => showInspectorForTopic(topic));
        }
        listDiv.appendChild(item);
    });
}

function safe(val, fallback = "n/a") {
    return (val !== null && val !== undefined && val !== "") ? val : fallback;
}

function safeGet(obj, path, defaultValue = "n/a") {
    if (!obj || !path) return defaultValue;
    try {
        const parts = path.split(".");
        let current = obj;
        for (const p of parts) {
            if (current === null || current === undefined || !(p in current)) {
                return defaultValue;
            }
            current = current[p];
        }
        return current ?? defaultValue;
    } catch {
        return defaultValue;
    }
}

function renderPrinter(printer) {
    if (!printer) {
        return "<div>No PrinterData received.</div>";
    }

    return `
        <div class="printer-block">
            <h2>Printer Status</h2>
            <pre>
Model:          ${safe(printer.model)}
MQTT Version:   ${safe(printer.mqtt_version)}
Timestamp:      ${safe(printer.timestamp)}
State:          ${safe(printer.state)}
Progress:       ${safe(printer.progress)} %

Layer:          ${safe(printer.layer?.current)} / ${safe(printer.layer?.total)}

Temperatures:
 - Nozzle:      ${safe(printer.temperature?.nozzle)}
 - Bed:         ${safe(printer.temperature?.bed)}
 - Chamber:     ${safe(printer.temperature?.chamber)}

Fans:
 - Part:        ${safe(printer.fan?.part_cooling)}
 - Aux:         ${safe(printer.fan?.aux)}
 - Chamber:     ${safe(printer.fan?.chamber)}

AMS:            ${safe(JSON.stringify(printer.ams, null, 2))}

Capabilities:
 - AMS:          ${safe(printer.capabilities?.has_ams)}
 - LiDAR:        ${safe(printer.capabilities?.has_lidar)}
 - Chamber Temp: ${safe(printer.capabilities?.has_chamber_temp)}
 - Aux Fan:      ${safe(printer.capabilities?.has_aux_fan)}

Job:
 - File:        ${safe(printer.job?.file)}
 - Elapsed:     ${safe(printer.job?.time_elapsed)}
 - Remaining:   ${safe(printer.job?.time_remaining)}

Error:          <span style="color:${printer.error ? 'red' : 'white'}">
                    ${safe(printer.error)}
                </span>

Extra:
${JSON.stringify(printer.extra, null, 2)}
            </pre>
        </div>
    `;
}

function renderMessage(msg) {
    const printer = msg.printer || null;
    const raw = msg.raw || null;

    const pdEl = document.getElementById("printerData");
    if (pdEl) pdEl.innerHTML = renderPrinter(printer);

    const rawEl = document.getElementById("rawData");
    if (rawEl) {
        rawEl.innerHTML = `
        <h2>Raw Payload</h2>
        <pre>${JSON.stringify(raw, null, 2)}</pre>
    `;
    }
}

function displayMqttMessage(message) {
    // Increment message counter
    const counterEl = document.getElementById('mqttMessagesReceived');
    if (counterEl) {
        const currentCount = parseInt(counterEl.textContent) || 0;
        counterEl.textContent = currentCount + 1;
    }
    
    // Parse JSON payload for Inspector and Health tracking
    let payload = message.payload ?? '';
    let parsedObj = null;
    const printerData = message.printer || null;
    
    // Try to parse JSON
    try {
        const firstBrace = payload.indexOf('{');
        const jsonPart = firstBrace !== -1 ? payload.substring(firstBrace) : payload;
        parsedObj = JSON.parse(jsonPart);
    } catch {}
    
    const timestamp = message.timestamp
        ? new Date(message.timestamp).toLocaleTimeString('de-DE')
        : new Date().toLocaleTimeString('de-DE');

    // Zusï¿½tzlich: Spiegle jede eingehende Nachricht in den Raw-Output
    // So sieht man garantiert Daten im Bereich "Live Raw MQTT Data".
    try {
        const rawDiv = document.getElementById('mqttLiveRaw');
        const rawDivPublish = document.getElementById('mqttLiveRawPublish');
        if (rawDiv) {
            // Entferne Platzhalter, falls vorhanden
            const ph = rawDiv.querySelector('p');
            if (ph) rawDiv.removeChild(ph);
            // Unescape falls Payload ein JSON-String ist
            let displayPayload = String(message.payload ?? '');
            try {
                const maybe = JSON.parse(displayPayload);
                if (typeof maybe === 'string') displayPayload = maybe;
            } catch {}
            const line = document.createElement('pre');
            line.style.color = '#ddd';
            line.style.borderBottom = '1px solid #222';
            line.style.margin = 0;
            line.textContent = `[${timestamp}] ${message.topic || ''} \n${displayPayload}`;
            rawDiv.appendChild(line);
            // Begrenze auf 200 Eintrï¿½ge
            while (rawDiv.children.length > 200) {
                rawDiv.removeChild(rawDiv.firstChild);
            }
            rawDiv.scrollTop = rawDiv.scrollHeight;
        }
        if (rawDivPublish && !rawOutputPaused && liveViewEnabled) {
            // Entferne Platzhalter
            const ph2 = rawDivPublish.querySelector('p');
            if (ph2) rawDivPublish.removeChild(ph2);
            // Unescape falls Payload ein JSON-String ist
            let displayPayload2 = String(message.payload ?? '');
            try {
                const maybe2 = JSON.parse(displayPayload2);
                if (typeof maybe2 === 'string') displayPayload2 = maybe2;
            } catch {}
            const line2 = document.createElement('pre');
            line2.style.color = '#ddd';
            line2.style.borderBottom = '1px solid #222';
            line2.style.margin = 0;
            const ts2 = new Date().toLocaleTimeString('de-DE');
            const preview2 = displayPayload2.length > 400 ? displayPayload2.slice(0, 400) + ' ï¿½' : displayPayload2;
            line2.textContent = `[${ts2}] ${preview2}`;
            rawDivPublish.appendChild(line2);
            while (rawDivPublish.children.length > 20) {
                rawDivPublish.removeChild(rawDivPublish.firstChild);
            }
            rawDivPublish.scrollTop = rawDivPublish.scrollHeight;
        }
    } catch {}

    // Speichere letzte Nachricht dieses Topics fï¿½r den Inspector
    if (message.topic) {
        lastMessageByTopic.set(message.topic, {
            topic: message.topic,
            timestamp,
            raw: message.payload ?? '',
            json: parsedObj,
            ams: Array.isArray(message.ams) ? message.ams : [],
            job: message.job || null,
            printer: printerData || null
        });
    }
    if (message.topic && Array.isArray(message.ams)) {
        const entry = lastMessageByTopic.get(message.topic);
        if (entry) {
            entry.ams = message.ams;
        }
    }
    if (Array.isArray(message.ams) && message.ams.length > 0) {
        lastAmsData = message.ams;
        lastAmsMeta = { topic: message.topic || '', timestamp };
        renderAmsOverview(lastAmsData, lastAmsMeta);
    }
    if (parsedObj && typeof parsedObj === 'object' && message.topic && String(message.topic).endsWith('/report')) {
        let printRoot = parsedObj.print || parsedObj;
        if (printerData && typeof printerData === 'object') {
            printRoot = { ...printRoot };
            printRoot.gcode_state = printerData.state ?? printRoot.gcode_state ?? printRoot.state;
            printRoot.state = printerData.state ?? printRoot.state;
            printRoot.progress = printerData.progress ?? printRoot.progress;
            printRoot.layer_num = (printerData.layer && printerData.layer.current != null) ? printerData.layer.current : printRoot.layer_num;
            printRoot.total_layer = (printerData.layer && printerData.layer.total != null) ? printerData.layer.total : printRoot.total_layer;
            const temps = printerData.temperature || {};
            printRoot.nozzle_temp = temps.nozzle ?? printRoot.nozzle_temp;
            printRoot.bed_temp = temps.bed ?? printRoot.bed_temp;
            printRoot.chamber_temp = temps.chamber ?? printRoot.chamber_temp;
            const job = printerData.job || {};
            printRoot.time_remaining = job.time_remaining ?? printRoot.time_remaining;
            printRoot.file = job.file ?? printRoot.file;
        }
        const amsRoot = printRoot.ams || {};
        const trayTarget = toSafeInt(amsRoot.tray_tar);
        const trayNow = toSafeInt(amsRoot.tray_now);
        const vt = printRoot.vt_tray || (Array.isArray(printRoot.vir_slot) ? printRoot.vir_slot[0] : null);

        // Ermittle Anforderung aus virtual_tray oder ersatzweise aus dem Tray des Ziel-/aktuellen Slots
        let reqLabel = vt?.tray_type || vt?.tray_id || vt?.tray_name || vt?.type || vt?.id || null;
        let reqColor = normalizeAmsColor(vt?.tray_color || vt?.color);
        if (!reqLabel || String(reqLabel) === '255') {
            const slotToUse = trayTarget != null ? trayTarget : trayNow != null ? trayNow : null;
            const amsList = Array.isArray(amsRoot.ams) ? amsRoot.ams : [];
            if (slotToUse !== null && amsList.length > 0 && Array.isArray(amsList[0].tray)) {
                const found = amsList[0].tray.find(t => String(t.id ?? t.tray_id) === String(slotToUse));
                if (found) {
                    const mat = found.tray_type || found.material || found.type || '';
                    reqLabel = `Slot ${slotToUse}${mat ? ' - ' + mat : ''}`;
                    reqColor = normalizeAmsColor(found.tray_color || found.color);
                } else {
                    reqLabel = `Slot ${slotToUse}`;
                }
            }
        }
        console.debug('merged requirement', { reqLabel, reqColor, trayTarget, trayNow, vt });

        const mergedJob = {
            ...(message.job || {}),
            gcode_state: (message.job && message.job.gcode_state) || printRoot.gcode_state || printRoot.state,
            progress_percent: (message.job && message.job.progress_percent) ?? (printRoot.percent ?? null),
            remain_time_s: (message.job && message.job.remain_time_s) ?? (printRoot.remain_time ?? null),
            gcode_file: (message.job && message.job.gcode_file) || printRoot.gcode_file || printRoot.file || null,
            task_id: (message.job && message.job.task_id) || message.job?.job_id || printRoot.task_id || printRoot.job_id || null,
            job_id: (message.job && message.job.job_id) || printRoot.job_id || null,
            mc_print_stage: (message.job && (message.job.mc_print_stage ?? message.job.mc_stage)) ?? (printRoot.mc_print_stage ?? printRoot.mc_stage ?? null),
            tray_target: trayTarget ?? (message.job ? message.job.tray_target ?? null : null),
            tray_current: trayNow ?? (message.job ? message.job.tray_current ?? null : null),
            virtual_tray: (message.job && message.job.virtual_tray) || (vt ? {
                id: toSafeInt(vt.id),
                type: vt.tray_type || vt.tray_id_name || vt.tray_name || vt.type || null,
                color: vt.tray_color || vt.color || null,
                remain: toSafeInt(vt.remain)
            } : null),
            req_label: reqLabel || null,
            req_color: reqColor || null
        };
        lastJobData = mergedJob;
        lastJobMeta = { topic: message.topic || '', timestamp };
        const entry = lastMessageByTopic.get(message.topic);
        if (entry) entry.job = mergedJob;
        console.debug('Job merged from payload/job', mergedJob);
        renderJobOverview(lastJobData, lastJobMeta);
    } else if (message.job) {
        lastJobData = message.job;
        lastJobMeta = { topic: message.topic || '', timestamp };
        renderJobOverview(lastJobData, lastJobMeta);
    }
    if (message.topic) {
        const entry = lastMessageByTopic.get(message.topic);
        if (entry && message.job) {
            entry.job = message.job;
        }
    }
    if (message.job) {
        lastJobData = message.job;
        lastJobMeta = { topic: message.topic || '', timestamp };
        renderJobOverview(lastJobData, lastJobMeta);
    }

    // Render summary blocks (printer/raw)
    renderMessage(message);
    
    // Update Health & Aggregation
    updateMqttHealth(message, parsedObj);
}

function renderAmsOverview(amsList, meta = { topic: '', timestamp: '' }) {
    const container = document.getElementById('mqttAmsContainer');
    const metaEl = document.getElementById('mqttAmsMeta');
    if (!container) return;
    container.innerHTML = '';
    if (!Array.isArray(amsList) || amsList.length === 0) {
        container.innerHTML = '<p style="color: var(--text-dim); text-align:center; padding: 10px;">Keine AMS-Daten empfangen.</p>';
        return;
    }
    if (metaEl) {
        metaEl.textContent = `${meta.topic || ''} @ ${meta.timestamp || ''}`;
    }
    amsList.forEach(ams => {
        const card = document.createElement('div');
        card.className = 'card';
        card.style.padding = '10px';
        const active = ams.active_tray ?? '-';
        card.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <strong>AMS ${ams.ams_id ?? 0}</strong>
                <span class="badge" style="background: var(--success); color: #0b0f1a;">Aktiv: ${active}</span>
            </div>
            <div class="ams-trays" style="display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:8px;"></div>
        `;
        const wrap = card.querySelector('.ams-trays');
        const trays = Array.isArray(ams.trays) ? ams.trays : [];
        trays.forEach(tray => {
            const isActive = active !== '-' && String(tray.tray_id ?? tray.id) === String(active);
            const el = document.createElement('div');
            el.className = 'card';
            el.style.padding = '8px';
            el.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span class="color-dot" style="width:14px; height:14px; border-radius:50%; border:1px solid #111827; background:${normalizeAmsColor(tray.color || tray.tray_color)};"></span>
                        <span>Slot ${tray.tray_id ?? tray.id ?? '-'}</span>
                    </div>
                    <span class="badge" style="background:${isActive ? '#22c55e' : '#1f2937'}; color:${isActive ? '#0b0f1a' : '#e5e7eb'};">
                        ${isActive ? 'Aktiv' : 'Bereit'}
                    </span>
                </div>
                <div style="color:var(--text-dim); font-size:0.9rem; margin:4px 0;">${tray.name || tray.tray_id_name || tray.tray_name || ''}</div>
                <div style="font-size:0.9rem;">${tray.material || tray.type || tray.tray_type || ''} ${tray.tray_sub_brands ? '- ' + tray.tray_sub_brands : ''}</div>
                <div style="color:var(--text-dim); font-size:0.85rem;">Fuellstand: ${tray.remain != null ? tray.remain + '%' : 'k.A.'}</div>
            `;
            wrap.appendChild(el);
        });
        container.appendChild(card);
    });
}

function normalizeAmsColor(hex) {
    if (!hex || typeof hex !== 'string') return '#111827';
    const cleaned = hex.startsWith('#') ? hex.slice(1) : hex;
    if (cleaned.length >= 6) return '#' + cleaned.slice(0, 6);
    return '#111827';
}

function toSafeInt(value) {
    const n = parseInt(value, 10);
    return Number.isFinite(n) ? n : null;
}

function renderJobOverview(jobData, meta = { topic: '', timestamp: '' }) {
    const container = document.getElementById('mqttJobContainer');
    const metaEl = document.getElementById('mqttJobMeta');
    if (!container) return;
    container.innerHTML = '';
    if (!jobData || typeof jobData !== 'object') {
        container.innerHTML = '<p style="color: var(--text-dim); text-align:center; padding: 10px;">Keine Job-Daten empfangen.</p>';
        if (metaEl) metaEl.textContent = '';
        return;
    }
    if (metaEl) {
        metaEl.textContent = `${meta.topic || ''} @ ${meta.timestamp || ''}`;
    }
    const card = document.createElement('div');
    card.className = 'card';
    card.style.padding = '10px';
    const prog = jobData.progress_percent != null ? `${jobData.progress_percent}%` : 'k.A.';
    const remain = jobData.remain_time_s != null ? formatSeconds(jobData.remain_time_s) : 'k.A.';
    let targetSlot = jobData.tray_target !== undefined && jobData.tray_target !== null ? String(jobData.tray_target) : '-';
    let currentSlot = jobData.tray_current !== undefined && jobData.tray_current !== null ? String(jobData.tray_current) : '-';
    const vt = jobData.virtual_tray || {};
    let reqLabel = jobData.req_label || vt.type || vt.id || null;
    let reqColor = jobData.req_color || normalizeAmsColor(vt.color);
    // Fallback: Wenn keine echte Anforderung vorhanden, nutze den Ziel-/aktuellen Slot und dessen Material/Farbe
    if (!reqLabel || String(reqLabel) === '255') {
        const slotToUse = targetSlot !== '-' ? targetSlot : currentSlot !== '-' ? currentSlot : null;
        if (slotToUse !== null && Array.isArray(lastAmsData) && lastAmsData.length > 0) {
            const trays = Array.isArray(lastAmsData[0].trays) ? lastAmsData[0].trays : [];
            const found = trays.find(t => String(t.tray_id ?? t.id) === String(slotToUse));
            if (found) {
                const mat = found.tray_type || found.material || found.type || '';
                reqLabel = `Slot ${slotToUse}${mat ? ' - ' + mat : ''}`;
                reqColor = normalizeAmsColor(found.tray_color || found.color);
            }
        }
    }
    if (reqLabel === null || reqLabel === undefined) {
        reqLabel = 'k.A.';
    }
    reqColor = reqColor || '#111827';
    // Letzter Fallback: falls Anforderung noch k.A., hole Slot-Material aus letzter Nachricht
    if ((!reqLabel || reqLabel === 'k.A.') && meta.topic && lastMessageByTopic.has(meta.topic)) {
        try {
            const entry = lastMessageByTopic.get(meta.topic);
            const json = entry?.json || null;
            const pr = json?.print || json || {};
            const amsRoot = pr.ams || {};
            const slotToUse = targetSlot !== '-' ? targetSlot : currentSlot !== '-' ? currentSlot : toSafeInt(amsRoot.tray_tar) ?? toSafeInt(amsRoot.tray_now);
            const amsList = Array.isArray(amsRoot.ams) ? amsRoot.ams : [];
            if (slotToUse !== null && slotToUse !== '-' && amsList.length > 0 && Array.isArray(amsList[0].tray)) {
                const found = amsList[0].tray.find(t => String(t.id ?? t.tray_id) === String(slotToUse));
                if (found) {
                    const mat = found.tray_type || found.material || found.type || '';
                    reqLabel = `Slot ${slotToUse}${mat ? ' - ' + mat : ''}`;
                    reqColor = normalizeAmsColor(found.tray_color || found.color);
                } else {
                    reqLabel = `Slot ${slotToUse}`;
                }
            } else if (slotToUse !== null && slotToUse !== '-') {
                reqLabel = `Slot ${slotToUse}`;
            }
        } catch (e) {
            console.debug('fallback requirement parse failed', e);
        }
    }
    console.debug('render requirement', { reqLabel, reqColor });
    // Fallback: Wenn Slots fehlen, versuche aus letzter Nachricht zu lesen
    if ((targetSlot === '-' || currentSlot === '-') && meta.topic && lastMessageByTopic.has(meta.topic)) {
        try {
            const entry = lastMessageByTopic.get(meta.topic);
            const json = entry?.json || null;
            const pr = json?.print || json || {};
            const amsRoot = pr.ams || {};
            const tTar = toSafeInt(amsRoot.tray_tar);
            const tNow = toSafeInt(amsRoot.tray_now);
            if (targetSlot === '-' && tTar !== null && tTar !== undefined) targetSlot = String(tTar);
            if (currentSlot === '-' && tNow !== null && tNow !== undefined) currentSlot = String(tNow);
        } catch (e) {
            console.debug('fallback slot parse failed', e);
        }
    }
    console.debug('renderJobOverview slots', { targetSlot, currentSlot, tray_target: jobData.tray_target, tray_current: jobData.tray_current });
    card.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
            <strong>${jobData.gcode_file || 'Kein Job'}</strong>
            <span class="badge">${jobData.gcode_state || jobData.state || '-'}</span>
        </div>
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:8px; font-size:0.9rem;">
            <div><span style="color:var(--text-dim);">Fortschritt:</span> ${prog}</div>
            <div><span style="color:var(--text-dim);">Restzeit:</span> ${remain}</div>
            <div><span style="color:var(--text-dim);">Stage:</span> ${jobData.mc_print_stage ?? jobData.mc_stage ?? '-'}</div>
            <div><span style="color:var(--text-dim);">Task/Job:</span> ${jobData.task_id || jobData.job_id || '-'}</div>
            <div><span style="color:var(--text-dim);">Ziel-Slot:</span> ${targetSlot}</div>
            <div><span style="color:var(--text-dim);">Aktueller Slot:</span> ${currentSlot}</div>
            <div style="display:flex; align-items:center; gap:6px;"><span style="color:var(--text-dim);">Anforderung:</span> <span class="color-dot" style="width:14px;height:14px;border-radius:50%;border:1px solid #111827;background:${reqColor};"></span> <span>${reqLabel}</span></div>
        </div>
    `;
    container.appendChild(card);
}

function formatSeconds(sec) {
    const n = parseInt(sec, 10);
    if (!Number.isFinite(n) || n < 0) return 'k.A.';
    const h = Math.floor(n / 3600);
    const m = Math.floor((n % 3600) / 60);
    const s = n % 60;
    if (h > 0) return `${h}h ${m.toString().padStart(2, '0')}m`;
    return `${m}m ${s.toString().padStart(2, '0')}s`;
}

// =============== HEALTH & AGGREGATION ===============
function updateMqttHealth(message, parsedObj) {
    // Uptime
    if (!mqttStartTime) mqttStartTime = Date.now();
    const uptimeSec = Math.floor((Date.now() - mqttStartTime) / 1000);
    const uptimeEl = document.getElementById('mqttUptime');
    if (uptimeEl) {
        if (uptimeSec < 60) uptimeEl.textContent = uptimeSec + 's';
        else if (uptimeSec < 3600) uptimeEl.textContent = Math.floor(uptimeSec/60) + 'm';
        else uptimeEl.textContent = Math.floor(uptimeSec/3600) + 'h';
    }
    
    // Message Rate (Rolling Window)
    const now = Date.now();
    mqttMessageRateQueue.push(now);
    mqttMessageRateQueue = mqttMessageRateQueue.filter(t => now - t < RATE_WINDOW * 1000);
    const rate = mqttMessageRateQueue.length / RATE_WINDOW;
    const rateEl = document.getElementById('mqttMsgRate');
    if (rateEl) rateEl.textContent = rate.toFixed(1);
    
    // Active Topics
    const activeTopicsEl = document.getElementById('mqttActiveTopics');
    if (activeTopicsEl) activeTopicsEl.textContent = lastMessageByTopic.size;
    
    // Avg Payload Size
    const payloadSize = String(message.payload || '').length;
    mqttPayloadSizes.push(payloadSize);
    if (mqttPayloadSizes.length > 100) mqttPayloadSizes.shift();
    const avgSize = mqttPayloadSizes.reduce((a,b)=>a+b,0) / mqttPayloadSizes.length;
    const avgEl = document.getElementById('mqttAvgPayload');
    if (avgEl) {
        if (avgSize < 1024) avgEl.textContent = Math.round(avgSize) + ' B';
        else avgEl.textContent = (avgSize/1024).toFixed(1) + ' KB';
    }
    
    // Extract Live Values
    if (parsedObj && typeof parsedObj === 'object') {
        extractLiveValues(parsedObj);
    }
}

function extractLiveValues(obj) {
    // Rekursive Suche nach bekannten Keys
    function findKey(o, key) {
        if (!o || typeof o !== 'object') return null;
        if (key in o) return o[key];
        for (const k of Object.keys(o)) {
            const res = findKey(o[k], key);
            if (res !== null) return res;
        }
        return null;
    }
    
    const nozzle = findKey(obj, 'nozzle_temper') || findKey(obj, 'nozzle_temp');
    const bed = findKey(obj, 'bed_temper') || findKey(obj, 'bed_temp');
    const progress = findKey(obj, 'mc_percent') || findKey(obj, 'percent') || findKey(obj, 'progress');
    const layer = findKey(obj, 'layer_num');
    const totalLayer = findKey(obj, 'total_layer_num');
    const speed = findKey(obj, 'spd_mag') || findKey(obj, 'print_speed');
    const status = findKey(obj, 'gcode_state') || findKey(obj, 'print_state') || findKey(obj, 'state');
    
    const nozzleEl = document.getElementById('valNozzleTemp');
    const bedEl = document.getElementById('valBedTemp');
    const progressEl = document.getElementById('valProgress');
    const layerEl = document.getElementById('valLayer');
    const speedEl = document.getElementById('valSpeed');
    const statusEl = document.getElementById('valStatus');
    
    if (nozzleEl && nozzle !== null) nozzleEl.textContent = nozzle + 'ï¿½C';
    if (bedEl && bed !== null) bedEl.textContent = bed + 'ï¿½C';
    if (progressEl && progress !== null) progressEl.textContent = progress + '%';
    if (layerEl && layer !== null && totalLayer !== null) layerEl.textContent = layer + '/' + totalLayer;
    else if (layerEl && layer !== null) layerEl.textContent = layer;
    if (speedEl && speed !== null) speedEl.textContent = speed + ' mm/s';
    if (statusEl && status !== null) statusEl.textContent = String(status);
}

// =============== JSON INSPECTOR ===============
function showInspectorForTopic(topic) {
    const tree = document.getElementById('mqttJsonTree');
    const tEl = document.getElementById('mqttJsonTopic');
    const timeEl = document.getElementById('mqttJsonTime');
    if (!tree) return;
    const entry = lastMessageByTopic.get(topic);
    tEl && (tEl.textContent = topic || '-');
    if (!entry) {
        timeEl && (timeEl.textContent = '-');
        tree.innerHTML = `<p style="color: var(--text-dim); text-align:center; padding:8px;">Keine Daten fï¿½r dieses Topic vorhanden.</p>`;
        return;
    }
    timeEl && (timeEl.textContent = entry.timestamp || '-');
    if (entry.ams && Array.isArray(entry.ams) && entry.ams.length > 0) {
        lastAmsData = entry.ams;
        lastAmsMeta = { topic, timestamp: entry.timestamp || '' };
        renderAmsOverview(lastAmsData, lastAmsMeta);
    }
    if (entry.job) {
        lastJobData = entry.job;
        lastJobMeta = { topic, timestamp: entry.timestamp || '' };
        renderJobOverview(lastJobData, lastJobMeta);
    }
    tree.innerHTML = '';
    if (entry.json && typeof entry.json === 'object') {
        renderJsonTree(entry.json, tree);
        // Buttons
        const copyBtn = document.getElementById('jsonCopyAll');
        copyBtn && copyBtn.addEventListener('click', () => copyToClipboard(JSON.stringify(entry.json, null, 2)));
        const expAll = document.getElementById('jsonExpandAll');
        const colAll = document.getElementById('jsonCollapseAll');
        expAll && expAll.addEventListener('click', () => setAllCollapsed(tree, false));
        colAll && colAll.addEventListener('click', () => setAllCollapsed(tree, true));
    } else {
        const pre = document.createElement('pre');
        pre.textContent = entry.raw;
        pre.style.margin = 0;
        tree.appendChild(pre);
        const copyBtn = document.getElementById('jsonCopyAll');
        copyBtn && copyBtn.addEventListener('click', () => copyToClipboard(String(entry.raw || '')));
    }
}

function renderJsonTree(obj, container) {
    const root = buildJsonNode('(root)', obj, true, '');
    container.appendChild(root);
}

function buildJsonNode(key, value, expanded, path) {
    const node = document.createElement('div');
    node.className = 'json-node';
    const row = document.createElement('div');
    row.className = 'json-row';
    const toggle = document.createElement('span');
    toggle.className = 'json-toggle';
    const keyEl = document.createElement('span');
    keyEl.className = 'json-key';
    keyEl.textContent = key;
    const typeEl = document.createElement('span');
    typeEl.className = 'json-type';
    const copyBtn = document.createElement('button');
    copyBtn.className = 'copy-btn';
    const children = document.createElement('div');
    children.className = 'json-children';

    if (value !== null && typeof value === 'object') {
        const isArray = Array.isArray(value);
        typeEl.textContent = isArray ? `[${value.length}]` : '{ }';
        copyBtn.textContent = 'Copy';
        copyBtn.addEventListener('click', () => copyToClipboard(JSON.stringify(value, null, 2)));
        toggle.textContent = expanded ? '-' : '+';
        toggle.addEventListener('click', () => {
            const collapsed = children.style.display === 'none';
            children.style.display = collapsed ? 'block' : 'none';
            toggle.textContent = collapsed ? '-' : '+';
        });
        row.appendChild(toggle);
        row.appendChild(keyEl);
        row.appendChild(typeEl);
        row.appendChild(copyBtn);
        node.appendChild(row);
        node.appendChild(children);
        // Kinder
        for (const k of Object.keys(value)) {
            const childPath = path ? `${path}.${k}` : k;
            children.appendChild(buildJsonNode(k, value[k], false, childPath));
        }
        children.style.display = expanded ? 'block' : 'none';
    } else {
        // Primitive
        toggle.textContent = '';
        const val = document.createElement('span');
        val.className = 'json-value';
        val.textContent = String(value);
        copyBtn.textContent = 'Copy';
        copyBtn.addEventListener('click', () => copyToClipboard(String(value)));
        row.appendChild(toggle);
        row.appendChild(keyEl);
        row.appendChild(document.createTextNode(':'));
        row.appendChild(val);
        row.appendChild(copyBtn);
        node.appendChild(row);
    }
    return node;
}

function setAllCollapsed(container, collapsed) {
    container.querySelectorAll('.json-children').forEach(ch => {
        ch.style.display = collapsed ? 'none' : 'block';
    });
    container.querySelectorAll('.json-toggle').forEach(tg => {
        if (tg.textContent.trim()) tg.textContent = collapsed ? '?' : '?';
    });
}

async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        if (typeof showNotification === 'function') showNotification('In Zwischenablage kopiert', 'success');
    } catch (e) {
        console.warn('Clipboard nicht verfï¿½gbar');
    }
}

// === PERFORMANCE MONITORING (LITE) ===
function setupPerformanceListeners() {
    document.addEventListener('visibilitychange', handlePerformanceVisibilityChange);
    window.addEventListener('pagehide', stopPerformanceMonitoring);
    window.addEventListener('beforeunload', stopPerformanceMonitoring);
}

function handlePerformanceVisibilityChange() {
    if (document.visibilityState === 'visible' && isPerformancePanelActive()) {
        startPerformanceMonitoring();
    } else {
        stopPerformanceMonitoring();
    }
}

function isPerformancePanelActive() {
    const perfTab = document.querySelector('.debug-tab[data-tab="performance"]');
    const panel = document.getElementById('panel-performance');
    const tabActive = !!(perfTab && perfTab.classList.contains('active'));
    const panelVisible = !!(panel && panel.style.display !== 'none');
    return tabActive && panelVisible && document.visibilityState === 'visible';
}

function startPerformanceMonitoring() {
    if (!isPerformancePanelActive()) return;
    stopPerformanceMonitoring();
    loadPerformanceLiteOnce();
    performanceInterval = setInterval(() => {
        if (!isPerformancePanelActive()) {
            stopPerformanceMonitoring();
            return;
        }
        loadPerformanceLiteOnce();
    }, PERFORMANCE_LITE_INTERVAL_MS);
}

function stopPerformanceMonitoring() {
    if (performanceInterval) {
        clearInterval(performanceInterval);
        performanceInterval = null;
    }
}

async function loadPerformanceLiteOnce() {
    const panel = document.getElementById('panel-performance');
    if (isNullElement(panel)) return;

    let payload = null;
    try {
        const response = await fetch('/api/performance/panel', { cache: 'no-store' });
        if (!response.ok) {
            setPerformanceLiteIdle();
            return;
        }
        payload = await response.json();
    } catch {
        setPerformanceLiteIdle();
        return;
    }

    updatePerformanceLite(payload || {});
}

// Legacy name for compatibility with existing calls
async function loadPerformanceData() {
    return loadPerformanceLiteOnce();
}

function updatePerformanceLite(data) {
    const current = data?.current || {};
    const alerts = Array.isArray(data?.alerts) ? data.alerts : [];

    const cpuPercent = firstMeaningful([safeGet(current, 'cpu.percent', null), safeGet(current, 'cpu_percent', null)]);
    const ramPercent = firstMeaningful([safeGet(current, 'ram.percent', null), safeGet(current, 'ram_percent', null)]);
    const diskPercent = firstMeaningful([safeGet(current, 'disk.percent', null), safeGet(current, 'disk_percent', null)]);

    const cpu = { ...(current.cpu || {}), percent: cpuPercent };
    const ram = {
        ...(current.ram || {}),
        percent: ramPercent,
        used_mb: firstMeaningful([safeGet(current, 'ram.used_mb', null), safeGet(current, 'ram_used_mb', null)]),
        total_mb: firstMeaningful([safeGet(current, 'ram.total_mb', null), safeGet(current, 'ram_total_mb', null)])
    };
    const disk = {
        ...(current.disk || {}),
        percent: diskPercent,
        used_gb: firstMeaningful([safeGet(current, 'disk.used_gb', null), safeGet(current, 'disk_used_gb', null)]),
        total_gb: firstMeaningful([safeGet(current, 'disk.total_gb', null), safeGet(current, 'disk_total_gb', null)])
    };

    setPerfLiteCard('perf-lite-card-cpu', 'perf-lite-cpu-value', 'perf-lite-cpu-meta', cpu.percent, buildCpuMeta(cpu), 'cpu');
    setPerfLiteCard('perf-lite-card-ram', 'perf-lite-ram-value', 'perf-lite-ram-meta', ram.percent, buildUsageMeta(ram), 'ram');
    setPerfLiteCard('perf-lite-card-disk', 'perf-lite-disk-value', 'perf-lite-disk-meta', disk.percent, buildUsageMeta(disk), 'disk');

    const uptimeInfo = resolveUptime(current);
    setPerfLiteCard(
        'perf-lite-card-uptime',
        'perf-lite-uptime-value',
        'perf-lite-uptime-meta',
        uptimeInfo.value,
        uptimeInfo.detail,
        'uptime',
        { status: uptimeInfo.status, formatValue: (v) => (meaningful(v) ? v : '–') }
    );

    renderPerformanceLiteAlerts(alerts);
}

function setPerformanceLiteIdle() {
    setPerfLiteCard('perf-lite-card-cpu', 'perf-lite-cpu-value', 'perf-lite-cpu-meta', null, '–', 'cpu', { status: 'idle' });
    setPerfLiteCard('perf-lite-card-ram', 'perf-lite-ram-value', 'perf-lite-ram-meta', null, '–', 'ram', { status: 'idle' });
    setPerfLiteCard('perf-lite-card-disk', 'perf-lite-disk-value', 'perf-lite-disk-meta', null, '–', 'disk', { status: 'idle' });
    setPerfLiteCard('perf-lite-card-uptime', 'perf-lite-uptime-value', 'perf-lite-uptime-meta', null, '–', 'uptime', { status: 'idle', formatValue: () => '–' });
    renderPerformanceLiteAlerts([]);
}

function setPerfLiteCard(cardId, valueId, metaId, rawValue, detail, metricType, options = {}) {
    const card = document.getElementById(cardId);
    const valueEl = document.getElementById(valueId);
    const metaEl = metaId ? document.getElementById(metaId) : null;

    const formatter = options.formatValue || formatPercent;
    if (valueEl) valueEl.textContent = formatter(rawValue);
    if (metaEl) metaEl.textContent = meaningful(detail) ? detail : '–';

    if (card) {
        const status = options.status || getPerformanceStatus(rawValue, metricType);
        card.classList.remove('status-ok', 'status-warn', 'status-error', 'status-idle');
        card.classList.add(`status-${status}`);
    }
}

function renderPerformanceLiteAlerts(alerts) {
    const container = document.getElementById('perf-lite-alerts');
    if (!container) return;
    container.innerHTML = '';

    const list = Array.isArray(alerts) ? alerts : [];
    if (!list.length) {
        container.style.display = 'none';
        return;
    }

    container.style.display = '';
    list.forEach(alert => {
        const level = String(alert?.level || alert?.status || 'info').toLowerCase();
        const status = level === 'error' ? 'error' : (level === 'warn' || level === 'warning') ? 'warn' : 'idle';
        const label = meaningful(alert?.title) ? alert.title : (alert?.level || 'Info');
        const message = meaningful(alert?.message) ? alert.message : (alert?.text || '');
        const alertEl = document.createElement('div');
        alertEl.className = `perf-lite-alert status-${status}`;
        alertEl.textContent = [label, message].filter(Boolean).join(': ');
        container.appendChild(alertEl);
    });
}

function getPerformanceStatus(value, metricType) {
    const num = toNumber(value);
    if (!Number.isFinite(num)) return 'idle';
    const thresholds = PERFORMANCE_THRESHOLDS[metricType] || PERFORMANCE_THRESHOLDS.cpu;
    if (num > thresholds.error) return 'error';
    if (num >= thresholds.warn) return 'warn';
    return 'ok';
}

function formatPercent(value) {
    const num = toNumber(value);
    if (!Number.isFinite(num)) return '–';
    const fixed = Math.abs(num % 1) < 0.05 ? num.toFixed(0) : num.toFixed(1);
    return `${fixed}%`;
}

function toNumber(value) {
    const num = Number(value);
    return Number.isFinite(num) ? num : null;
}

function meaningful(value) {
    return value !== null && value !== undefined && value !== '' && value !== 'n/a';
}

function firstMeaningful(values) {
    for (const val of values) {
        if (meaningful(val)) return val;
    }
    return null;
}

function buildCpuMeta(cpu) {
    if (!cpu || typeof cpu !== 'object') return '–';
    const cores = firstMeaningful([safeGet(cpu, 'cores', null), safeGet(cpu, 'core_count', null)]);
    if (cores !== null) return `${cores} cores`;
    const loadLabel = firstMeaningful([
        safeGet(cpu, 'load', null),
        safeGet(cpu, 'detail', null),
        safeGet(cpu, 'label', null)
    ]);
    if (loadLabel) return loadLabel;
    return '–';
}

function buildUsageMeta(section) {
    if (!section || typeof section !== 'object') return '–';
    const usedTotal = formatUsedTotal(section);
    if (usedTotal) return usedTotal;
    const label = firstMeaningful([
        safeGet(section, 'detail', null),
        safeGet(section, 'label', null),
        safeGet(section, 'text', null)
    ]);
    return label || '–';
}

function formatUsedTotal(section) {
    const used = firstMeaningful([safeGet(section, 'used_human', null), safeGet(section, 'used', null)]);
    const total = firstMeaningful([safeGet(section, 'total_human', null), safeGet(section, 'total', null)]);
    if (used && total) return `${used} / ${total}`;
    const usedGb = toNumber(safeGet(section, 'used_gb', null));
    const totalGb = toNumber(safeGet(section, 'total_gb', null));
    if (Number.isFinite(usedGb) && Number.isFinite(totalGb)) return `${usedGb} GB / ${totalGb} GB`;
    const usedMb = toNumber(safeGet(section, 'used_mb', null));
    const totalMb = toNumber(safeGet(section, 'total_mb', null));
    if (Number.isFinite(usedMb) && Number.isFinite(totalMb)) return `${usedMb} MB / ${totalMb} MB`;
    return null;
}

function resolveUptime(current) {
    const uptimeValue = firstMeaningful([
        safeGet(current, 'uptime', null),
        safeGet(current, 'backend_uptime', null),
        safeGet(current, 'app_uptime', null),
        safeGet(current, 'runtime.uptime', null),
        safeGet(lastSystemStatus, 'app.uptime', null)
    ]);
    const detail = firstMeaningful([
        safeGet(current, 'uptime_detail', null),
        safeGet(current, 'backend_uptime_detail', null)
    ]);
    if (!meaningful(uptimeValue)) {
        return { value: '–', detail: '–', status: 'idle' };
    }
    return { value: uptimeValue, detail: meaningful(detail) ? detail : '–', status: 'ok' };
}
// === ADD PRINTER MODAL ===
function openAddPrinterModal() {
    const modal = document.getElementById('addPrinterModal');
    // Reset fields
    document.getElementById('manualIp').value = '';
    document.getElementById('manualPort').value = '6000';
    document.getElementById('manualType').value = 'bambu';
    document.getElementById('manualHostname').value = '';
    modal.style.display = 'flex';
}

function closeAddPrinterModal() {
    const modal = document.getElementById('addPrinterModal');
    modal.style.display = 'none';
}

function addManualPrinter() {
    const ip = document.getElementById('manualIp').value.trim();
    const port = parseInt(document.getElementById('manualPort').value);
    const type = document.getElementById('manualType').value;
    const hostname = document.getElementById('manualHostname').value.trim();
    
    if (!ip) {
        showNotification('Bitte IP-Adresse eingeben', 'warning');
        return;
    }
    
    if (!port || port < 1 || port > 65535) {
        showNotification('Bitte gï¿½ltigen Port eingeben (1-65535)', 'warning');
        return;
    }
    
    // Drucker zur Liste hinzufï¿½gen
    const resultsDiv = document.getElementById('foundPrinters');
    const existingMessage = resultsDiv.querySelector('p');
    if (existingMessage) {
        resultsDiv.innerHTML = '';
    }
    
    const printer = {
        ip: ip,
        port: port,
        type: type,
        hostname: hostname || null,
        accessible: true
    };
    
    // Prï¿½fe ob Drucker bereits existiert
    const cards = resultsDiv.querySelectorAll('.printer-card');
    for (let card of cards) {
        const existingIp = card.querySelector('strong').textContent;
        if (existingIp === ip) {
            showNotification('Drucker mit dieser IP existiert bereits', 'warning');
            closeAddPrinterModal();
            return;
        }
    }
    
    // Erstelle Karte
    const card = document.createElement('div');
    card.className = 'printer-card';
    card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: start;">
            <div>
                <strong>${printer.ip}</strong>:${printer.port}
                ${printer.hostname ? `<br><small style="color: var(--text-dim);">${printer.hostname}</small>` : ''}
                <br><span class="badge">${printer.type}</span>
                <span class="badge" style="background: var(--success); margin-left: 5px;">Manuell hinzugefï¿½gt</span>
            </div>
            <div style="display: flex; gap: 5px;">
                <button class="btn btn-sm btn-primary" onclick="testSinglePrinter('${printer.ip}', ${printer.port})">
                    Test
                </button>
                <button class="btn btn-sm btn-danger" onclick="this.closest('.printer-card').remove(); checkPrinterList()">
                    ?
                </button>
            </div>
        </div>
    `;
    
    resultsDiv.appendChild(card);
    
    closeAddPrinterModal();
    showNotification(`Drucker ${ip}:${port} hinzugefï¿½gt. Bitte teste die Verbindung!`, 'success');
    
    // Stelle sicher, dass Config-Button disabled bleibt
    checkConfigButton();
}

function checkPrinterList() {
    const resultsDiv = document.getElementById('foundPrinters');
    const cards = resultsDiv.querySelectorAll('.printer-card');
    
    if (cards.length === 0) {
        resultsDiv.innerHTML = '<p style="color: var(--text-dim); text-align: center; padding: 20px;">Noch keine Drucker gefunden. Starte einen Scan!</p>';
    }
    
    checkConfigButton();
}

function checkConfigButton() {
    const configBtn = document.getElementById('generateConfig');
    if (!configBtn) return; // Button existiert nicht, Fehler vermeiden
    const cards = document.querySelectorAll('.printer-card[data-tested="true"]');
    if (cards.length > 0) {
        configBtn.disabled = false;
        configBtn.style.opacity = '1';
        configBtn.style.cursor = 'pointer';
    } else {
        configBtn.disabled = true;
        configBtn.style.opacity = '0.5';
        configBtn.style.cursor = 'not-allowed';
    }
}

// Close modals on outside click
window.addEventListener('click', (e) => {
    const testModal = document.getElementById('testResultModal');
    const addModal = document.getElementById('addPrinterModal');
    
    if (e.target === testModal) {
        closeTestResultModal();
    }
    if (e.target === addModal) {
        closeAddPrinterModal();
    }
});

// === CLEANUP ===
window.addEventListener('beforeunload', () => {
    if (updateInterval) {
        clearInterval(updateInterval);
    }
    if (performanceInterval) {
        clearInterval(performanceInterval);
    }
    
    if (mqttWebSocket) {
        mqttWebSocket.close();
    }
});

// Modernes Cleanup beim Seitenwechsel/Tab-Wechsel/Reload
window.addEventListener('pagehide', () => {
    if (!mqttConnected) return;

    const brokerElem = document.getElementById('mqttBroker');
    const portElem = document.getElementById('mqttPort');

    // sendBeacon funktioniert zuverlÃ¤ssig beim pagehide-Event
    if (brokerElem && portElem) {
        const broker = brokerElem.value;
        const port = parseInt(portElem.value);
        navigator.sendBeacon(
            `/api/mqtt/disconnect?broker=${encodeURIComponent(broker)}&port=${port}`
        );
    }

    // WebSocket sauber schlieÃŸen
    if (mqttWebSocket) {
        try { mqttWebSocket.close(); } catch {}
    }
});

// Fallback fÃ¼r Browser, die pagehide nicht unterstÃ¼tzen
document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "hidden") return;
    if (!mqttConnected) return;

    const brokerElem = document.getElementById('mqttBroker');
    const portElem = document.getElementById('mqttPort');

    if (brokerElem && portElem) {
        const broker = brokerElem.value;
        const port = parseInt(portElem.value);
        navigator.sendBeacon(
            `/api/mqtt/disconnect?broker=${encodeURIComponent(broker)}&port=${port}`
        );
    }

    if (mqttWebSocket) {
        try { mqttWebSocket.close(); } catch {}
    }
});

























// === DEBUG CENTER MODE (Lite/Pro) ===

async function initDebugCenterMode() {
    const radios = document.querySelectorAll("input[name='debugMode']");
    const systemPanel = document.getElementById('systemPanel');
    const systemPanelPro = document.getElementById('systemPanelPro');
    if (!radios.length || isNullElement(systemPanel) || isNullElement(systemPanelPro)) return;
    let mode = 'lite';
    try {
        const res = await fetch('/api/settings');
        const settings = await res.json();
        mode = (settings?.debug_center_mode || 'lite').toLowerCase();
    } catch (err) {
        console.debug('debug_center_mode laden fehlgeschlagen, fallback lite');
    }
    debugCenterMode = mode === 'pro' ? 'pro' : 'lite';
    applyDebugCenterMode(debugCenterMode);

    const onChange = async (newMode) => {
        const normalized = newMode === 'pro' ? 'pro' : 'lite';
        debugCenterMode = normalized;
        applyDebugCenterMode(normalized);
        fetch('/api/settings', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ debug_center_mode: normalized }),
        }).catch(() => {
            console.debug('debug_center_mode speichern fehlgeschlagen');
        });
    };
    radios.forEach(r => {
        r.checked = r.value === debugCenterMode;
        r.addEventListener('change', (e) => onChange(e.target.value === 'pro' ? 'pro' : 'lite'));
    });
}

function applyDebugCenterMode(mode) {
    const normalized = mode === 'pro' ? 'pro' : 'lite';
    const systemPanel = document.getElementById('systemPanel');
    const systemPanelPro = document.getElementById('systemPanelPro');
    if (!isNullElement(systemPanel) && !isNullElement(systemPanelPro)) {
        if (normalized === 'pro') {
            systemPanel.classList.add('hidden');
            systemPanelPro.classList.remove('hidden');
        } else {
            systemPanel.classList.remove('hidden');
            systemPanelPro.classList.add('hidden');
        }
    }
    const proItems = document.querySelectorAll('.pro-only');
    proItems.forEach(el => {
        el.style.display = (normalized === 'pro') ? '' : 'none';
    });

    const tabs = document.querySelectorAll('.debug-tab');
    tabs.forEach(tab => {
        const tabMode = (tab.dataset.mode || 'lite').toLowerCase();
        const allowed = tabMode === 'lite' || normalized === 'pro';
        tab.style.display = allowed ? '' : 'none';
    });

    const activeTab = document.querySelector('.debug-tab.active');
    const activeAllowed = activeTab ? (activeTab.style.display !== 'none') : false;
    if (!activeAllowed) {
        const systemTab = document.querySelector('.debug-tab[data-tab="system"]');
        if (systemTab) systemTab.click();
    }
}

// === SYSTEM STATUS (neue IDs) ===
async function loadSystemStatus() {
    try {
        const response = await fetch('/api/system/status');
        const data = await response.json();
        lastSystemStatus = data || {};
        renderSystemStatus(data || {});
    } catch (error) {
        console.error('Fehler beim Laden des System-Status:', error);
    }
}

function setText(id, value, fallback = 'n/a') {
    const el = document.getElementById(id);
    if (el) el.textContent = value ?? fallback;
}

function setStatusBadge(id, status) {
    const el = document.getElementById(id);
    if (!el) return;
    const normalized = String(status || 'offline').toLowerCase();
    el.classList.remove('status-ok', 'status-warn', 'status-error');
    let cls = 'status-ok';
    if (['warn', 'warning'].includes(normalized)) cls = 'status-warn';
    if (['error', 'offline', 'down', 'failed'].includes(normalized)) cls = 'status-error';
    el.classList.add(cls);
    el.textContent = status || 'offline';
}

function setStatus(id, state, fallback = "offline") {
    const el = document.getElementById(id);
    if (!el) return;
    const val = state ?? fallback;
    el.textContent = val;
    el.classList.remove("status-ok", "status-warn", "status-error", "status-idle", "status-info");
    switch (val) {
        case "online":
        case "connected":
        case "reachable":
            el.classList.add("status-ok");
            break;
        case "listening":
            el.classList.add("status-info");
            break;
        case "connecting":
        case "idle":
        case "disabled":
            el.classList.add("status-warn");
            break;
        case "offline":
        case "error":
            el.classList.add("status-error");
            break;
        default:
            el.classList.add("status-idle");
            break;
    }
}

function setTitle(id, value) {
    const el = document.getElementById(id);
    if (el && value) {
        el.title = value;
    }
}

function buildMqttTooltip(mqtt) {
    if (!mqtt) return "";
    const host = mqtt.host || "n/a";
    const port = mqtt.port || "n/a";
    const err = mqtt.last_error || "";
    return `MQTT Host: ${host}:${port}${err ? "\nLast Error: " + err : ""}`;
}

function buildWsTooltip(ws) {
    if (!ws) return "";
    const lastPing = ws.last_ping_s != null ? ws.last_ping_s + " s" : "n/a";
    const lastActivity = ws.last_activity_s != null ? ws.last_activity_s + " s" : "n/a";
    const clients = ws.clients != null ? ws.clients : 0;
    const state = ws.state || "";
    const hint = (() => {
        if (state === "listening") return "Server aktiv, wartet auf Client";
        if (state === "connected") return "Aktiver WebSocket-Client verbunden";
        if (state === "idle") return "Kein aktiver Client";
        if (state === "offline") return "WebSocket nicht erreichbar";
        return "";
    })();
    return `WebSocket Status: ${state || "n/a"}\nLetzte Antwort: ${lastPing}\nLetzte Aktivität: ${lastActivity}\nClients: ${clients}${hint ? "\n" + hint : ""}`;
}

async function loadBackendStatus() {
    try {
        const res = await fetch("/api/debug/system_status");
        if (!res.ok) {
            setStatus("apiStatus", "offline");
            setStatus("dbStatus", "error", "error");
            setStatus("mqttStatus", "offline");
            setStatus("wsStatus", "offline");
            return;
        }
        const data = await res.json();
        const apiState = safeGet(data, "api.state", "offline");
        const dbState = safeGet(data, "db.state", "error");
        const mqttState = safeGet(data, "mqtt.state", "offline");
        const wsState = safeGet(data, "websocket.state", "offline");
        const wsClients = safeGet(data, "websocket.clients", 0);
        const runtimeState = safeGet(data, "runtime.state", "idle");
        const runtimeReq = safeGet(data, "runtime.requests_per_minute", null);
        const runtimeAvg = safeGet(data, "runtime.avg_response_ms", null);

        setStatus("apiStatus", apiState, "offline");
        setStatus("dbStatus", dbState, "error");
        setStatus("mqttStatus", mqttState, "offline");
        setStatus("wsStatus", wsState, "offline");
        setText("wsClients", wsClients ? `(${wsClients} client${wsClients === 1 ? "" : "s"})` : "");

                // Runtime & Requests Anzeige
        const idleMode = runtimeState === "idle";
        const reqNum = Number(runtimeReq);
        const respNum = Number(runtimeAvg);
        const hasReq = Number.isFinite(reqNum) && reqNum > 0;
        const reqText = idleMode || !hasReq ? "?" : reqNum.toString();
        const respText = idleMode || !Number.isFinite(respNum) ? "?" : `${respNum} ms`;
        setText("sys_runtime_rpm", reqText, "–");
        setText("sys_runtime_avg", respText, "–");
        const runtimeBadge = document.getElementById("sys_runtime_state");
        if (runtimeBadge) {
            runtimeBadge.textContent = idleMode ? "Idle" : "Active";
            runtimeBadge.classList.remove("status-ok", "status-warn", "status-error", "status-idle", "status-info");
            runtimeBadge.classList.add(idleMode ? "status-idle" : "status-ok");
        }

        setTitle("mqttStatus", buildMqttTooltip(data.mqtt));
        setTitle("wsStatus", buildWsTooltip(data.websocket));
    } catch (e) {
        console.error("Backend-Status konnte nicht geladen werden:", e);
        setStatus("apiStatus", "offline");
        setStatus("dbStatus", "error", "error");
        setStatus("mqttStatus", "offline");
        setStatus("wsStatus", "offline");
        setText("wsClients", "");
    }
}

function renderSystemStatus(data) {
    const appName = safeGet(data, "app.name", "FilamentHub");
    const appVersion = safeGet(data, "app.version", "n/a");
    const appEnv = safeGet(data, "app.environment", "n/a");
    const appUptime = safeGet(data, "app.uptime", "0");
    setText("sys_app_name", appName, "FilamentHub");
    setText("sys_app_version", appVersion, "n/a");
    setText("sys_app_env", appEnv, "n/a");
    setText("sys_app_uptime", appUptime, "0");

    const cpuPercent = safeGet(data, "system.cpu_percent", 0);
    const cpuCores = safeGet(data, "system.cpu_count", "n/a");
    const ramPercent = safeGet(data, "system.ram_percent", 0);
    const ramUsed = safeGet(data, "system.ram_used_gb", null);
    const ramTotal = safeGet(data, "system.ram_total_gb", null);
    const ramDetail = (ramUsed !== null && ramTotal !== null) ? `${ramUsed} GB / ${ramTotal} GB` : "0 / 0";
    const diskPercent = safeGet(data, "system.disk_percent", 0);
    const diskUsed = safeGet(data, "system.disk_used_gb", null);
    const diskTotal = safeGet(data, "system.disk_total_gb", null);
    const diskDetail = (diskUsed !== null && diskTotal !== null) ? `${diskUsed} GB / ${diskTotal} GB` : "0 / 0";

    setText("sys_cpu_usage", `${cpuPercent} %`, "0 %");
    setText("sys_cpu_cores", cpuCores !== null ? `${cpuCores} Cores` : "n/a", "n/a");
    setText("sys_ram_usage", `${ramPercent} %`, "0 %");
    setText("sys_ram_detail", ramDetail, "0 / 0");
    setText("sys_disk_usage", `${diskPercent} %`, "0 %");
    setText("sys_disk_detail", diskDetail, "0 / 0");

    const bambuActive = Number(safeGet(data, "printers.bambu_active", 0)) || 0;
    const klipperActive = Number(safeGet(data, "printers.klipper_active", 0)) || 0;
    const totalPrinters = Number(safeGet(data, "printers.total", bambuActive + klipperActive)) || 0;
    let onlineCount = Number(safeGet(data, "printers.online", NaN));
    if (Number.isNaN(onlineCount)) {
        onlineCount = 0;
        const bambuStatus = String(safeGet(data, "printers.bambu", "")).toLowerCase();
        const klipperStatus = String(safeGet(data, "printers.klipper", "")).toLowerCase();
        if (bambuStatus === "online") onlineCount += 1;
        if (klipperStatus === "online") onlineCount += 1;
    }
    const amsCount = Number(safeGet(data, "ams.count", safeGet(data, "printers.ams_count", 0))) || 0;
    const amsLastUpdate = safeGet(data, "ams.last_update", safeGet(data, "printers.ams_last_update", "-"));

    setText("sys_printer_total", totalPrinters, 0);
    setText("sys_printer_online", onlineCount, 0);
    setText("sys_ams_count", amsCount, 0);
    setText("sys_ams_last_update", amsLastUpdate || "-", "-");

    const reqRateRaw = safeGet(data, "runtime.requests_per_min", safeGet(data, "requests.rate", null));
    const respAvgRaw = safeGet(data, "runtime.avg_response_ms", safeGet(data, "requests.response_avg", null));
    const reqRateNum = reqRateRaw !== null && reqRateRaw !== undefined ? Number(reqRateRaw) : NaN;
    const hasReqData = Number.isFinite(reqRateNum) && reqRateNum > 0;
    if (!hasReqData) {
        setText("sys_runtime_rpm", "–", "–");
        setText("sys_runtime_avg", "–", "–");
    } else {
        setText("sys_runtime_rpm", reqRateNum, "–");
        const respNum = respAvgRaw !== null && respAvgRaw !== undefined ? Number(respAvgRaw) : NaN;
        setText("sys_runtime_avg", Number.isFinite(respNum) ? `${respNum} ms` : "–", "–");
    }
}
// Defensive DOM helpers to keep debug center quiet when elements are missing
// Defensive DOM helpers to keep debug center quiet when elements are missing
const DEBUG_VERBOSE = false;
const __missingFeatureLog = new Set();
const __origGetElementById = document.getElementById.bind(document);
const __origQuerySelector = document.querySelector.bind(document);
const __origQuerySelectorAll = document.querySelectorAll.bind(document);
const __noop = () => {};

function __logMissing(label) {
    if (__missingFeatureLog.has(label)) return;
    __missingFeatureLog.add(label);
    if (DEBUG_VERBOSE) {
        console.debug(`Debug feature ${label} not mounted yet`);
    }
}

function createNullElement(label = 'unknown') {
    const dummy = {
        __isNull: true,
        addEventListener: __noop,
        removeEventListener: __noop,
        dispatchEvent: () => false,
        appendChild: __noop,
        removeChild: __noop,
        querySelector: (sel) => {
            __logMissing(`${label} ${sel}`);
            return createNullElement(`${label} ${sel}`);
        },
        querySelectorAll: () => [],
        setAttribute: __noop,
        getContext: () => null,
        focus: __noop,
        click: __noop,
        classList: {
            add: __noop,
            remove: __noop,
            toggle: __noop,
            contains: () => false
        },
        style: {},
        dataset: {},
        set innerHTML(_) {},
        set textContent(_) {},
        set value(_) {},
        get value() { return ''; },
        set checked(_) {},
        get checked() { return false; },
        set disabled(_) {},
        get disabled() { return false; },
        set href(_) {},
        set download(_) {},
        width: 0,
        height: 0
    };
    return new Proxy(dummy, {
        get(target, prop) {
            if (prop in target) return target[prop];
            return __noop;
        },
        set(target, prop, value) {
            target[prop] = value;
            return true;
        }
    });
}

function isNullElement(el) {
    return !el || el.__isNull === true;
}

document.__origGetElementById = __origGetElementById;
document.__origQuerySelector = __origQuerySelector;
document.__origQuerySelectorAll = __origQuerySelectorAll;

document.getElementById = function (id) {
    const el = __origGetElementById(id);
    if (!el) {
        __logMissing(`#${id}`);
        return createNullElement(`#${id}`);
    }
    return el;
};

document.querySelector = function (selector) {
    const el = __origQuerySelector(selector);
    if (!el) {
        __logMissing(selector);
        return createNullElement(selector);
    }
    return el;
};

document.querySelectorAll = function (selector) {
    const list = __origQuerySelectorAll(selector);
    if (list && list.length) return list;
    __logMissing(selector);
    const arr = [];
    arr.forEach = Array.prototype.forEach.bind(arr);
    arr.map = Array.prototype.map.bind(arr);
    return arr;
};

window.addEventListener('load', () => {
    if (__missingFeatureLog.size && !DEBUG_VERBOSE) {
        console.debug(`Debug: ${__missingFeatureLog.size} features not mounted yet (migration in progress)`);
    }
});
