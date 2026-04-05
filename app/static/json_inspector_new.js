// ============================================
// NEUER SAUBERER JSON INSPECTOR
// ============================================

console.log('🔥 JSON Inspector NEU geladen:', new Date().toISOString());

let jsonInspectorPollInterval = null;
let jsonInspectorPaused = true;
let expandLevel = 2; // Standardmäßig bis Level 2 aufklappen

// Simple JSON Tree Renderer - mit Baumstruktur und Collapse-Funktionalität
function renderJsonInspectorTree(data, targetContainer = null) {
    const container = targetContainer || document.getElementById('json-inspector-tree');
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
    container.style.lineHeight = '1.6';

    function createNode(key, value, level = 0) {
        const wrapper = document.createElement('div');
        wrapper.style.marginLeft = (level * 20) + 'px';

        if (value === null) {
            wrapper.innerHTML = `<span style="color:#888">${key}:</span> <span style="color:#666">null</span>`;
            container.appendChild(wrapper);
        } else if (typeof value === 'object' && !Array.isArray(value)) {
            // Objekt mit Collapse-Button
            const header = document.createElement('div');
            header.style.cursor = 'pointer';
            header.style.userSelect = 'none';
            header.style.display = 'flex';
            header.style.alignItems = 'center';
            header.style.gap = '5px';
            header.style.padding = '2px 0';
            header.style.borderRadius = '3px';
            header.addEventListener('mouseenter', () => { header.style.backgroundColor = 'rgba(74, 158, 255, 0.1)'; });
            header.addEventListener('mouseleave', () => { header.style.backgroundColor = ''; });

            const toggle = document.createElement('span');
            toggle.textContent = '▼';
            toggle.style.fontSize = '10px';
            toggle.style.color = '#666';
            toggle.style.transition = 'transform 0.2s';

            const label = document.createElement('span');
            label.innerHTML = `<span style="color:#4a9eff;font-weight:bold">${key}</span> <span style="color:#666">{...}</span>`;

            header.appendChild(toggle);
            header.appendChild(label);
            wrapper.appendChild(header);

            const childContainer = document.createElement('div');
            const shouldExpand = level < expandLevel;
            childContainer.style.display = shouldExpand ? 'block' : 'none';
            toggle.style.transform = shouldExpand ? 'rotate(0deg)' : 'rotate(-90deg)';

            Object.keys(value).forEach(k => {
                const childWrapper = document.createElement('div');
                childWrapper.style.marginLeft = '20px';
                createNodeInto(k, value[k], level + 1, childWrapper);
                childContainer.appendChild(childWrapper);
            });

            wrapper.appendChild(childContainer);
            container.appendChild(wrapper);

            // Toggle-Funktion
            header.addEventListener('click', (e) => {
                e.stopPropagation();
                const isHidden = childContainer.style.display === 'none';
                childContainer.style.display = isHidden ? 'block' : 'none';
                toggle.style.transform = isHidden ? 'rotate(0deg)' : 'rotate(-90deg)';
            });
        } else if (Array.isArray(value)) {
            // Array mit Collapse-Button
            const header = document.createElement('div');
            header.style.cursor = 'pointer';
            header.style.userSelect = 'none';
            header.style.display = 'flex';
            header.style.alignItems = 'center';
            header.style.gap = '5px';
            header.style.padding = '2px 0';
            header.style.borderRadius = '3px';
            header.addEventListener('mouseenter', () => { header.style.backgroundColor = 'rgba(74, 158, 255, 0.1)'; });
            header.addEventListener('mouseleave', () => { header.style.backgroundColor = ''; });

            const toggle = document.createElement('span');
            toggle.textContent = '▼';
            toggle.style.fontSize = '10px';
            toggle.style.color = '#666';
            toggle.style.transition = 'transform 0.2s';

            const label = document.createElement('span');
            label.innerHTML = `<span style="color:#4a9eff;font-weight:bold">${key}</span> <span style="color:#666">[${value.length}]</span>`;

            header.appendChild(toggle);
            header.appendChild(label);
            wrapper.appendChild(header);

            const childContainer = document.createElement('div');
            const shouldExpand = level < expandLevel;
            childContainer.style.display = shouldExpand ? 'block' : 'none';
            toggle.style.transform = shouldExpand ? 'rotate(0deg)' : 'rotate(-90deg)';

            value.forEach((item, i) => {
                const childWrapper = document.createElement('div');
                childWrapper.style.marginLeft = '20px';
                createNodeInto(`[${i}]`, item, level + 1, childWrapper);
                childContainer.appendChild(childWrapper);
            });

            wrapper.appendChild(childContainer);
            container.appendChild(wrapper);

            // Toggle-Funktion
            header.addEventListener('click', (e) => {
                e.stopPropagation();
                const isHidden = childContainer.style.display === 'none';
                childContainer.style.display = isHidden ? 'block' : 'none';
                toggle.style.transform = isHidden ? 'rotate(0deg)' : 'rotate(-90deg)';
            });
        } else if (typeof value === 'string') {
            wrapper.innerHTML = `<span style="color:#888">${key}:</span> <span style="color:#8ef0b5">"${value}"</span>`;
            container.appendChild(wrapper);
        } else if (typeof value === 'number') {
            wrapper.innerHTML = `<span style="color:#888">${key}:</span> <span style="color:#ffd666">${value}</span>`;
            container.appendChild(wrapper);
        } else if (typeof value === 'boolean') {
            wrapper.innerHTML = `<span style="color:#888">${key}:</span> <span style="color:#ff9a8a">${value}</span>`;
            container.appendChild(wrapper);
        } else {
            wrapper.innerHTML = `<span style="color:#888">${key}:</span> ${value}`;
            container.appendChild(wrapper);
        }
    }

    // Hilfsfunktion für verschachtelte Nodes
    function createNodeInto(key, value, level, parentElement) {
        if (value === null) {
            parentElement.innerHTML = `<span style="color:#888">${key}:</span> <span style="color:#666">null</span>`;
        } else if (typeof value === 'object' && !Array.isArray(value)) {
            const header = document.createElement('div');
            header.style.cursor = 'pointer';
            header.style.userSelect = 'none';
            header.style.display = 'flex';
            header.style.alignItems = 'center';
            header.style.gap = '5px';
            header.style.padding = '2px 0';
            header.style.borderRadius = '3px';
            header.addEventListener('mouseenter', () => { header.style.backgroundColor = 'rgba(74, 158, 255, 0.1)'; });
            header.addEventListener('mouseleave', () => { header.style.backgroundColor = ''; });

            const toggle = document.createElement('span');
            toggle.textContent = '▼';
            toggle.style.fontSize = '10px';
            toggle.style.color = '#666';
            toggle.style.transition = 'transform 0.2s';

            const label = document.createElement('span');
            label.innerHTML = `<span style="color:#4a9eff;font-weight:bold">${key}</span> <span style="color:#666">{...}</span>`;

            header.appendChild(toggle);
            header.appendChild(label);
            parentElement.appendChild(header);

            const childContainer = document.createElement('div');
            const shouldExpand = level < expandLevel;
            childContainer.style.display = shouldExpand ? 'block' : 'none';
            toggle.style.transform = shouldExpand ? 'rotate(0deg)' : 'rotate(-90deg)';

            Object.keys(value).forEach(k => {
                const childWrapper = document.createElement('div');
                childWrapper.style.marginLeft = '20px';
                createNodeInto(k, value[k], level + 1, childWrapper);
                childContainer.appendChild(childWrapper);
            });

            parentElement.appendChild(childContainer);

            header.addEventListener('click', (e) => {
                e.stopPropagation();
                const isHidden = childContainer.style.display === 'none';
                childContainer.style.display = isHidden ? 'block' : 'none';
                toggle.style.transform = isHidden ? 'rotate(0deg)' : 'rotate(-90deg)';
            });
        } else if (Array.isArray(value)) {
            const header = document.createElement('div');
            header.style.cursor = 'pointer';
            header.style.userSelect = 'none';
            header.style.display = 'flex';
            header.style.alignItems = 'center';
            header.style.gap = '5px';
            header.style.padding = '2px 0';
            header.style.borderRadius = '3px';
            header.addEventListener('mouseenter', () => { header.style.backgroundColor = 'rgba(74, 158, 255, 0.1)'; });
            header.addEventListener('mouseleave', () => { header.style.backgroundColor = ''; });

            const toggle = document.createElement('span');
            toggle.textContent = '▼';
            toggle.style.fontSize = '10px';
            toggle.style.color = '#666';
            toggle.style.transition = 'transform 0.2s';

            const label = document.createElement('span');
            label.innerHTML = `<span style="color:#4a9eff;font-weight:bold">${key}</span> <span style="color:#666">[${value.length}]</span>`;

            header.appendChild(toggle);
            header.appendChild(label);
            parentElement.appendChild(header);

            const childContainer = document.createElement('div');
            const shouldExpand = level < expandLevel;
            childContainer.style.display = shouldExpand ? 'block' : 'none';
            toggle.style.transform = shouldExpand ? 'rotate(0deg)' : 'rotate(-90deg)';

            value.forEach((item, i) => {
                const childWrapper = document.createElement('div');
                childWrapper.style.marginLeft = '20px';
                createNodeInto(`[${i}]`, item, level + 1, childWrapper);
                childContainer.appendChild(childWrapper);
            });

            parentElement.appendChild(childContainer);

            header.addEventListener('click', (e) => {
                e.stopPropagation();
                const isHidden = childContainer.style.display === 'none';
                childContainer.style.display = isHidden ? 'block' : 'none';
                toggle.style.transform = isHidden ? 'rotate(0deg)' : 'rotate(-90deg)';
            });
        } else if (typeof value === 'string') {
            parentElement.innerHTML = `<span style="color:#888">${key}:</span> <span style="color:#8ef0b5">"${value}"</span>`;
        } else if (typeof value === 'number') {
            parentElement.innerHTML = `<span style="color:#888">${key}:</span> <span style="color:#ffd666">${value}</span>`;
        } else if (typeof value === 'boolean') {
            parentElement.innerHTML = `<span style="color:#888">${key}:</span> <span style="color:#ff9a8a">${value}</span>`;
        } else {
            parentElement.innerHTML = `<span style="color:#888">${key}:</span> ${value}`;
        }
    }

    createNode('root', data, 0);
    console.log('✅ JSON Tree gerendert');
}

