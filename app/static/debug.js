// FilamentHub Debug Center JavaScript

// === STATE ===
let updateInterval = null;
let performanceInterval = null;
let cpuChart = null;
let ramChart = null;
let diskChart = null;
let performanceHistory = {
    cpu: [],
    ram: [],
    disk: [],
    timestamps: []
};

// === INIT ===
document.addEventListener('DOMContentLoaded', () => {
    initTabs();
    if (typeof loadSystemStatus === 'function') {
        loadSystemStatus();
    }
    if (typeof loadConfigData === 'function') {
        loadConfigData();
    }
    setupEventListeners?.();
    setupServiceListeners?.();
    setupDatabaseListeners?.();
    setupScannerListeners?.();
    setupMqttListeners?.();
    setupPerformanceListeners?.();
    
    // Auto-refresh every 3 seconds
    if (typeof loadSystemStatus === 'function') {
        updateInterval = setInterval(loadSystemStatus, 3000);
    }
});

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
            if (tab.dataset.tab === 'config') {
                loadConfigData();
            } else if (tab.dataset.tab === 'services') {
                loadServicesData();
            } else if (tab.dataset.tab === 'database') {
                loadDatabaseData();
            } else if (tab.dataset.tab === 'scanner') {
                loadScannerData();
            } else if (tab.dataset.tab === 'mqtt') {
                loadMqttTab();
            } else if (tab.dataset.tab === 'performance') {
                loadPerformanceData();
                startPerformanceMonitoring();
            }
        });
    });
// ... keine weitere schließende Klammer hier!

// === SYSTEM STATUS ===
async function loadSystemStatus() {
    try {
        const response = await fetch('/api/system/status');
        const data = await response.json();
        
        updateAppInfo(data.app);
        updateSystemInfo(data.system);
        updatePrinterInfo(data.printers);
        updateLoggingInfo(data.logging);
        
    } catch (error) {
        console.error('Fehler beim Laden des System-Status:', error);
    }
}

function updateAppInfo(app) {
    document.getElementById('appName').textContent = app.name;
    document.getElementById('appVersion').textContent = app.version;
    document.getElementById('appEnv').textContent = app.environment;
    document.getElementById('appUptime').textContent = app.uptime;
    document.getElementById('serverUptime').textContent = app.uptime;
    // Uhr immer aktualisieren
    if (window.uptimeTimer) clearInterval(window.uptimeTimer);
    let uptimeParts = app.uptime.split(':');
    let h = parseInt(uptimeParts[0]);
    let m = parseInt(uptimeParts[1]);
    let s = parseInt(uptimeParts[2]);
    window.uptimeTimer = setInterval(() => {
        s++;
        if (s >= 60) { s = 0; m++; }
        if (m >= 60) { m = 0; h++; }
        document.getElementById('serverUptime').textContent = `${h.toString().padStart(2,'0')}:${m.toString().padStart(2,'0')}:${s.toString().padStart(2,'0')}`;
    }, 1000);
}

function updateSystemInfo(system) {
    // CPU
    const cpuPercent = Math.round(system.cpu_percent);
    document.getElementById('cpuPercent').textContent = cpuPercent + '%';
    document.getElementById('cpuBar').style.width = cpuPercent + '%';
    document.getElementById('cpuCores').textContent = `${system.cpu_count} Cores`;
    
    // RAM
    const ramPercent = Math.round(system.ram_percent);
    document.getElementById('ramPercent').textContent = ramPercent + '%';
    document.getElementById('ramBar').style.width = ramPercent + '%';
    document.getElementById('ramDetails').textContent = 
        `${system.ram_used_gb} GB / ${system.ram_total_gb} GB (${system.ram_free_gb} GB frei)`;
    
    // Disk
    const diskPercent = system.disk_percent;
    document.getElementById('diskPercent').textContent = diskPercent + '%';
    document.getElementById('diskBar').style.width = diskPercent + '%';
    document.getElementById('diskDetails').textContent = 
        `${system.disk_used_gb} GB / ${system.disk_total_gb} GB (${system.disk_free_gb} GB frei)`;
}

function updatePrinterInfo(printers) {
    document.getElementById('printerMode').textContent = printers.mode.toUpperCase();

    const bambuElem = document.getElementById('bambuStatus');
    bambuElem.textContent = printers.bambu;
    bambuElem.classList.remove('status-online', 'status-offline');
    bambuElem.classList.add(printers.bambu === 'online' ? 'status-online' : 'status-offline');

    const klipperElem = document.getElementById('klipperStatus');
    klipperElem.textContent = printers.klipper;
    klipperElem.classList.remove('status-online', 'status-offline');
    klipperElem.classList.add(printers.klipper === 'online' ? 'status-online' : 'status-offline');
}

