// Synced from frontend/static/js on 2025-12-14
// Lädt Logdaten für den Pro-Log-Viewer und rendert sie als Karten

let proLogLines = [];
let proLogFiltered = [];
let autoScroll = true;

function scrollLogToBottom() {
    const container = document.getElementById('log-entries');
    container.scrollTop = container.scrollHeight;
}

function renderProLogCards() {
    renderLogCards(proLogFiltered);
    if (autoScroll) scrollLogToBottom();
}

function applyProLogFilter() {
    const level = document.getElementById('proLogFilterLevel')?.value || 'ALL';
    const module = document.getElementById('proLogFilterModule')?.value || 'ALL';
    const search = document.getElementById('proLogFilterSearch')?.value?.toLowerCase() || '';
    proLogFiltered = proLogLines.filter(line => {
        let ok = true;
        if (level !== 'ALL') {
            if (level === 'ERROR' && !/\b(ERROR|CRITICAL)\b/i.test(line)) ok = false;
            if (level === 'WARNING' && !/\bWARNING\b/i.test(line)) ok = false;
            if (level === 'INFO' && !/\bINFO\b/i.test(line)) ok = false;
            if (level === 'DEBUG' && !/\bDEBUG\b/i.test(line)) ok = false;
        }
        if (module !== 'ALL' && !line.toLowerCase().includes(module.toLowerCase())) ok = false;
        if (search && !line.toLowerCase().includes(search)) ok = false;
        return ok;
    });
    renderProLogCards();
}

async function loadProLogCards() {
    const container = document.getElementById('log-entries');
    container.innerHTML = 'Lade Logs...';
    try {
        const res = await fetch('/api/debug/logs?module=app&limit=1000');
        const data = await res.json();
        let lines = [];
        if (Array.isArray(data.items)) {
            lines = data.items;
        } else if (typeof data.lines === 'string') {
            lines = data.lines.split('\n');
        } else if (Array.isArray(data.lines)) {
            lines = data.lines;
        } else {
            lines = [];
        }
        proLogLines = lines;
        applyProLogFilter();
    } catch (e) {
        container.innerHTML = 'Fehler beim Laden der Logs.';
    }
}

function observeProLogPanel() {
    const panel = document.getElementById('panel-logs');
    if (!panel) return;
    const observer = new MutationObserver(() => {
        if (panel.style.display !== 'none') {
            loadProLogCards();
        }
    });
    observer.observe(panel, { attributes: true, attributeFilter: ['style'] });
}

function setupProLogPauseButton() {
    let btn = document.getElementById('proLogPauseBtn');
    if (!btn) {
        btn = document.createElement('button');
        btn.id = 'proLogPauseBtn';
        btn.textContent = 'Pause';
        btn.className = 'btn btn-secondary';
        btn.style.margin = '8px 0 8px 0';
        btn.onclick = function() {
            autoScroll = !autoScroll;
            btn.textContent = autoScroll ? 'Pause' : 'Fortsetzen';
            if (autoScroll) scrollLogToBottom();
        };
        const logPanel = document.getElementById('panel-logs');
        if (logPanel) logPanel.querySelector('.panel')?.appendChild(btn);
    }
}

function setupProLogFilterUI() {
    const logPanel = document.getElementById('panel-logs');
    if (!logPanel) return;
    let filterBar = document.getElementById('proLogFilterBar');
    if (!filterBar) {
        filterBar = document.createElement('div');
        filterBar.id = 'proLogFilterBar';
        filterBar.style.display = 'flex';
        filterBar.style.gap = '8px';
        filterBar.style.margin = '8px 0';
        filterBar.innerHTML = `
            <select id="proLogFilterLevel" class="btn btn-secondary">
                <option value="ALL">Level: Alle</option>
                <option value="ERROR">Error</option>
                <option value="WARNING">Warning</option>
                <option value="INFO">Info</option>
                <option value="DEBUG">Debug</option>
            </select>
            <select id="proLogFilterModule" class="btn btn-secondary">
                <option value="ALL">Modul: Alle</option>
                <option value="app">App</option>
                <option value="bambu">Bambu</option>
                <option value="klipper">Klipper</option>
                <option value="mqtt">MQTT</option>
            </select>
            <input id="proLogFilterSearch" class="btn btn-secondary" placeholder="Suche..." style="min-width:120px;" />
            <button id="proLogReloadBtn" class="btn btn-primary">Neu laden</button>
            <button id="proLogCollapseAllBtn" class="btn btn-secondary">Alle einklappen</button>
            <button id="proLogExpandAllBtn" class="btn btn-secondary">Alle ausklappen</button>
        `;
        logPanel.querySelector('.panel')?.appendChild(filterBar);
    }
    document.getElementById('proLogFilterLevel').onchange = applyProLogFilter;
    document.getElementById('proLogFilterModule').onchange = applyProLogFilter;
    document.getElementById('proLogFilterSearch').oninput = applyProLogFilter;
    document.getElementById('proLogReloadBtn').onclick = loadProLogCards;
    document.getElementById('proLogCollapseAllBtn').onclick = () => {
        if (window.collapseAllLogStacktraces) window.collapseAllLogStacktraces();
    };
    document.getElementById('proLogExpandAllBtn').onclick = () => {
        if (window.expandAllLogStacktraces) window.expandAllLogStacktraces();
    };
}

function setupProLogCardClickPause() {
    const container = document.getElementById('log-entries');
    container.onclick = function(e) {
        if (e.target.classList.contains('log-line')) {
            autoScroll = false;
            const btn = document.getElementById('proLogPauseBtn');
            if (btn) btn.textContent = 'Fortsetzen';
        }
    };
}

document.addEventListener('DOMContentLoaded', () => {
    observeProLogPanel();
    setupProLogPauseButton();
    setupProLogFilterUI();
    setupProLogCardClickPause();
    const c2 = document.getElementById('proLogCollapseAllBtn2');
    if (c2) c2.onclick = () => { if (window.collapseAllLogStacktraces) window.collapseAllLogStacktraces(); };
    const e2 = document.getElementById('proLogExpandAllBtn2');
    if (e2) e2.onclick = () => { if (window.expandAllLogStacktraces) window.expandAllLogStacktraces(); };
});
