// === INIT ===
document.addEventListener('DOMContentLoaded', () => {
    console.log('[Dashboard] Initializing Live Operations Dashboard (FULL MATCH)');
    loadDashboardDataFull();
    setInterval(loadDashboardDataFull, 5000); // Refresh every 5 seconds for live feel
});

const ACTIVE_JOB_STATES = new Set(['RUNNING', 'PAUSE', 'ERROR']);

// === LOAD DATA (LIVE-STATE) ===
// === LOAD DATA (ALLE DRUCKER + LIVE-STATE) ===
async function loadDashboardDataFull() {
    try {
        // Hole alle Drucker aus der Datenbank
        const printersRes = await fetch('/api/printers/');
        const printers = await printersRes.json();
        // Hole Live-State
        const liveRes = await fetch('/api/live-state/');
        const liveData = await liveRes.json();
        // Mappe Live-State nach cloud_serial, nutze payload.print falls vorhanden, sonst payload
        const liveMap = Object.fromEntries(
            Object.entries(liveData).map(([k, v]) => [k, v.payload && v.payload.print ? v.payload.print : v.payload])
        );
        // Kombiniere Druckerliste mit Live-State anhand cloud_serial
        const printerList = printers.map(printer => {
            const live = liveMap[printer.cloud_serial] || {};
            return { ...printer, live };
        });
        console.log('[DEBUG] printerList:', printerList);
        updateLiveStatusFull(printerList);
        updateActiveJobsFull(printerList);
        updateRefreshTime();

        // === NEU: Statistik-API für Tageswerte ===
        try {
            const statsRes = await fetch('/api/statistics/heatmap?days=1');
            const statsData = await statsRes.json();
            // statsData.data ist ein Array mit einem Eintrag für heute
            const today = (statsData.data && statsData.data.length > 0) ? statsData.data[0] : null;
            if (today) {
                // Druckzeit (duration_h) in Minuten
                const durationMin = Math.round((today.duration_h || 0) * 60);
                document.getElementById('avgTimeTodayValue').textContent = durationMin > 0 ? formatDuration(durationMin) : '0 Min';
                document.getElementById('avgTimeTodayLabel').textContent = 'Heute';
                // Filamentverbrauch (filament_g)
                document.getElementById('filamentTodayValue').textContent = (today.filament_g || 0).toFixed(1) + ' g';
            } else {
                document.getElementById('avgTimeTodayValue').textContent = '0 Min';
                document.getElementById('avgTimeTodayLabel').textContent = 'Heute';
                document.getElementById('filamentTodayValue').textContent = '0.0 g';
            }
        } catch (err) {
            console.warn('[Dashboard] Statistik-API nicht erreichbar:', err);
        }
    } catch (error) {
        console.error('[Dashboard] Error loading dashboard data:', error);
    }
}

// === UPDATE LIVE STATUS (ALLE DRUCKER + LIVE-STATE) ===
function updateLiveStatusFull(printerList) {
    const totalCount = printerList.length;
    // Online: Wenn ein Live-State-Objekt für den Drucker existiert (unabhängig von Feldern)
    const onlineCount = printerList.filter(p => p.live && Object.keys(p.live).length > 0).length;
    document.getElementById('onlinePrinters').textContent = onlineCount;
    document.getElementById('printerStats').textContent = `${onlineCount}/${totalCount} Online`;

    // Aktive Drucke (robuste Logik wie in updateActiveJobsFull)
        const activePrinters = printerList.filter(p => {
            const state = typeof p.live?.gcode_state === 'string' ? p.live.gcode_state.toUpperCase() : '';
            return ACTIVE_JOB_STATES.has(state);
        });
    document.getElementById('activeJobCount').textContent = activePrinters.length;

    // Alerts: Zeige Warnung, wenn nicht alle online sind
    updateAlertsLive(totalCount, onlineCount);
}

// === UPDATE ACTIVE JOBS (ALLE DRUCKER + LIVE-STATE) ===
function updateActiveJobsFull(printerList) {
        const activePrinters = printerList.filter(p => {
            const state = typeof p.live?.gcode_state === 'string' ? p.live.gcode_state.toUpperCase() : '';
            return ACTIVE_JOB_STATES.has(state);
        });
    const container = document.getElementById('activeJobsList');
    if (activePrinters.length === 0) {
        container.innerHTML = '<p style="color: var(--text-dim); text-align: center; padding: 20px;">Keine aktiven Drucke</p>';
        return;
    }
    container.innerHTML = activePrinters.map(printer => {
        const rawGcode = printer.live.gcode_file || printer.live.file;
        const gcodeBase = rawGcode && rawGcode.includes('/') ? rawGcode.split('/').pop() : rawGcode;
        const jobName = printer.live.subtask_name
            || printer.live.job_name
            || gcodeBase
            || 'Unbekannter Job';
        const printerName = printer.name || printer.cloud_serial || 'Unbekannter Drucker';
        const progress = printer.live.percent || 0;
        return `
            <div class="job-card">
                <div>
                    <div class="job-name">${jobName}</div>
                    <div class="job-printer">${printerName}</div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 14px; font-weight: 600; color: var(--accent-2);">${progress.toFixed(0)}%</div>
                    <div style="font-size: 11px; color: var(--text-dim);">verbleibend</div>
                </div>
            </div>
        `;
    }).join('');
}

// === UPDATE ALERTS (LIVE-STATE) ===
function updateAlertsLive(totalCount, onlineCount) {
    const alerts = [];
    const offlineCount = totalCount - onlineCount;
    if (offlineCount > 0) {
        alerts.push(`⚠️ ${offlineCount} Drucker offline`);
    }
    const container = document.getElementById('alertsList');
    if (alerts.length === 0) {
        container.innerHTML = '<p style="color: var(--text-dim); font-size: 12px;">Keine Alerts</p>';
    } else {
        container.innerHTML = alerts.map(a => `<p style="color: var(--error); font-size: 12px;">${a}</p>`).join('');
    }
}

// === UPDATE REFRESH TIME ===
function updateRefreshTime() {
    const now = new Date();
    const time = now.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    document.getElementById('refreshTime').textContent = `Aktualisiert ${time}`;
}

// === HELPERS ===
function formatDuration(minutes) {
    if (minutes < 1) return '< 1 Min';
    if (minutes < 60) return `${Math.round(minutes)} Min`;
    const hours = Math.floor(minutes / 60);
    const mins = Math.round(minutes % 60);
    return `${hours}h ${mins}m`;
}