function updateLoggingInfo(logging) {
    // Später verwenden für Config Tab
}

// === CONFIG MANAGER ===
async function loadConfigData() {
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
            status.textContent = '● Nicht gespeichert';
            status.className = 'config-status modified';
        } else {
            status.textContent = '✓ Gespeichert';
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
        status.textContent = '💾 Speichere...';
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
            status.textContent = '✓ Erfolgreich gespeichert';
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
        status.textContent = '✗ Fehler beim Speichern';
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
        if (confirm('Config neu laden? Nicht gespeicherte Änderungen gehen verloren.')) {
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
        success: '✓',
        error: '✗',
        info: 'ℹ',
        warning: '⚠'
    }[type] || 'ℹ';
    
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
                    <span class="value" style="color: var(--success)">✓ Verfügbar</span>
                </div>
                <div class="info-item">
                    <span class="label">Version:</span>
                    <span class="value">${data.docker_version}</span>
                </div>
                <div class="info-item">
                    <span class="label">Compose:</span>
                    <span class="value">${data.compose_available ? '✓ Ja' : '✗ Nein'}</span>
                </div>
            `;
        } else {
            container.innerHTML = `
                <div class="info-item">
                    <span class="label">Status:</span>
                    <span class="value" style="color: var(--error)">✗ Nicht verfügbar</span>
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
            
            const totalSize = files.reduce((sum, f) => sum + f.size_kb, 0).toFixed(2);
            
            moduleDiv.innerHTML = `
                <div class="log-module-header">
                    <span class="log-module-title">${module.toUpperCase()}</span>
                    <button class="btn btn-danger btn-small" onclick="clearModuleLogs('${module}')">
                        🗑️ Löschen
                    </button>
                </div>
                <div class="log-files">
                    ${files.map(f => `<div>${f.name} (${f.size_kb} KB)</div>`).join('')}
                    <div style="margin-top: 4px; font-weight: 600;">Total: ${totalSize} KB</div>
                </div>
            `;
            
            container.appendChild(moduleDiv);
        }
    } catch (error) {
        console.error('Fehler beim Laden der Logs:', error);
    }
}