// Export als window.renderJsonTree für Kompatibilität mit debug.html
window.renderJsonTree = renderJsonInspectorTree;

// Expand/Collapse All Funktionen
function expandAll() {
    const container = document.getElementById('json-inspector-tree');
    if (!container) return;

    const allToggles = container.querySelectorAll('div[style*="cursor: pointer"]');
    allToggles.forEach(toggle => {
        const nextSibling = toggle.nextElementSibling;
        if (nextSibling && nextSibling.style.display === 'none') {
            nextSibling.style.display = 'block';
            const arrow = toggle.querySelector('span:first-child');
            if (arrow) arrow.style.transform = 'rotate(0deg)';
        }
    });
    console.log('✅ Alle Nodes aufgeklappt');
}

function collapseAll() {
    const container = document.getElementById('json-inspector-tree');
    if (!container) return;

    const allToggles = container.querySelectorAll('div[style*="cursor: pointer"]');
    allToggles.forEach(toggle => {
        const nextSibling = toggle.nextElementSibling;
        if (nextSibling && nextSibling.style.display === 'block') {
            nextSibling.style.display = 'none';
            const arrow = toggle.querySelector('span:first-child');
            if (arrow) arrow.style.transform = 'rotate(-90deg)';
        }
    });
    console.log('✅ Alle Nodes zugeklappt');
}

