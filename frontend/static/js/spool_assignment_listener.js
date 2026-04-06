/**
 * Spool Assignment Listener
 *
 * Connects to SSE stream for new AMS spool detections.
 * Shows toast notifications and opens assignment dialog on click.
 */

(function() {
    console.log("[SpoolAssignmentListener] Initializing...");

    let eventSource = null;
    let reconnectAttempts = 0;
    const MAX_RECONNECT_ATTEMPTS = 5;

    function connect() {
        console.log("[SpoolAssignmentListener] Connecting to SSE stream...");

        eventSource = new EventSource('/api/spools/new-detected/stream');

        eventSource.onopen = function() {
            console.log("[SpoolAssignmentListener] Connected");
            reconnectAttempts = 0;
        };

        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);

                if (data.type === 'new_spool_detected') {
                    console.log("[SpoolAssignmentListener] New spool detected:", data);
                    handleNewSpool(data);
                }
            } catch (err) {
                console.error("[SpoolAssignmentListener] Parse error:", err);
            }
        };

        eventSource.onerror = function() {
            console.error("[SpoolAssignmentListener] Connection error");
            eventSource.close();

            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
                reconnectAttempts++;
                console.log(`[SpoolAssignmentListener] Reconnecting in ${delay}ms (attempt ${reconnectAttempts})...`);
                setTimeout(connect, delay);
            }
        };
    }

    // Verzoegerung nach Job-Start: 5 Minuten warten bevor Hinweis erscheint
    const JOB_START_DELAY_MS = 5 * 60 * 1000;

    function handleNewSpool(data) {
        // Store for later (immer sofort speichern, egal ob verzoegert)
        storePending(data);

        // Pruefen ob ein Job gerade erst gestartet wurde (< 5 min)
        fetch('/api/jobs/active')
            .then(r => r.ok ? r.json() : [])
            .then(activeJobs => {
                const now = Date.now();
                let delayMs = 0;

                if (Array.isArray(activeJobs) && activeJobs.length > 0) {
                    // Juengsten Job finden
                    const recentJob = activeJobs.reduce((best, job) => {
                        if (!job.started_at) return best;
                        const t = new Date(job.started_at).getTime();
                        return (!best || t > new Date(best.started_at).getTime()) ? job : best;
                    }, null);

                    if (recentJob && recentJob.started_at) {
                        const elapsed = now - new Date(recentJob.started_at).getTime();
                        if (elapsed < JOB_START_DELAY_MS) {
                            delayMs = JOB_START_DELAY_MS - elapsed;
                            console.log(`[SpoolAssignmentListener] Job kuerzlich gestartet (${Math.round(elapsed / 1000)}s), Hinweis in ${Math.round(delayMs / 1000)}s`);
                        }
                    }
                }

                setTimeout(() => showNewSpoolNotification(data), delayMs);
            })
            .catch(() => {
                // Fehler beim API-Aufruf: sofort anzeigen
                showNewSpoolNotification(data);
            });
    }

    function showNewSpoolNotification(data) {
        // Build description
        const material = data.tray_sub_brands || data.tray_type || 'Unbekannt';
        const slot = data.ams_slot != null ? `Slot ${Number(data.ams_slot) + 1}` : 'AMS';
        const printer = data.printer_name ? ` (${data.printer_name})` : '';

        // Show toast
        if (typeof window.GlobalNotifications !== 'undefined' &&
            typeof window.GlobalNotifications.triggerAlert === 'function') {

            window.GlobalNotifications.triggerAlert({
                id: `new_spool_${data.tray_uuid || data.tag_uid || Date.now()}`,
                type: 'warning',
                label: 'Neue Spule erkannt',
                message: `${material} in ${slot}${printer} - Klicken zum Zuordnen`,
                persistent: true,
                onClick: () => {
                    openAssignmentDialog(data);
                }
            });
        }
    }

    function openAssignmentDialog(data) {
        if (typeof window.SpoolAssignmentDialog !== 'undefined' &&
            typeof window.SpoolAssignmentDialog.open === 'function') {
            window.SpoolAssignmentDialog.open(data);
        } else {
            console.warn("[SpoolAssignmentListener] Dialog not loaded, redirecting to /spools");
            window.location.href = '/spools';
        }
    }

    function storePending(data) {
        try {
            let pending = JSON.parse(localStorage.getItem('pending_spool_assignments') || '[]');

            // Deduplicate by tray_uuid or tag_uid
            const key = data.tray_uuid || data.tag_uid;
            if (key) {
                pending = pending.filter(p => (p.tray_uuid || p.tag_uid) !== key);
            }

            pending.push({
                ...data,
                timestamp: new Date().toISOString(),
            });

            localStorage.setItem('pending_spool_assignments', JSON.stringify(pending));
        } catch (err) {
            console.error("[SpoolAssignmentListener] Failed to store pending:", err);
        }
    }

    /**
     * Prüft beim Seitenaufruf ob ausstehende Spulen-Zuordnungen existieren.
     * Falls ja, wird nach 2s automatisch der Dialog geöffnet.
     * So wird sichergestellt dass der Dialog erscheint, auch wenn der Benutzer
     * die SSE-Benachrichtigung verpasst hat.
     */
    function checkPendingOnPageLoad() {
        try {
            const pending = JSON.parse(localStorage.getItem('pending_spool_assignments') || '[]');
            if (!pending.length) return;

            const first = pending[0];

            if (!first.spool_id) {
                // Kein spool_id → keine Auto-Spule erstellt (neues Verhalten).
                // Einfach den Dialog wieder anzeigen damit User noch zuordnen kann.
                console.log('[SpoolAssignmentListener] Ausstehende Zuordnung (kein spool_id) gefunden, öffne Dialog...');
                setTimeout(() => showNewSpoolNotification(first), 2000);
                return;
            }

            // spool_id vorhanden → prüfe ob die Spule noch in der DB existiert
            fetch(`/api/spools/${first.spool_id}`)
                .then(r => {
                    if (!r.ok) {
                        // Spule existiert nicht mehr → Eintrag bereinigen
                        let p = JSON.parse(localStorage.getItem('pending_spool_assignments') || '[]');
                        const key = first.tray_uuid || first.tag_uid;
                        p = p.filter(x => (x.tray_uuid || x.tag_uid) !== key);
                        localStorage.setItem('pending_spool_assignments', JSON.stringify(p));
                        return;
                    }
                    // Spule existiert noch → Dialog nach kurzer Verzögerung öffnen
                    console.log('[SpoolAssignmentListener] Ausstehende Zuordnung gefunden, öffne Dialog...');
                    setTimeout(() => showNewSpoolNotification(first), 2000);
                })
                .catch(() => {});
        } catch (err) {
            console.error('[SpoolAssignmentListener] Fehler beim Pending-Check:', err);
        }
    }

    // Initialize
    function init() {
        connect();
        // Pending-Zuordnungen nach kurzem Delay prüfen (warte bis UI bereit ist)
        setTimeout(checkPendingOnPageLoad, 3000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Cleanup
    window.addEventListener('beforeunload', function() {
        if (eventSource) {
            eventSource.close();
        }
    });

    // Export
    window.SpoolAssignmentListener = {
        reconnect: connect,
        getPending: () => JSON.parse(localStorage.getItem('pending_spool_assignments') || '[]'),
        clearPending: () => localStorage.removeItem('pending_spool_assignments'),
        checkPending: checkPendingOnPageLoad,
    };

    console.log("[SpoolAssignmentListener] Initialized");
})();
