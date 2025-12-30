// Vanilla renderer for Active Print Card
// Exposes global function: renderActiveJobs(container, activePrinters)
(function () {
    function pad(n) { return n < 10 ? '0' + n : '' + n; }

    function formatTime(minutes) {
        if (minutes == null) return '-';
        minutes = Math.max(0, Math.round(minutes));
        const h = Math.floor(minutes / 60);
        const m = minutes % 60;
        return h > 0 ? `${h}h ${m}m` : `${m}m`;
    }

    function getStartTime(progressPercent, timeRemainingMin) {
        try {
            const now = new Date();
            const elapsed = (progressPercent / 100) * ((timeRemainingMin || 0) + (progressPercent?0:0));
            // If no reliable total, fallback to now
            const start = new Date(now.getTime() - (elapsed * 60000));
            return start.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
        } catch (e) { return '-'; }
    }

    function getEndTime(timeRemainingMin) {
        try {
            const now = new Date();
            const end = new Date(now.getTime() + (Math.max(0, Math.round(timeRemainingMin || 0)) * 60000));
            return end.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit' });
        } catch (e) { return '-'; }
    }

    function toPercent(v) {
        if (v == null) return 0;
        const n = Number(v);
        if (isNaN(n)) return 0;
        return Math.max(0, Math.min(100, Math.round(n)));
    }

    function renderCardForPrinter(printer) {
        const rawGcode = printer.live?.gcode_file || printer.live?.file || printer.live?.job_name || '';
        const gcodeBase = rawGcode && rawGcode.includes('/') ? rawGcode.split('/').pop() : rawGcode;
        const jobName = printer.live?.subtask_name || printer.live?.job_name || gcodeBase || 'Unbekannter Job';
        const printerName = printer.name || printer.cloud_serial || 'Unbekannter Drucker';
        const progress = toPercent(printer.live?.percent ?? printer.live?.progress ?? printer.live?.progress_percent);

        // time remaining: try common fields (seconds/minutes)
        let timeRemainingMin = null;
        const remSec = printer.live?.mc_remaining_time || printer.live?.remaining_time || printer.live?.remain_time || printer.live?.mc_remaining_seconds;
        if (remSec != null && Number(remSec) !== 0) {
            // assume seconds
            timeRemainingMin = Math.round(Number(remSec) / 60);
        } else if (printer.live?.time_remaining_min != null) {
            timeRemainingMin = Number(printer.live.time_remaining_min);
        }

        // Fallback: if not present, try to estimate via percent (unknown total -> leave '-')
        const timeText = formatTime(timeRemainingMin);
        const startText = getStartTime(progress, timeRemainingMin);
        const endText = getEndTime(timeRemainingMin);

        return `
            <div class="active-print-card">
                <div class="print-card-inner">
                    <div class="print-card-header">
                        <div class="print-card-title">
                            <span class="print-dot" aria-hidden="true"></span>
                            <div>
                                <div class="print-name">${escapeHtml(jobName)}</div>
                                <div class="print-sub">· ${escapeHtml(printerName)}</div>
                            </div>
                        </div>
                        <div class="print-updated">${new Date().toLocaleTimeString('de-DE', {hour:'2-digit', minute:'2-digit'})}</div>
                    </div>
                    <div class="print-progress-row">
                        <div class="print-remaining">
                            <div class="remaining-num">${100 - progress}%</div>
                            <div class="remaining-label">left</div>
                        </div>
                        <div class="print-progress-bar">
                            <div class="progress-bar-track"><div class="progress-bar-fill" style="width:${progress}%;"></div></div>
                        </div>
                        <div class="print-time">${timeText}</div>
                    </div>
                    <div class="print-time-footer">
                        <span>▶ ${startText}</span>
                        <span>🏁 ~${endText}</span>
                    </div>
                </div>
            </div>
        `;
    }

    // basic HTML escaper
    function escapeHtml(str) {
        if (str == null) return '';
        return String(str).replace(/[&<>\"]/g, function (c) { return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; });
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
            const prog = toPercent(p.live?.percent ?? p.progress ?? 0);
            return `
                <div class="job-card small">
                    <div>
                        <div class="job-name">${name}</div>
                        <div class="job-printer">${pname}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="font-size:14px;font-weight:600;color:var(--accent-2);">${prog}%</div>
                        <div style="font-size:11px;color:var(--text-dim);">fertig</div>
                    </div>
                </div>
            `;
        }).join('');
        container.innerHTML = html;
    };

})();

// Einmaliger Fetch beim Laden der Seite: /api/jobs/active nutzen (kein Polling)
document.addEventListener('DOMContentLoaded', async function () {
    try {
        const container = document.getElementById('activeJobsList');
        if (!container) return;

        const res = await fetch('/api/jobs/active');
        if (!res.ok) return; // still rely on other fallbacks
        const jobs = await res.json();
        if (!Array.isArray(jobs) || jobs.length === 0) return;

        // Map Jobs -> Printer-like shape expected by renderer
        const mapped = jobs.map(job => {
            const printerName = job.printer_name || job.printer || job.printer_id || 'Unbekannter Drucker';
            const live = {};
            if (job.progress != null) live.percent = job.progress;
            else if (job.progress_percent != null) live.percent = job.progress_percent;
            if (job.eta_seconds != null) live.mc_remaining_time = job.eta_seconds;
            // Provide some job name fields the renderer expects
            live.job_name = job.name || job.print_name || '';
            live.gcode_file = job.name || job.print_name || '';
            return { name: printerName, cloud_serial: job.printer_cloud_serial || null, live };
        });

        // Use global renderer
        if (typeof window.renderActiveJobs === 'function') {
            window.renderActiveJobs(container, mapped);
        }
    } catch (e) {
        // silent fallback to existing live-state rendering
        console.warn('[activePrintCard] Failed to fetch /api/jobs/active', e);
    }
});
