// Patch: Aktive Drucke aus /api/live-state/
// Diese Datei ersetzt die Anzeige der aktiven Drucke im Dashboard durch die Daten aus /api/live-state/

document.addEventListener('DOMContentLoaded', () => {
    console.log('[Dashboard] Initializing Live Operations Dashboard (LIVE PATCH)');
    loadDashboardDataLive();
    setInterval(loadDashboardDataLive, 5000);
});

async function loadDashboardDataLive() {
    try {
        // Hole Live-State
        const res = await fetch('/api/live-state/');
        const liveData = await res.json();
        // liveData sollte ein Array von Druckern enthalten
        updateLiveActivePrints(liveData);
        updateRefreshTime();
    } catch (error) {
        console.error('[Dashboard] Error loading live-state:', error);
    }
}

function updateLiveActivePrints(liveData) {
    // Filtere alle Drucker, die aktuell drucken
    const activePrinters = liveData.filter(p => p.state === 'printing' || p.state === 'busy');
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
                    <div class="job-name">${printer.current_job_name || 'Unbekannter Job'}</div>
                    <div class="job-printer">${printer.name || 'Unbekannter Drucker'}</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 14px; font-weight: 600; color: var(--accent-2);">${printer.progress ? printer.progress.toFixed(0) : '?'}%</div>
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