async function clearModuleLogs(module) {
    if (!confirm(`Alle ${module.toUpperCase()}-Logs löschen?`)) return;
    
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
        showNotification('Fehler beim Löschen', 'error');
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
    // Process
    document.getElementById('refreshProcess').addEventListener('click', loadProcessInfo);
    
    // Server
    document.getElementById('serverRestart').addEventListener('click', async () => {
        if (!confirm('Möchten Sie den Server wirklich neu starten?')) return;
        
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
        
        showNotification('Prüfe Updates...', 'info');
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
        showNotification('Prüfe veraltete Packages...', 'info');
        const result = await executeServiceCommand('/api/services/dependencies/outdated', 'GET');
        const output = document.getElementById('depsOutput');
        
        if (result.packages && result.packages.length > 0) {
            output.textContent = result.packages.map(p => 
                `${p.name}: ${p.version} → ${p.latest_version}`
            ).join('\n');
            output.classList.add('show');
            showNotification(`⚠️ ${result.count} Updates verfügbar!`, 'warning');
        } else {
            output.textContent = '✅ Alle Packages sind aktuell!';
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
    document.getElementById('runTests').addEventListener('click', async () => {
        showNotification('Führe Tests aus...', 'info', 5000);
        const result = await executeServiceCommand('/api/services/tests/run');
        const output = document.getElementById('testsOutput');
        output.textContent = result.output || result.message;
        output.classList.add('show');
        showNotification(result.message, result.success ? 'success' : 'error');
    });
    
    document.getElementById('runCoverage').addEventListener('click', async () => {
        showNotification('Führe Tests mit Coverage aus...', 'info', 5000);
        const result = await executeServiceCommand('/api/services/tests/coverage', 'GET');
        const output = document.getElementById('testsOutput');
        output.textContent = result.output || result.message;
        output.classList.add('show');
        showNotification(result.message, result.success ? 'success' : 'error');
    });
}

// === DATABASE TAB ===
async function loadDatabaseData() {
    loadDatabaseInfo();
    loadDatabaseStats();
    loadDatabaseTables();
    loadBackupsList();
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
                    <span class="value" style="color: var(--error)">✗ Nicht gefunden</span>
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
                <span class="value" style="color: var(--success)">✓ Vorhanden</span>
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
                        <span class="db-table-info">${table.row_count} Zeilen • ${table.column_count} Spalten</span>
                    </div>
                    <div class="db-columns">
                        ${table.columns.map(col => `
                            <span class="db-column">
                                ${col.name} <small>(${col.type})</small>
                                ${col.primary_key ? '<span class="badge" style="font-size: 0.7rem; padding: 2px 6px;">PK</span>' : ''}
                            </span>
                        `).join('')}
                    </div>
                    <div class="db-preview">
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
    document.getElementById('vacuumDb').addEventListener('click', async () => {
        if (!confirm('Datenbank optimieren? Dies kann einen Moment dauern.')) return;
        
        showNotification('VACUUM wird ausgeführt...', 'info');
        
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
    document.getElementById('backupDb').addEventListener('click', async () => {
        showNotification('Backup wird erstellt...', 'info');
        
        try {
            const response = await fetch('/api/database/backup', { method: 'POST' });
            const data = await response.json();
            
            const output = document.getElementById('backupOutput');
            output.textContent = `${data.message}\nDatei: ${data.backup_path}\nGröße: ${data.backup_size_mb} MB`;
            output.classList.add('show');
            
            showNotification(data.message, 'success');
            loadBackupsList();
        } catch (error) {
            showNotification('Backup Fehler: ' + error.message, 'error');
        }
    });
    
    // Refresh Backups
    document.getElementById('refreshBackups').addEventListener('click', loadBackupsList);
    
    // SQL Query
    document.getElementById('executeQuery').addEventListener('click', async () => {
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
    
    document.getElementById('clearQuery').addEventListener('click', () => {
        document.getElementById('sqlQuery').value = '';
        document.getElementById('queryOutput').textContent = '';
        document.getElementById('queryOutput').classList.remove('show');
    });
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
    document.getElementById('generateConfig').addEventListener('click', () => generateConfig());
}

async function quickScan() {
    const resultsDiv = document.getElementById('foundPrinters');
    const progressDiv = document.getElementById('scanProgress');
    
    resultsDiv.innerHTML = '';
    progressDiv.innerHTML = `
        <div>Quick Scan läuft... (überprüfe häufige IPs)</div>
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
    
    const ipRange = document.getElementById('ipRange').value;
    const timeout = document.getElementById('scanTimeout').value || 2;
    const portBambu = document.getElementById('portBambu').checked;
    const portKlipper = document.getElementById('portKlipper').checked;
    const customPorts = document.getElementById('customPorts').value
        .split(',')
        .map(p => parseInt(p.trim()))
        .filter(p => !isNaN(p));
    
    let ports = [];
    if (portBambu) ports.push(6000);
    if (portKlipper) ports.push(7125);
    ports = [...ports, ...customPorts];
    
    if (ports.length === 0) {
        showNotification('Bitte mindestens einen Port auswählen', 'warning');
        return;
    }
    
    resultsDiv.innerHTML = '';
    progressDiv.textContent = `Netzwerk scannen... (${ipRange} auf Ports: ${ports.join(', ')})`;
    progressDiv.classList.add('show');
    
    try {
        const response = await fetch('/api/scanner/scan-network', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                ip_range: ipRange, 
                ports: ports, 
                timeout: parseFloat(timeout) 
            })
        });
        const data = await response.json();
        
        progressDiv.classList.remove('show');
        displayFoundPrinters(data.hosts);
        
        if (data.hosts.length > 0) {
            showNotification(`${data.hosts.length} Hosts gefunden!`, 'success');
        } else {
            showNotification('Keine Hosts gefunden', 'info');
        }
    } catch (error) {
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
            showNotification(`✅ ${ip}:${port} ist erreichbar! (${data.response_time}ms) - ${data.type}`, 'success');
        } else {
            showNotification(`❌ ${data.message || 'Nicht erreichbar'}`, 'error');
        }
    } catch (error) {
        showNotification('Connection Test Fehler: ' + error.message, 'error');
    }
}

function displayFoundPrinters(printers) {
    const resultsDiv = document.getElementById('foundPrinters');
    resultsDiv.innerHTML = '';
    
    // Deaktiviere Config-Button bis Tests durchgeführt wurden
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
                    ${printer.hostname ? `<span>🖥️ ${printer.hostname}</span>` : ''}
                    <span>🔌 Port: ${port}</span>
                </div>
            </div>
            <div class="printer-actions">
                <button class="btn btn-secondary btn-sm" onclick="testSinglePrinter('${printer.ip}', ${port})">
                    Test
                </button>
                <button class="btn btn-primary btn-sm" onclick="savePrinterToDb('${printer.ip}', ${port}, '${printerType}', '${printer.hostname || ''}')">
                    ➕ Speichern
                </button>
                <button class="btn btn-danger btn-sm" onclick="this.closest('.printer-card').remove(); checkPrinterList()">
                    ✕
                </button>
            </div>
        `;
        
        resultsDiv.appendChild(card);
    });
}

async function savePrinterToDb(ip, port, type, hostname) {
    try {
        const data = {
            name: hostname || ip,
            printer_type: type,
            ip_address: ip,
            port: port,
            cloud_serial: null,
            api_key: null
        };
        const response = await fetch('/api/printers/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        if (response.ok) {
            showNotification('Drucker gespeichert!', 'success');
        } else {
            showNotification('Fehler beim Speichern!', 'error');
        }
    } catch (error) {
        showNotification('Fehler beim Speichern: ' + error.message, 'error');
    }
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
                    
                    // Füge Badge hinzu wenn noch nicht vorhanden
                    const badge = card.querySelector('.test-success-badge');
                    if (!badge) {
                        const actionsDiv = card.querySelector('.printer-actions') || card.querySelector('div:last-child');
                        const successBadge = document.createElement('span');
                        successBadge.className = 'test-success-badge';
                        successBadge.style.cssText = 'background: var(--success); color: white; padding: 4px 8px; border-radius: 4px; font-size: 0.75rem; margin-right: 8px;';
                        successBadge.textContent = '✓ Getestet';
                        actionsDiv.insertBefore(successBadge, actionsDiv.firstChild);
                    }
                }
            });
            
            // Prüfe ob Config-Button aktiviert werden kann
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
    
    title.innerHTML = data.success ? '✅ Verbindung erfolgreich' : '❌ Verbindung fehlgeschlagen';
    
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
                    ${data.success ? '🟢 Online' : '🔴 Offline'}
                </span>
            </div>
            <div class="info-item">
                <span class="label">Drucker-Typ:</span>
                <span class="value badge">${data.type || 'unknown'}</span>
            </div>
        </div>
        <div style="margin-top: 20px; padding: 15px; background: var(--card-bg); border-left: 3px solid ${data.success ? 'var(--success)' : 'var(--error)'}; border-radius: 4px;">
            <strong>📋 Nachricht:</strong><br>
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

async function generateConfig() {
    const resultsDiv = document.getElementById('foundPrinters');
    const testedCards = resultsDiv.querySelectorAll('.printer-card[data-tested="true"]');
    
    if (testedCards.length === 0) {
        showNotification('Keine getesteten Drucker vorhanden. Bitte teste zuerst die Drucker!', 'warning');
        return;
    }
    
    // Sammle nur erfolgreich getestete Drucker
    const printers = [];
    testedCards.forEach(card => {
        const ip = card.querySelector('.printer-ip')?.textContent || card.querySelector('strong')?.textContent;
        const badge = card.querySelector('.printer-badge');
        const type = badge?.classList.contains('bambu') ? 'Bambu Lab' :
                     badge?.classList.contains('klipper') ? 'Klipper' : 'Unknown';
        printers.push({ ip, printer_type: type });
    });
    
    try {
        const response = await fetch('/api/scanner/generate-config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ printers: printers })
        });
        const data = await response.json();
        
        // Zeige Config in einem Modal oder neuen Fenster
        const configWindow = window.open('', '_blank', 'width=800,height=600');
        configWindow.document.write(`
            <html>
            <head>
                <title>Generierte Printer Config</title>
                <style>
                    body { 
                        background: #1a1a1a; 
                        color: #e0e0e0; 
                        font-family: 'Consolas', monospace; 
                        padding: 20px;
                    }
                    pre { 
                        background: #2a2a2a; 
                        padding: 20px; 
                        border-radius: 8px; 
                        overflow: auto;
                    }
                    button {
                        background: #4fc3f7;
                        color: white;
                        border: none;
                        padding: 10px 20px;
                        border-radius: 6px;
                        cursor: pointer;
                        margin: 10px 5px;
                    }
                    button:hover { background: #29b6f6; }
                </style>
            </head>
            <body>
                <h1>🖨️ Printer Konfiguration</h1>
                <button onclick="navigator.clipboard.writeText(document.getElementById('config').textContent)">
                    📋 In Zwischenablage kopieren
                </button>
                <button onclick="window.close()">❌ Schließen</button>
                <pre id="config">${data.config}</pre>
            </body>
            </html>
        `);
        
        showNotification('Config erfolgreich generiert!', 'success');
    } catch (error) {
        showNotification('Config Generator Fehler: ' + error.message, 'error');
    }
}

// =============================
// MQTT VIEWER TAB
// =============================

let mqttWebSocket = null;
let mqttConnected = false;
let mqttPaused = false;
let mqttMessageCount = 0;
let mqttSubscribedTopics = new Set();

function loadMqttTab() {
    loadMqttStatus();
    loadMqttMessagesBuffer();
}

async function loadMqttStatus() {
    try {
        const response = await fetch('/api/mqtt/status');
        const data = await response.json();
        const active = data.active_connections || 0;
        const topics = data.subscribed_topics || [];
        const bufferSize = data.message_buffer_size || 0;

        const elActive = document.getElementById('mqttActiveConnections');
        const elTopics = document.getElementById('mqttSubscribedCount');
        const elMsgCount = document.getElementById('mqttMessagesReceived');
        const elBuffer = document.getElementById('mqttBufferSize');
        const elStatus = document.getElementById('mqttStatus');

        if (!elActive || !elTopics || !elMsgCount || !elBuffer || !elStatus) {
            console.warn('MQTT Status-Elemente nicht gefunden');
            return;
        }

        elActive.textContent = active;
        elTopics.textContent = topics.length;
        elMsgCount.textContent = bufferSize;
        elBuffer.textContent = bufferSize;
        
        if (active > 0) {
            elStatus.textContent = 'Connected';
            elStatus.style.color = 'var(--success)';
            mqttConnected = true;
            enableMqttControls(true);
        } else {
            elStatus.textContent = 'Disconnected';
            elStatus.style.color = 'var(--error)';
            mqttConnected = false;
            enableMqttControls(false);
        }
        
        updateTopicList(topics);
        
    } catch (error) {
        console.error('Fehler beim Laden des MQTT-Status:', error);
    }
}
}

// Hole vorhandene Nachrichten aus dem Buffer und zeige sie an
async function loadMqttMessagesBuffer(limit = 100) {
    try {
        const response = await fetch(`/api/mqtt/messages?limit=${limit}`);
        const data = await response.json();
        const streamDiv = document.getElementById('mqttMessageStream');
        streamDiv.innerHTML = '';
        if (!data.messages || data.messages.length === 0) {
            streamDiv.innerHTML = '<p style="color: var(--text-dim); text-align: center; padding: 20px;">Keine Nachrichten empfangen</p>';
            return;
        }
        data.messages.forEach(msg => displayMqttMessage(msg));
    } catch (error) {
        console.error('Fehler beim Laden der MQTT-Messages:', error);
    }
}

function enableMqttControls(enabled) {
    document.getElementById('mqttConnect').disabled = enabled;
    document.getElementById('mqttDisconnect').disabled = !enabled;
    document.getElementById('mqttSubscribe').disabled = !enabled;
    document.getElementById('mqttPublish').disabled = !enabled;
    document.getElementById('mqttSubscribeDefaults').disabled = !enabled;
}

function setupMqttListeners() {
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
    
    // Suggested topics
    document.querySelectorAll('.topic-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.getElementById('mqttTopic').value = btn.dataset.topic;
            subscribeTopic();
        });
    });
    
    // Message controls
    document.getElementById('mqttClearMessages').addEventListener('click', clearMessages);
    document.getElementById('mqttPauseStream').addEventListener('click', togglePause);
    
    // Publish
    document.getElementById('mqttPublish').addEventListener('click', publishMessage);
    
    // Filter
    document.getElementById('mqttFilterTopic').addEventListener('input', filterMessages);
}

