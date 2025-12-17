// Synced from frontend/static/js on 2025-12-14
// Debug Log Cards Renderer für Pro-Log-Viewer
// Fügt maximal 50 Log-Einträge als Karten in #log-entries ein

function renderLogCards(logLines) {
    const container = document.getElementById('log-entries');
    container.innerHTML = '';
    const lastLines = logLines.slice(-50);
    lastLines.forEach((line, idx) => {
        // Stacktrace-Erkennung
        let hasStacktrace = false;
        let message = line;
        // Prüfe auf typische Stacktrace-Marker oder Zeilenumbrüche
        if (typeof line === 'string') {
            if (line.includes('\n')) hasStacktrace = true;
            if (/Traceback \(most recent call last\):|File \\\"|Exception|Error:/i.test(line)) hasStacktrace = true;
        }
        // Zeilen splitten
        const msgLines = line.split(/\r?\n/);
        // Level bestimmen
        let level = 'info';
        if (/\bERROR|CRITICAL\b/i.test(line)) level = 'error';
        else if (/\bWARNING|WARN\b/i.test(line)) level = 'warning';
        else if (/\bDEBUG\b/i.test(line)) level = 'debug';
        // Modul extrahieren (optional, falls im Text vorhanden)
        const moduleMatch = line.match(/\[(.*?)\]/);
        // Hauptcontainer
        const div = document.createElement('div');
        div.className = 'log-line';
        div.classList.add('log-' + level);
        div.dataset.level = level;
        if (moduleMatch) div.dataset.module = moduleMatch[1];
        // .log-summary
        const summary = document.createElement('div');
        summary.className = 'log-summary';
        // Timestamp extrahieren (optional, falls im Text vorhanden)
        let timestamp = '';
        const tsMatch = line.match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)/);
        if (tsMatch) timestamp = tsMatch[1];
        if (timestamp) {
            const tsSpan = document.createElement('span');
            tsSpan.className = 'log-timestamp';
            tsSpan.textContent = timestamp + ' ';
            summary.appendChild(tsSpan);
        }
        // Level
        const lvlSpan = document.createElement('span');
        lvlSpan.className = 'log-level';
        lvlSpan.textContent = level.toUpperCase() + ' ';
        summary.appendChild(lvlSpan);
        // Kurztext (erste Zeile)
        const msgSpan = document.createElement('span');
        msgSpan.className = 'log-msg-short';
        msgSpan.textContent = msgLines[0];
        summary.appendChild(msgSpan);
        // Toggle-Button, falls Stacktrace
        let toggleBtn = null;
        if (hasStacktrace && msgLines.length > 1) {
            toggleBtn = document.createElement('button');
            toggleBtn.className = 'log-toggle-btn';
            toggleBtn.textContent = 'Details anzeigen';
            toggleBtn.onclick = function(e) {
                e.stopPropagation();
                const expanded = div.classList.toggle('expanded');
                stackDiv.style.display = expanded ? 'block' : 'none';
                toggleBtn.textContent = expanded ? 'Details ausblenden' : 'Details anzeigen';
                // Auto-Scroll deaktivieren
                if (typeof autoScroll !== 'undefined') {
                    autoScroll = false;
                    const btn = document.getElementById('proLogPauseBtn');
                    if (btn) btn.textContent = 'Fortsetzen';
                }
            };
            summary.appendChild(toggleBtn);
        }
        div.appendChild(summary);
        // .log-stacktrace
        let stackDiv = null;
        if (hasStacktrace && msgLines.length > 1) {
            stackDiv = document.createElement('div');
            stackDiv.className = 'log-stacktrace';
            stackDiv.style.display = 'none';
            stackDiv.textContent = msgLines.slice(1).join('\n');
            div.appendChild(stackDiv);
        }
        // Klick auf ganze Zeile (außer Toggle)
        div.onclick = function(e) {
            if (e.target.classList.contains('log-toggle-btn')) return;
            container.querySelectorAll('.log-line.active').forEach(e => e.classList.remove('active'));
            div.classList.add('active');
            // Log-Detail-Anzeige (optional)
            const detail = document.getElementById('log-detail');
            if (detail) detail.textContent = line;
            // Auto-Scroll deaktivieren
            if (typeof autoScroll !== 'undefined') {
                autoScroll = false;
                const btn = document.getElementById('proLogPauseBtn');
                if (btn) btn.textContent = 'Fortsetzen';
            }
        };
        container.appendChild(div);
    });
    // Auto-Scroll nach dem Rendern
    if (typeof autoScroll !== 'undefined' && autoScroll) {
        container.scrollTop = container.scrollHeight;
    }
}
// window.renderLogCards = renderLogCards;

function collapseAllLogStacktraces() {
    const container = document.getElementById('log-entries');
    container.querySelectorAll('.log-line.expanded').forEach(div => {
        div.classList.remove('expanded');
        const stack = div.querySelector('.log-stacktrace');
        if (stack) stack.style.display = 'none';
        const btn = div.querySelector('.log-toggle-btn');
        if (btn) btn.textContent = 'Details anzeigen';
    });
}

function expandAllLogStacktraces() {
    const container = document.getElementById('log-entries');
    container.querySelectorAll('.log-line').forEach(div => {
        const stack = div.querySelector('.log-stacktrace');
        if (stack) {
            div.classList.add('expanded');
            stack.style.display = 'block';
            const btn = div.querySelector('.log-toggle-btn');
            if (btn) btn.textContent = 'Details ausblenden';
        }
    });
    if (typeof autoScroll !== 'undefined') {
        autoScroll = false;
        const btn = document.getElementById('proLogPauseBtn');
        if (btn) btn.textContent = 'Fortsetzen';
    }
}

window.collapseAllLogStacktraces = collapseAllLogStacktraces;
window.expandAllLogStacktraces = expandAllLogStacktraces;