// Suchfunktion
function searchTree(searchTerm) {
    const container = document.getElementById('json-inspector-tree');
    if (!container) return;

    const allElements = container.querySelectorAll('div');

    if (!searchTerm) {
        // Reset highlighting
        allElements.forEach(el => {
            el.style.backgroundColor = '';
        });
        return;
    }

    const lowerSearch = searchTerm.toLowerCase();
    let matchCount = 0;

    allElements.forEach(el => {
        const text = el.textContent.toLowerCase();
        if (text.includes(lowerSearch) && el.children.length === 0) {
            el.style.backgroundColor = '#3a5a3a';
            matchCount++;

            // Expand parent nodes
            let parent = el.parentElement;
            while (parent && parent !== container) {
                if (parent.style.display === 'none') {
                    parent.style.display = 'block';
                    const prevSibling = parent.previousElementSibling;
                    if (prevSibling) {
                        const arrow = prevSibling.querySelector('span:first-child');
                        if (arrow) arrow.style.transform = 'rotate(0deg)';
                    }
                }
                parent = parent.parentElement;
            }
        } else {
            el.style.backgroundColor = '';
        }
    });

    console.log(`🔍 Suche: "${searchTerm}" - ${matchCount} Treffer`);
}

window.expandAll = expandAll;
window.collapseAll = collapseAll;
window.searchTree = searchTree;

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
                const isOnline = firstDevice.printer_online === true;
                badge.className = isOnline ? 'status-badge status-ok' : 'status-badge status-warn';
                badge.textContent = isOnline ? 'Live' : 'Offline';
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

    // Expand/Collapse Buttons
    const expandBtn = document.getElementById('json-expand-all');
    if (expandBtn) {
        expandBtn.addEventListener('click', expandAll);
        console.log('✅ Expand-All Button registriert');
    }

    const collapseBtn = document.getElementById('json-collapse-all');
    if (collapseBtn) {
        collapseBtn.addEventListener('click', collapseAll);
        console.log('✅ Collapse-All Button registriert');
    }

    // Search Input
    const searchInput = document.getElementById('json-search');
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                searchTree(e.target.value);
            }, 300);
        });
        console.log('✅ Search Input registriert');
    }

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
