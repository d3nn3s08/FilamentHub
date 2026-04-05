// Patch: Aktive Drucke aus /api/live-state/
// Diese Datei ersetzt die Anzeige der aktiven Drucke im Dashboard durch die Daten aus /api/live-state/

document.addEventListener('DOMContentLoaded', () => {
    console.log('[Dashboard] Initializing Live Operations Dashboard (LIVE PATCH)');
    loadDashboardDataLive();
    setInterval(loadDashboardDataLive, 15000); // Optimized from 5s
});

async function loadDashboardDataLive() {
    try {
        // Hole Live-State
        const res = await fetch('/api/live-state/');
        const liveData = await res.json();
        const liveItems = Object.values(liveData || {});
        // liveData sollte ein Array von Druckern enthalten
        updateLiveActivePrints(liveItems);
        updateRefreshTime();
    } catch (error) {
        console.error('[Dashboard] Error loading live-state:', error);
    }
}

function updateLiveActivePrints(liveData) {
    // Filtere alle Drucker, die aktuell drucken
    const activePrinters = liveData.filter(p => p.printer_online === true && ['RUNNING','PRINTING','PAUSE','ERROR'].includes(String(p.payload?.print?.gcode_state || p.payload?.gcode_state || '').toUpperCase()));
    // Zähle aktive Drucke
    document.getElementById('activeJobCount').textContent = activePrinters.length;
    // Zeige Details im Bereich "Aktive Drucke"
    const container = document.getElementById('activeJobsList');
    if (activePrinters.length === 0) {
        container.innerHTML = '<p style="color: var(--text-dim); text-align: center; padding: 20px;">Keine aktiven Drucke</p>';
        return;
    }
    // Delegate rendering to activePrintCard if available
    if (typeof renderActiveJobs === 'function') {
        renderActiveJobs(container, activePrinters);
    } else {
        container.innerHTML = activePrinters.map(printer => `
            <div class="job-card">
                <div>
                    <div class="job-name">${printer.payload?.print?.file?.name || 'Unbekannter Job'}</div>
                    <div class="job-printer">${printer.printer_name || printer.device || 'Unbekannter Drucker'}</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 14px; font-weight: 600; color: var(--accent-2);">${printer.payload?.print?.progress ? printer.payload?.print?.progress.toFixed(0) : '?'}%</div>
                    <div style="font-size: 11px; color: var(--text-dim);">fertig</div>
                </div>
            </div>
        `).join('');
    }
}

function updateRefreshTime() {
    const now = new Date();
    const time = now.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    document.getElementById('refreshTime').textContent = `Aktualisiert ${time}`;
}