// Convenience: Bambu-Default-Topics abonnieren
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
    for (const topic of DEFAULT_BAMBU_TOPICS) {
        try {
            const response = await fetch('/api/mqtt/subscribe', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ topic })
            });
            const data = await response.json();
            if (data.success) {
                mqttSubscribedTopics.add(topic);
            } else {
                showNotification(`Subscribe fehlgeschlagen für ${topic}: ${data.message || 'Unbekannter Fehler'}`, 'error');
            }
        } catch (error) {
            showNotification(`Subscribe Fehler für ${topic}: ${error.message}`, 'error');
        }
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
    const use_tls = port === 8883; // Bambu nutzt i.d.R. TLS auf 8883
    const tls_insecure = true;     // Zertifikat nicht prüfen (Drucker-CA)
    
    if (!broker) {
        showNotification('Bitte Broker-Adresse eingeben', 'warning');
        return;
    }
    
    try {
        const response = await fetch('/api/mqtt/connect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ broker, port, client_id: clientId, username, password, use_tls, tls_insecure })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`Verbunden mit ${broker}:${port}`, 'success');
            mqttConnected = true;
            enableMqttControls(true);
            
            // Connect WebSocket for live streaming
            connectMqttWebSocket();
            
            // Refresh status
            setTimeout(loadMqttStatus, 500);
        } else {
            showNotification('MQTT Verbindung fehlgeschlagen', 'error');
        }
    } catch (error) {
        showNotification('Verbindungsfehler: ' + error.message, 'error');
    }
}

