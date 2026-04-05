// === INIT ===
document.addEventListener('DOMContentLoaded', () => {
    console.log('[Dashboard] Initializing Live Operations Dashboard (FULL MATCH)');
    loadDashboardDataFull();
    setInterval(loadDashboardDataFull, 15000); // Refresh every 15 seconds (optimized from 5s)
});

// === LOAD DATA (LIVE-STATE) ===
// === LOAD DATA (ALLE DRUCKER + LIVE-STATE) ===
async function loadDashboardDataFull() {
    try {
        // Alle API-Calls parallel starten (statt sequentiell ~200ms pro Call)
        const [printersRes, jobRes, liveRes, statsRes] = await Promise.all([
            fetch('/api/printers/'),
            fetch('/api/jobs/active').catch(() => null),
            fetch('/api/live-state/'),
            fetch('/api/statistics/heatmap?days=1').catch(() => null)
        ]);

        const printers = await printersRes.json();

        // Jobs verarbeiten
        let jobsByPrinterId = new Map();
        try {
            if (jobRes && jobRes.ok) {
                const jobs = await jobRes.json();
                if (Array.isArray(jobs)) {
                    jobs.forEach(job => {
                        if (job.printer_id) jobsByPrinterId.set(job.printer_id, job);
                    });
                }
            }
        } catch (err) {
            console.warn('[Dashboard] Failed to parse /api/jobs/active', err);
        }

        // Live-State verarbeiten
        const liveData = await liveRes.json();
        const liveMap = Object.fromEntries(Object.entries(liveData));

        // Kombiniere Druckerliste mit Live-State anhand cloud_serial (Bambu) oder klipper_{id} (Klipper)
        const printerList = printers.map(printer => {
            const liveKey = printer.cloud_serial || `klipper_${printer.id}`;
            const liveEntry = liveMap[liveKey] || null;
            const livePayload = liveEntry?.payload && liveEntry.payload.print ? liveEntry.payload.print : liveEntry?.payload;
            const job = jobsByPrinterId.get(printer.id);
            const hasActiveJob = jobsByPrinterId.has(printer.id);
            return {
                ...printer,
                live: livePayload || {},
                live_state: liveEntry,
                hasActiveJob,
                job_progress: job?.progress,
                job_eta_seconds: job?.eta_seconds,
                job_finished_at: job?.finished_at,
                job_started_at: job?.started_at,
                job_name: job?.name || job?.print_name || job?.job_name || '',
                series: job?.series || printer.series || 'UNKNOWN',
                print_source: job?.print_source
            };
        });

        updateLiveStatusFull(printerList);
        updateActiveJobsFull(printerList);
        updateRefreshTime();

        // Statistik-Daten verarbeiten (bereits parallel geladen)
        try {
            if (statsRes && statsRes.ok) {
                const statsData = await statsRes.json();
                const today = (statsData.data && statsData.data.length > 0) ? statsData.data[0] : null;
                if (today) {
                    const durationMin = Math.round((today.duration_h || 0) * 60);
                    document.getElementById('avgTimeTodayValue').textContent = durationMin > 0 ? formatDuration(durationMin) : '0 Min';
                    document.getElementById('avgTimeTodayLabel').textContent = 'Heute';
                    document.getElementById('filamentTodayValue').textContent = (today.filament_g || 0).toFixed(1) + ' g';
                } else {
                    document.getElementById('avgTimeTodayValue').textContent = '0 Min';
                    document.getElementById('avgTimeTodayLabel').textContent = 'Heute';
                    document.getElementById('filamentTodayValue').textContent = '0.0 g';
                }
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
    const onlineCount = printerList.filter(p => p.live_state?.printer_online === true).length;
    document.getElementById('onlinePrinters').textContent = onlineCount;
    document.getElementById('printerStats').textContent = `${onlineCount}/${totalCount} Online`;

    // Aktive Drucke: Zähle nur Drucker mit aktivem Job in der DB
    // (Konsistent mit updateActiveJobsFull - keine Live-State Fallbacks mehr)
    const activePrintersCount = printerList.filter(p => p.hasActiveJob).length;
    document.getElementById('activeJobCount').textContent = activePrintersCount;

    // Alerts: Zeige detaillierte Warnungen
    updateAlertsLive(totalCount, onlineCount, printerList);
}

// === UPDATE ACTIVE JOBS (ALLE DRUCKER + LIVE-STATE) ===
function updateActiveJobsFull(printerList) {
    const container = document.getElementById('activeJobsList');

    // NUR Jobs aus der Datenbank verwenden (keine Fallback-Logik mehr!)
    // Das Backend tracked korrekt wann ein Job fertig ist (finished_at wird gesetzt).
    // Live-State Fallbacks führten zu Race Conditions und "Geister-Karten".
    // Nutze das hasActiveJob Flag, das bereits in loadDashboardDataFull gesetzt wurde.
    const activePrinters = printerList.filter(p => p.hasActiveJob);
    if (activePrinters.length === 0) {
        container.innerHTML = '<p style="color: var(--text-dim); text-align: center; padding: 20px;">Keine aktiven Drucke</p>';
        return;
    }
    // Job-Daten sind bereits in printerList gemappt (job_progress, job_eta_seconds, etc.)
    const enrichedPrinters = activePrinters;

    // Use centralized renderer from activePrintCard.js
    if (typeof renderActiveJobs === 'function') {
        renderActiveJobs(container, enrichedPrinters);
    } else {
        // Fallback to simple list if renderer not available
        container.innerHTML = activePrinters.map(printer => {
            const rawGcode = printer.live.gcode_file || printer.live.file || '';
            const gcodeBase = rawGcode && rawGcode.includes('/') ? rawGcode.split('/').pop() : rawGcode;
            const jobName = printer.live.subtask_name || printer.live.job_name || gcodeBase || 'Unbekannter Job';
            const printerName = printer.name || printer.cloud_serial || 'Unbekannter Drucker';
            const progress = (printer.live && printer.live.percent != null) ? printer.live.percent : null;
            return `
                <div class="job-card">
                    <div>
                        <div class="job-name">${jobName}</div>
                        <div class="job-printer">${printerName}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size: 14px; font-weight: 600; color: var(--accent-2);">${progress != null ? progress.toFixed(0) + '%' : '—'}</div>
                        <div style="font-size: 11px; color: var(--text-dim);">fertig</div>
                    </div>
                </div>
            `;
        }).join('');
    }
}

// === UPDATE ALERTS (LIVE-STATE) ===
function updateAlertsLive(totalCount, onlineCount, printerList = []) {
    const warnings = [];
    const alerts = [];

    // 1. WARNINGS - Spulen mit niedrigem Füllstand
    const lowSpools = printerList.filter(p => {
        if (!p.live_state?.payload?.ams) return false;
        const amsUnits = p.live_state.payload.ams.ams || [];
        return amsUnits.some(ams => {
            const trays = ams.trays || ams.tray || [];
            return trays.some(tray => {
                const remain = tray.remain || 0;
                return remain > 0 && remain < 15; // < 15%
            });
        });
    });
    if (lowSpools.length > 0) {
        const printerNames = lowSpools.map(p => p.name || p.cloud_serial).slice(0, 2);
        const moreCount = lowSpools.length > 2 ? ` (+${lowSpools.length - 2})` : '';
        warnings.push({
            type: 'warning',
            icon: '⚠️',
            title: 'Spulen mit niedrigem Füllstand',
            detail: printerNames.join(', ') + moreCount + ' - Bald leer'
        });
    }

    // 2. WARNINGS - AMS Humidity
    const highHumidity = printerList.filter(p => {
        if (!p.live_state?.payload?.ams) return false;
        const amsUnits = p.live_state.payload.ams.ams || [];
        return amsUnits.some(ams => {
            const humidity = ams.humidity_raw || ams.humidity;
            return humidity && humidity > 40;
        });
    });
    if (highHumidity.length > 0) {
        highHumidity.forEach(p => {
            const printerName = p.name || p.cloud_serial;
            warnings.push({
                type: 'warning',
                icon: '💧',
                title: 'AMS Luftfeuchtigkeit hoch',
                detail: `${printerName} - Filament könnte beeinträchtigt werden`
            });
        });
    }

    // 3. ALERTS - Offline-Drucker
    const offlinePrinters = printerList.filter(p => p.live_state?.printer_online !== true);
    if (offlinePrinters.length > 0) {
        const printerNames = offlinePrinters.map(p => p.name || p.cloud_serial).slice(0, 3);
        const moreCount = offlinePrinters.length > 3 ? ` (+${offlinePrinters.length - 3} weitere)` : '';
        alerts.push({
            type: 'error',
            icon: '🔴',
            title: `${offlinePrinters.length} Drucker offline`,
            detail: printerNames.join(', ') + moreCount
        });
    }

    // 4. ALERTS - Drucker mit ERROR-Status
    const errorPrinters = printerList.filter(p => {
        if (p.live_state?.printer_online !== true) return false;
        const state = typeof p.live?.gcode_state === 'string' ? p.live.gcode_state.toUpperCase() : '';
        return state === 'ERROR' || state === 'FAILED';
    });
    if (errorPrinters.length > 0) {
        errorPrinters.forEach(p => {
            const printerName = p.name || p.cloud_serial;
            alerts.push({
                type: 'error',
                icon: '❌',
                title: 'Druckfehler',
                detail: `${printerName} - Druck fehlgeschlagen`
            });
        });
    }

    // 5. Render Warnings
    const warningsContainer = document.getElementById('warningsList');
    if (warnings.length === 0) {
        warningsContainer.innerHTML = '<p style="color: var(--text-dim); font-size: 12px;">Keine Warnungen</p>';
    } else {
        warningsContainer.innerHTML = warnings.map(warning => `
            <div class="alert-item alert-${warning.type}">
                <div class="alert-icon">${warning.icon}</div>
                <div class="alert-content">
                    <div class="alert-title">${warning.title}</div>
                    <div class="alert-detail">${warning.detail}</div>
                </div>
            </div>
        `).join('');
    }

    // 6. Render Alerts
    const alertsContainer = document.getElementById('alertsList');
    if (alerts.length === 0) {
        alertsContainer.innerHTML = '<p style="color: var(--text-dim); font-size: 12px;">Keine Alerts</p>';
    } else {
        alertsContainer.innerHTML = alerts.map(alert => `
            <div class="alert-item alert-${alert.type}">
                <div class="alert-icon">${alert.icon}</div>
                <div class="alert-content">
                    <div class="alert-title">${alert.title}</div>
                    <div class="alert-detail">${alert.detail}</div>
                </div>
            </div>
        `).join('');
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


