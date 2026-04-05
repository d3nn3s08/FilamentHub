// Vanilla renderer for Active Print Card
// ============================================================
// A-SERIES LIVE UI RULES
//
// Die A-Serie (A1 / A1 mini) liefert ueber MQTT keine zuverlaessigen
// globalen Prozent- oder ETA-Werte.
// Felder wie mc_remaining_time und mc_percent sind phasenbezogen
// und duerfen NICHT fuer die Aktive-Drucke-Anzeige verwendet werden.
//
// LÖSUNG: A-Serie nutzt Backend-ETA (job_eta_seconds, layer-basiert)
// X-, P- und H-Serie nutzen weiterhin Controller-ETA (mc_remaining_time)
// ============================================================
// Exposes global function: renderActiveJobs(container, activePrinters)
(function () {
    function pad(n) { return n < 10 ? '0' + n : '' + n; }

    function formatTimeSeconds(seconds) {
        if (seconds == null) return '-';
        const totalSeconds = Math.max(0, Math.round(Number(seconds)));
        if (!Number.isFinite(totalSeconds)) return '-';
        const h = Math.floor(totalSeconds / 3600);
        const m = Math.floor((totalSeconds % 3600) / 60);
        const s = totalSeconds % 60;
        // Format: "2h 30m" oder "45m 12s" (eindeutig, keine Mehrdeutigkeit)
        return h > 0 ? `${h}h ${m}m` : `${m}m ${s}s`;
    }

    function getStartTime(progressPercent, timeRemainingSec) {
        try {
            if (timeRemainingSec == null) return '-';
            const remainingSec = Math.max(0, Math.round(Number(timeRemainingSec)));
            if (!Number.isFinite(remainingSec)) return '-';
            if (!progressPercent || progressPercent <= 0) return '-';
            const totalSec = (remainingSec * 100) / progressPercent;
            const elapsedSec = totalSec - remainingSec;
            const now = new Date();
            const start = new Date(now.getTime() - (elapsedSec * 1000));
            return start.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
        } catch (e) { return '-'; }
    }

    function getEndTime(timeRemainingSec) {
        try {
            if (timeRemainingSec == null) return '-';
            const remainingSec = Math.max(0, Math.round(Number(timeRemainingSec)));
            if (!Number.isFinite(remainingSec)) return '-';
            const now = new Date();
            const end = new Date(now.getTime() + (remainingSec * 1000));
            return end.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
        } catch (e) { return '-'; }
    }

    function toPercent(v) {
        if (v == null) return 0;
        const n = Number(v);
        if (isNaN(n)) return 0;
        return Math.max(0, Math.min(100, Math.round(n)));
    }

    function toPercentNoClamp(v) {
        if (v == null) return null;
        const n = Number(v);
        if (isNaN(n)) return null;
        return Math.max(0, Math.round(n));
    }

    function isASeries(printer) {
        return printer && printer.series === 'A';
    }

    function renderCardForPrinter(printer) {
        const rawGcode = printer.live?.gcode_file || printer.live?.file || printer.live?.job_name || '';
        const gcodeBase = rawGcode && rawGcode.includes('/') ? rawGcode.split('/').pop() : rawGcode;
        const jobName = printer.job_name || printer.live?.subtask_name || printer.live?.job_name || gcodeBase || 'Unbekannter Job';
        const printerName = printer.name || printer.cloud_serial || 'Unbekannter Drucker';
        const aSeries = isASeries(printer);
        const jobProgress = printer.job_progress ?? printer.job?.progress ?? printer.progress;
        const jobEtaSeconds = printer.job_eta_seconds ?? printer.job?.eta_seconds;
        const jobFinishedAt = printer.job_finished_at ?? printer.job?.finished_at;
        const jobStartedAt = printer.job_started_at ?? printer.job?.started_at;
        const liveLayerNum = printer.live?.layer_num ?? printer.live?.layer_current;
        const liveTotalLayers = printer.live?.total_layer_num ?? printer.live?.total_layers ?? printer.live?.layer_total;

        // Check if external spool (print_source from job API)
        // Externe Spulen haben oft keine Live-Verbrauchsdaten während des Drucks
        const isExternalSpool = printer.print_source === 'external' || printer.job?.print_source === 'external';
        const showFilamentWarning = isExternalSpool;
        let progress = null;

        if (aSeries) {
            // A-Series: Nach Bambu-Update (Jan 2026) sind mc_percent und mc_remaining_time
            // jetzt zuverlässig und inkludieren die Vorheizphase
            if (jobFinishedAt) {
                progress = 100;
            } else {
                // Nutze mc_percent vom Drucker (wie bei anderen Serien)
                const mcPercent = printer.live?.mc_percent;
                if (mcPercent != null && Number(mcPercent) > 0) {
                    progress = toPercentNoClamp(Number(mcPercent));
                } else if (liveLayerNum != null && liveTotalLayers != null && Number(liveTotalLayers) > 0) {
                    // Fallback: Layer-basiert (wenn mc_percent nicht verfügbar)
                    if (Number(liveLayerNum) === 0) {
                        progress = null;  // Zeigt "Vorbereitung..." an
                    } else {
                        progress = toPercentNoClamp((Number(liveLayerNum) / Number(liveTotalLayers)) * 100);
                    }
                }
            }
        } else {
            progress = toPercent(printer.live?.percent ?? printer.live?.progress ?? printer.live?.progress_percent);
        }

        // time remaining in seconds
        // Nach Bambu-Update (Jan 2026): Alle Serien nutzen mc_remaining_time
        let timeRemainingSec = null;
        const remSec = printer.live?.mc_remaining_time || printer.live?.remaining_time || printer.live?.remain_time || printer.live?.mc_remaining_seconds;
        if (remSec != null && Number(remSec) !== 0) {
            timeRemainingSec = Number(remSec) * 60;  // mc_remaining_time ist in Minuten
        } else if (printer.live?.time_remaining_min != null) {
            timeRemainingSec = Number(printer.live.time_remaining_min) * 60;
        }
        // Fallback: Backend-ETA (wenn mc_remaining_time nicht verfügbar)
        if (timeRemainingSec == null && jobEtaSeconds != null) {
            timeRemainingSec = Number(jobEtaSeconds);
        }

        // ========================================================
        // KRITISCH: Pre-Print-Phase Anzeige (A-Serie)
        //
        // Wenn progress = null, zeige "Vorbereitung..." statt 100%
        // ========================================================
        const isPrePrint = (progress == null && aSeries);
        const timeText = isPrePrint ? 'Vorbereitung...' : (timeRemainingSec == null ? '-' : formatTimeSeconds(timeRemainingSec));

        // Start/End-Zeiten: Alle Serien nutzen mc_remaining_time (seit Bambu-Update Jan 2026)
        const showDerivedTimes = !isPrePrint && timeRemainingSec != null && progress != null && progress > 0;

        // Start-Zeit: Nutze echte started_at aus Job (nicht berechnet!)
        // WICHTIG: Start-Zeit zeigen sobald Layer >= 1 (auch wenn ETA noch fehlt)
        let startText = '-';
        if (!isPrePrint && jobStartedAt) {
            try {
                const startDate = new Date(jobStartedAt);
                startText = startDate.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
            } catch (e) {
                startText = '-';
            }
        }

        const endText = showDerivedTimes ? getEndTime(timeRemainingSec) : '-';
        const progressValue = isPrePrint ? 0 : (progress == null ? 0 : progress);
        const remainingPercent = isPrePrint ? 0 : (progress == null ? 0 : 100 - progress);
        
        // Zeige "Warm Up" wenn Layer <= 0
        let remainingText = '';
        if (isPrePrint) {
            remainingText = 'Vorbereitung...';
        } else if (liveLayerNum != null && Number(liveLayerNum) <= 0) {
            remainingText = '🔥 Warm Up';
        } else if (progress == null) {
            remainingText = '-';
        } else {
            remainingText = `${remainingPercent}%`;
        }

        // Farbe für LEFT basierend auf Restprozent (100% → 0%):
        // Grün (0-10% remaining = fast fertig) -> Gelb (10-30%) -> Rot (30%+ = noch viel übrig)
        let remainingColor = '#ef5350'; // rot (default = viel übrig)
        let remainingClass = '';
        if (!isPrePrint && progress != null) {
            if (remainingPercent <= 10) {
                remainingColor = '#66bb6a'; // grün = fast fertig!
                remainingClass = 'low-remaining'; // Animation aktivieren bei den letzten 10%
            } else if (remainingPercent <= 30) {
                remainingColor = '#ffa726'; // gelb/orange = mittendrin
            }
        }

        return `
            <div class="active-print-card">
                <div class="print-card-inner">
                    <div class="print-card-header">
                        <div class="print-card-title">
                            <span class="print-dot" aria-hidden="true"></span>
                            <div>
                                <div class="print-name">
                                    ${escapeHtml(jobName)}
                                    ${showFilamentWarning ? '<span class="filament-warning-badge" title="Externe Spule: Verbrauch wird am Job-Ende berechnet">ⓘ Verbrauch nach Druck</span>' : ''}
                                </div>
                                <div class="print-sub">von ${escapeHtml(printerName)}</div>
                            </div>
                        </div>
                        <div class="print-updated">${new Date().toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'})}</div>
                    </div>
                    <div class="print-progress-row">
                        <div class="print-remaining">
                            <div class="remaining-num ${remainingClass}" style="color:${remainingColor};">${remainingText}</div>
                            <div class="remaining-label">${isPrePrint ? '' : 'left'}</div>
                        </div>
                        <div class="print-progress-bar">
                            <div class="progress-bar-track"><div class="progress-bar-fill" style="width:${progressValue}%;"></div></div>
                        </div>
                        <div class="print-time">${timeText}</div>
                    </div>
                    <div class="print-time-footer">
                        <span>Start ${startText}</span>
                        <span title="${aSeries ? 'Backend-ETA (Layer-basiert) - kann von Drucker-ETA abweichen' : ''}">ETA ~${endText}</span>
                    </div>
                </div>
            </div>
        `;
    }

    // basic HTML escaper
    function escapeHtml(str) {
        if (str == null) return '';
        return String(str).replace(/[&<>"]/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; });
    }

    window.renderActiveJobs = function (container, activePrinters) {
        if (!container) return;
        if (!Array.isArray(activePrinters) || activePrinters.length === 0) {
            container.innerHTML = '<p style="color: var(--text-dim); text-align: center; padding: 20px;">Keine aktiven Drucke</p>';
            return;
        }
        // Render first active print as large card, others as smaller job-cards
        const html = activePrinters.map((p, idx) => {
            if (idx === 0) return renderCardForPrinter(p);
            // fallback smaller card for additional printers
            const name = escapeHtml(p.live?.job_name || p.current_job_name || 'Unbekannter Job');
            const pname = escapeHtml(p.name || p.cloud_serial || 'Unbekannter Drucker');
            const aSeries = isASeries(p);
            let prog = null;
            if (aSeries) {
                // A-Series: Use backend job_progress or layer-based calculation
                if (p.job_finished_at) {
                    prog = 100;
                } else if (p.job_progress != null) {
                    prog = toPercentNoClamp(Number(p.job_progress) * 100);
                } else if (p.live?.layer_num != null && p.live?.total_layer_num != null && Number(p.live.total_layer_num) > 0) {
                    prog = toPercentNoClamp((Number(p.live.layer_num) / Number(p.live.total_layer_num)) * 100);
                }
            } else {
                prog = toPercent(p.live?.percent ?? p.progress ?? 0);
            }
            const progText = prog == null ? '-' : `${prog}%`;
            return `
                <div class="job-card small">
                    <div>
                        <div class="job-name">${name}</div>
                        <div class="job-printer">${pname}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size:14px;font-weight:600;color:var(--accent-2);">${progText}</div>
                        <div style="font-size:11px;color:var(--text-dim);">fertig</div>
                    </div>
                </div>
            `;
        }).join('');
        container.innerHTML = html;
    };

})();

// ============================================================
// HINWEIS: Polling wurde deaktiviert!
// Das Dashboard (dashboard.js) übernimmt das Polling für aktive Jobs.
// Dieses Modul stellt nur noch die renderActiveJobs()-Funktion bereit.
// ============================================================