async function disconnectMqtt() {
    const broker = document.getElementById('mqttBroker').value;
    const port = parseInt(document.getElementById('mqttPort').value);
    
    try {
        const response = await fetch('/api/mqtt/disconnect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ broker, port })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification('MQTT Verbindung getrennt', 'info');
            mqttConnected = false;
            enableMqttControls(false);
            
            // Close WebSocket
            if (mqttWebSocket) {
                mqttWebSocket.close();
                mqttWebSocket = null;
            }
            
            // Clear UI
            mqttSubscribedTopics.clear();
            updateTopicList([]);
            
            setTimeout(loadMqttStatus, 500);
        }
    } catch (error) {
        showNotification('Disconnect Fehler: ' + error.message, 'error');
    }
}

function connectMqttWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/mqtt/ws`;
    
    // schließe ggf. alte Verbindungen, damit der neue Stream sauber läuft
    if (mqttWebSocket) {
        mqttWebSocket.close();
    }
    
    mqttWebSocket = new WebSocket(wsUrl);
    
    mqttWebSocket.onopen = () => {
        console.log('✅ MQTT WebSocket connected');
    };
    
    mqttWebSocket.onmessage = (event) => {
        if (mqttPaused) return;
        
        const data = JSON.parse(event.data);
        
        if (data.type === 'status') {
            // Initial status message
            return;
        }
        
        // Regular MQTT message
        displayMqttMessage(data);
        mqttMessageCount++;
        document.getElementById('mqttMessageCount').textContent = mqttMessageCount;
    };
    
    mqttWebSocket.onerror = (error) => {
        console.error('❌ MQTT WebSocket error:', error);
    };
    
    mqttWebSocket.onclose = () => {
        console.log('🔌 MQTT WebSocket closed');
    };
    
    // Send ping every 30s to keep connection alive
    setInterval(() => {
        if (mqttWebSocket && mqttWebSocket.readyState === WebSocket.OPEN) {
            mqttWebSocket.send('ping');
        }
    }, 30000);
}

async function subscribeTopic() {
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
                ❌
            </button>
        `;
        listDiv.appendChild(item);
    });
}

