// ============================================
// NEUER SAUBERER JSON INSPECTOR
// ============================================

console.log('🔥 JSON Inspector NEU geladen:', new Date().toISOString());

let jsonInspectorPollInterval = null;
let jsonInspectorPaused = true;

// Simple JSON Tree Renderer
function renderJsonInspectorTree(data) {
    const container = document.getElementById('json-inspector-tree');
    if (!container) {
        console.error('❌ json-inspector-tree Element nicht gefunden!');
        return;
    }

    console.log('✅ Rendere JSON Tree, Daten-Keys:', Object.keys(data || {}).length);

    container.innerHTML = '';
    container.style.maxHeight = '500px';
    container.style.overflow = 'auto';
    container.style.padding = '10px';
    container.style.fontFamily = 'monospace';
    container.style.fontSize = '13px';

    function createNode(key, value, level = 0) {
        const div = document.createElement('div');
        div.style.paddingLeft = (level * 20) + 'px';
        div.style.margin = '2px 0';

        if (value === null) {
            div.innerHTML = `<span style="color:#888">${key}:</span> <span style="color:#666">null</span>`;
        } else if (typeof value === 'object' && !Array.isArray(value)) {
            div.innerHTML = `<span style="color:#4a9eff;font-weight:bold">${key}</span> <span style="color:#666">{</span>`;
            container.appendChild(div);
            Object.keys(value).forEach(k => createNode(k, value[k], level + 1));
            const close = document.createElement('div');
            close.style.paddingLeft = (level * 20) + 'px';
            close.innerHTML = '<span style="color:#666">}</span>';
            container.appendChild(close);
            return;
        } else if (Array.isArray(value)) {
            div.innerHTML = `<span style="color:#4a9eff;font-weight:bold">${key}</span> <span style="color:#666">[${value.length}]</span>`;
            container.appendChild(div);
            value.forEach((item, i) => createNode(`[${i}]`, item, level + 1));
            return;
        } else if (typeof value === 'string') {
            div.innerHTML = `<span style="color:#888">${key}:</span> <span style="color:#8ef0b5">"${value}"</span>`;
        } else if (typeof value === 'number') {
            div.innerHTML = `<span style="color:#888">${key}:</span> <span style="color:#ffd666">${value}</span>`;
        } else if (typeof value === 'boolean') {
            div.innerHTML = `<span style="color:#888">${key}:</span> <span style="color:#ff9a8a">${value}</span>`;
        } else {
            div.innerHTML = `<span style="color:#888">${key}:</span> ${value}`;
        }

        container.appendChild(div);
    }

    createNode('root', data, 0);
    console.log('✅ JSON Tree gerendert');
}

// Polling-Funktion
async function pollLiveState() {
    if (jsonInspectorPaused) {
        console.log('⏸ Polling pausiert');
        return;
    }

    try {
        const res = await fetch('/api/live-state/');
        if (!res.ok) {
            console.warn('❌ Live-State API Fehler:', res.status);
            return;
        }

        const data = await res.json();
        const devices = Object.keys(data);

        console.log('📥 Live-State empfangen:', devices.length, 'Geräte');

        if (devices.length === 0) {
            const container = document.getElementById('json-inspector-tree');
            if (container) {
                container.innerHTML = '<div style="padding:40px;text-align:center;color:#888">Keine Geräte gefunden</div>';
            }
            return;
        }

        // Erstes Gerät nehmen
        const firstDevice = data[devices[0]];
        if (firstDevice && firstDevice.payload) {
            renderJsonInspectorTree(firstDevice.payload);

            // Status-Badge aktualisieren
            const badge = document.getElementById('json-inspector-status');
            if (badge) {
                badge.className = 'status-badge status-ok';
                badge.textContent = 'Live';
            }
        }
    } catch (err) {
        console.error('❌ Polling Fehler:', err);
    }
}

// Start/Stop Funktionen
function startJsonInspectorPolling() {
    console.log('▶️ Starte JSON Inspector Polling');
    jsonInspectorPaused = false;

    const btn = document.getElementById('json-pause-btn');
    if (btn) {
        btn.textContent = '⏸ Pause';
        btn.title = 'Pausieren';
    }

    pollLiveState(); // Sofort einmal aufrufen

    if (jsonInspectorPollInterval) clearInterval(jsonInspectorPollInterval);
    jsonInspectorPollInterval = setInterval(pollLiveState, 2500);
}

function stopJsonInspectorPolling() {
    console.log('⏸ Stoppe JSON Inspector Polling');
    jsonInspectorPaused = true;

    const btn = document.getElementById('json-pause-btn');
    if (btn) {
        btn.textContent = '▶ Start';
        btn.title = 'Starten';
    }

    if (jsonInspectorPollInterval) {
        clearInterval(jsonInspectorPollInterval);
        jsonInspectorPollInterval = null;
    }
}

function toggleJsonInspectorPolling() {
    if (jsonInspectorPaused) {
        startJsonInspectorPolling();
    } else {
        stopJsonInspectorPolling();
    }
}

// Auto-Start wenn MQTT verbunden
async function initJsonInspector() {
    console.log('🔧 Initialisiere JSON Inspector');

    // Button-Event
    const pauseBtn = document.getElementById('json-pause-btn');
    if (pauseBtn) {
        pauseBtn.addEventListener('click', toggleJsonInspectorPolling);
        console.log('✅ Pause-Button registriert');
    }

    // Start-Button
    const startBtn = document.getElementById('json-start-btn');
    if (startBtn) {
        startBtn.addEventListener('click', () => {
            if (jsonInspectorPaused) {
                startJsonInspectorPolling();
            }
        });
        console.log('✅ Start-Button registriert');
    }

    // MQTT-Status prüfen
    try {
        const res = await fetch('/api/mqtt/runtime/status');
        const data = await res.json();

        if (data && data.connected === true) {
            console.log('🟢 MQTT verbunden - Auto-Start');
            startJsonInspectorPolling();
        } else {
            console.log('⚫ MQTT nicht verbunden');
            const container = document.getElementById('json-inspector-tree');
            if (container) {
                container.innerHTML = '<div style="padding:40px;text-align:center;color:#888">MQTT nicht verbunden<br><br>Klicke auf <strong>▶ Start</strong> zum Testen</div>';
            }
        }
    } catch (err) {
        console.error('❌ MQTT Status Check fehlgeschlagen:', err);
    }
}

// Warten bis DOM bereit ist
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initJsonInspector);
} else {
    initJsonInspector();
}

console.log('✅ JSON Inspector Modul geladen');