function displayMqttMessage(message) {
    const streamDiv = document.getElementById('mqttMessageStream');
    const autoScroll = document.getElementById('mqttAutoScroll').checked;
    const formatJson = document.getElementById('mqttFormatJson').checked;
    
    // Check if first message (remove placeholder)
    if (streamDiv.children.length === 1 && streamDiv.children[0].tagName === 'P') {
        streamDiv.innerHTML = '';
    }
    
    const messageDiv = document.createElement('div');
    messageDiv.className = 'mqtt-message';
    messageDiv.dataset.topic = message.topic || '';
    
    // Try to parse JSON payload
    let payload = message.payload ?? '';
    let isJson = false;
    
    if (formatJson) {
        try {
            const jsonData = JSON.parse(message.payload);
            payload = JSON.stringify(jsonData, null, 2);
            isJson = true;
        } catch (e) {
            // Not JSON, use as-is
        }
    }
    
    const timestamp = message.timestamp
        ? new Date(message.timestamp).toLocaleTimeString('de-DE')
        : new Date().toLocaleTimeString('de-DE');

    // Header
    const header = document.createElement('div');
    header.className = 'mqtt-message-header';
    const topicSpan = document.createElement('span');
    topicSpan.className = 'mqtt-topic';
    topicSpan.textContent = message.topic || '';
    const tsSpan = document.createElement('span');
    tsSpan.className = 'mqtt-timestamp';
    tsSpan.textContent = timestamp;
    header.appendChild(topicSpan);
    header.appendChild(tsSpan);

    // Payload
    const payloadDiv = document.createElement('div');
    payloadDiv.className = 'mqtt-payload' + (isJson ? ' json' : '');
    payloadDiv.textContent = payload;

    messageDiv.appendChild(header);
    messageDiv.appendChild(payloadDiv);
    
    streamDiv.appendChild(messageDiv);
    
    // Limit messages in DOM
    while (streamDiv.children.length > 100) {
        streamDiv.removeChild(streamDiv.firstChild);
    }
    
    // Auto-scroll to bottom
    if (autoScroll) {
        streamDiv.scrollTop = streamDiv.scrollHeight;
    }
}

function clearMessages() {
    const streamDiv = document.getElementById('mqttMessageStream');
    streamDiv.innerHTML = '<p style="color: var(--text-dim); text-align: center; padding: 20px;">Messages cleared</p>';
    mqttMessageCount = 0;
    document.getElementById('mqttMessageCount').textContent = '0';
}

function togglePause() {
    mqttPaused = !mqttPaused;
    const btn = document.getElementById('mqttPauseStream');
    
    if (mqttPaused) {
        btn.textContent = '▶️ Resume';
        btn.classList.remove('btn-secondary');
        btn.classList.add('btn-success');
        showNotification('Stream pausiert', 'info');
    } else {
        btn.textContent = '⏸️ Pause';
        btn.classList.remove('btn-success');
        btn.classList.add('btn-secondary');
        showNotification('Stream fortgesetzt', 'info');
    }
}

function filterMessages() {
    const filter = document.getElementById('mqttFilterTopic').value.toLowerCase();
    const messages = document.querySelectorAll('.mqtt-message');
    
    messages.forEach(msg => {
        const topic = msg.dataset.topic.toLowerCase();
        if (filter === '' || topic.includes(filter)) {
            msg.style.display = 'block';
        } else {
            msg.style.display = 'none';
        }
    });
}

async function publishMessage() {
    const topic = document.getElementById('mqttPublishTopic').value.trim();
    const payload = document.getElementById('mqttPublishPayload').value;
    const qos = parseInt(document.getElementById('mqttPublishQos').value);
    
    if (!topic || !payload) {
        showNotification('Topic und Payload benötigt', 'warning');
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
            showNotification(`📤 Nachricht gesendet an ${topic}`, 'success');
            document.getElementById('mqttPublishPayload').value = '';
        }
    } catch (error) {
        showNotification('Publish Fehler: ' + error.message, 'error');
    }
}

// === PERFORMANCE MONITORING ===
let maxDataPoints = 60;  // Show last 60 data points in charts

function setupPerformanceListeners() {
    // Auto-refresh toggle
    document.getElementById('perfAutoRefresh').addEventListener('change', (e) => {
        if (e.target.checked) {
            startPerformanceMonitoring();
        } else {
            stopPerformanceMonitoring();
        }
    });
    
    // Clear history
    document.getElementById('perfClearHistory').addEventListener('click', clearPerformanceHistory);
    
    // Export data
    document.getElementById('perfExportData').addEventListener('click', exportPerformanceData);
    
    // Initialize charts
    initPerformanceCharts();
}

function initPerformanceCharts() {
    const cpuCanvas = document.getElementById('cpuChart');
    const ramCanvas = document.getElementById('ramChart');
    const diskCanvas = document.getElementById('diskChart');
    
    if (cpuCanvas) cpuChart = cpuCanvas.getContext('2d');
    if (ramCanvas) ramChart = ramCanvas.getContext('2d');
    if (diskCanvas) diskChart = diskCanvas.getContext('2d');
}

async function loadPerformanceData() {
    try {
        // Load current data
        const currentRes = await fetch('/api/performance/current');
        const currentData = await currentRes.json();
        
        // Update current values
        updateCurrentPerformance(currentData);
        
        // Load history
        const historyRes = await fetch(`/api/performance/history?limit=${maxDataPoints}`);
        const historyData = await historyRes.json();
        
        // Update history and statistics
        updatePerformanceHistory(historyData);
        
    } catch (error) {
        console.error('Fehler beim Laden der Performance-Daten:', error);
        showNotification('Performance-Daten konnten nicht geladen werden', 'error');
    }
}

function updateCurrentPerformance(data) {
    const current = data.current;
    const alerts = data.alerts || [];
    
    // Update current values
    document.getElementById('perfCpuValue').textContent = current.cpu_percent.toFixed(1) + '%';
    document.getElementById('perfRamValue').textContent = current.ram_percent.toFixed(1) + '%';
    document.getElementById('perfDiskValue').textContent = current.disk_percent.toFixed(1) + '%';
    
    // Update alerts
    const alertsDiv = document.getElementById('perfAlerts');
    alertsDiv.innerHTML = '';
    
    if (alerts.length > 0) {
        alerts.forEach(alert => {
            const alertEl = document.createElement('div');
            alertEl.className = `alert alert-${alert.level}`;
            alertEl.innerHTML = `
                <strong>${alert.level === 'warning' ? '⚠️' : '🚨'} ${alert.level.toUpperCase()}</strong>: 
                ${alert.message}
            `;
            alertsDiv.appendChild(alertEl);
        });
    }
}

function updatePerformanceHistory(data) {
    const history = data.history || [];
    const stats = data.statistics || {};
    
    // Clear existing history
    performanceHistory.cpu = [];
    performanceHistory.ram = [];
    performanceHistory.disk = [];
    performanceHistory.timestamps = [];
    
    // Fill history arrays
    history.forEach(point => {
        performanceHistory.cpu.push(point.cpu_percent);
        performanceHistory.ram.push(point.ram_percent);
        performanceHistory.disk.push(point.disk_percent);
        performanceHistory.timestamps.push(new Date(point.timestamp));
    });
    
    // Update charts
    drawPerformanceCharts();
    
    // Update statistics
    if (stats.cpu) {
        document.getElementById('statAvgCpu').textContent = stats.cpu.average.toFixed(1) + '%';
        document.getElementById('statMaxCpu').textContent = stats.cpu.max.toFixed(1) + '%';
    }
    if (stats.ram) {
        document.getElementById('statAvgRam').textContent = stats.ram.average.toFixed(1) + '%';
        document.getElementById('statMaxRam').textContent = stats.ram.max.toFixed(1) + '%';
    }
    
    // Update recording info
    document.getElementById('statDataPoints').textContent = history.length;
    if (data.recording_start) {
        const start = new Date(data.recording_start);
        document.getElementById('perfRecordingStart').textContent = start.toLocaleString('de-DE');
    }
}

function drawPerformanceCharts() {
    drawChart(cpuChart, performanceHistory.cpu, '#4fc3f7', 'CPU');
    drawChart(ramChart, performanceHistory.ram, '#ff9800', 'RAM');
    drawChart(diskChart, performanceHistory.disk, '#9c27b0', 'Disk');
}

function drawChart(ctx, data, color, label) {
    if (!ctx || data.length === 0) return;
    
    const canvas = ctx.canvas;
    const width = canvas.width;
    const height = canvas.height;
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    
    // Draw background
    ctx.fillStyle = '#1a1a1a';
    ctx.fillRect(0, 0, width, height);
    
    // Draw grid
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 1;
    
    // Horizontal lines (percentage markers)
    for (let i = 0; i <= 4; i++) {
        const y = (height / 4) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
        
        // Labels
        ctx.fillStyle = '#666';
        ctx.font = '10px monospace';
        ctx.fillText((100 - i * 25) + '%', 5, y - 2);
    }
    
    // Draw data line
    if (data.length > 1) {
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        
        const xStep = width / (data.length - 1);
        
        data.forEach((value, index) => {
            const x = index * xStep;
            const y = height - (value / 100 * height);
            
            if (index === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });
        
        ctx.stroke();
        
        // Draw area under line
        ctx.lineTo(width, height);
        ctx.lineTo(0, height);
        ctx.closePath();
        ctx.fillStyle = color + '22';  // 22 = 13% opacity
        ctx.fill();
    }
}

function startPerformanceMonitoring() {
    if (performanceInterval) return;
    
    performanceInterval = setInterval(() => {
        loadPerformanceData();
    }, 5000);  // Update every 5 seconds
}

function stopPerformanceMonitoring() {
    if (performanceInterval) {
        clearInterval(performanceInterval);
        performanceInterval = null;
    }
}

async function clearPerformanceHistory() {
    if (!confirm('Möchten Sie die Performance-Historie wirklich löschen?')) return;
    
    try {
        const response = await fetch('/api/performance/clear', {
            method: 'POST'
        });
        
        if (response.ok) {
            showNotification('Performance-Historie gelöscht', 'success');
            loadPerformanceData();
        } else {
            throw new Error('Fehler beim Löschen');
        }
    } catch (error) {
        showNotification('Fehler: ' + error.message, 'error');
    }
}

async function exportPerformanceData() {
    try {
        const response = await fetch('/api/performance/export');
        const data = await response.json();
        
        // Create download
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `performance_${new Date().toISOString().split('T')[0]}.json`;
        a.click();
        URL.revokeObjectURL(url);
        
        showNotification('Performance-Daten exportiert', 'success');
    } catch (error) {
        showNotification('Export Fehler: ' + error.message, 'error');
    }
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
        showNotification('Bitte gültigen Port eingeben (1-65535)', 'warning');
        return;
    }
    
    // Drucker zur Liste hinzufügen
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
    
    // Prüfe ob Drucker bereits existiert
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
                <span class="badge" style="background: var(--success); margin-left: 5px;">Manuell hinzugefügt</span>
            </div>
            <div style="display: flex; gap: 5px;">
                <button class="btn btn-sm btn-primary" onclick="testSinglePrinter('${printer.ip}', ${printer.port})">
                    Test
                </button>
                <button class="btn btn-sm btn-danger" onclick="this.closest('.printer-card').remove(); checkPrinterList()">
                    ✕
                </button>
            </div>
        </div>
    `;
    
    resultsDiv.appendChild(card);
    
    closeAddPrinterModal();
    showNotification(`Drucker ${ip}:${port} hinzugefügt. Bitte teste die Verbindung!`, 'success');
    
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

}
