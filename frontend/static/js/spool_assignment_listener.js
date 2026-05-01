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
    const JOB_START_DELAY_MS = 5 * 60 * 1000;
    const PRINTER_STATUS_CACHE_MS = 15 * 1000;
    let printerStatusCache = {
        fetchedAt: 0,
        printers: [],
    };

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

    async function fetchPrinters() {
        const now = Date.now();
        if ((now - printerStatusCache.fetchedAt) < PRINTER_STATUS_CACHE_MS && Array.isArray(printerStatusCache.printers)) {
            return printerStatusCache.printers;
        }

        const response = await fetch('/api/printers/');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const printers = await response.json();
        printerStatusCache = {
            fetchedAt: now,
            printers: Array.isArray(printers) ? printers : [],
        };
        return printerStatusCache.printers;
    }

    async function isPrinterCurrentlyOnline(data) {
        if (!data?.printer_id) return true;

        try {
            const printers = await fetchPrinters();
            const printer = printers.find(p => p.id === data.printer_id);
            return printer ? Boolean(printer.online) : true;
        } catch (err) {
            console.warn('[SpoolAssignmentListener] Printer status check failed, showing notification anyway', err);
            return true;
        }
    }

    function removePending(key) {
        if (!key) return;

        try {
            let pending = JSON.parse(localStorage.getItem('pending_spool_assignments') || '[]');
            pending = pending.filter(p => (p.tray_uuid || p.tag_uid) !== key);
            localStorage.setItem('pending_spool_assignments', JSON.stringify(pending));
        } catch (err) {
            console.error('[SpoolAssignmentListener] Failed to remove pending:', err);
        }
    }

    function storePending(data) {
        try {
            let pending = JSON.parse(localStorage.getItem('pending_spool_assignments') || '[]');

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

    function handleNewSpool(data) {
        storePending(data);

        fetch('/api/jobs/active')
            .then(r => r.ok ? r.json() : [])
            .then(activeJobs => {
                const now = Date.now();
                let delayMs = 0;

                if (Array.isArray(activeJobs) && activeJobs.length > 0) {
                    const recentJob = activeJobs.reduce((best, job) => {
                        if (!job.started_at) return best;
                        const timestamp = new Date(job.started_at).getTime();
                        return (!best || timestamp > new Date(best.started_at).getTime()) ? job : best;
                    }, null);

                    if (recentJob && recentJob.started_at) {
                        const elapsed = now - new Date(recentJob.started_at).getTime();
                        if (elapsed < JOB_START_DELAY_MS) {
                            delayMs = JOB_START_DELAY_MS - elapsed;
                            console.log(`[SpoolAssignmentListener] Job recently started (${Math.round(elapsed / 1000)}s), showing hint in ${Math.round(delayMs / 1000)}s`);
                        }
                    }
                }

                setTimeout(() => {
                    showNewSpoolNotification(data);
                }, delayMs);
            })
            .catch(() => {
                showNewSpoolNotification(data);
            });
    }

    async function showNewSpoolNotification(data) {
        const key = data?.tray_uuid || data?.tag_uid;
        const printerOnline = await isPrinterCurrentlyOnline(data);
        if (!printerOnline) {
            console.log('[SpoolAssignmentListener] Skip notification because printer is offline:', data?.printer_name || data?.printer_id);
            removePending(key);
            return;
        }

        const material = data.tray_sub_brands || data.tray_type || 'Unbekannt';
        const slot = data.ams_slot != null ? `Slot ${Number(data.ams_slot) + 1}` : 'AMS';
        const printer = data.printer_name ? ` (${data.printer_name})` : '';

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

    function checkPendingOnPageLoad() {
        try {
            const pending = JSON.parse(localStorage.getItem('pending_spool_assignments') || '[]');
            if (!pending.length) return;

            const first = pending[0];
            const key = first.tray_uuid || first.tag_uid;

            isPrinterCurrentlyOnline(first)
                .then(isOnline => {
                    if (!isOnline) {
                        console.log('[SpoolAssignmentListener] Remove pending assignment for offline printer');
                        removePending(key);
                        return;
                    }

                    if (!first.spool_id) {
                        console.log('[SpoolAssignmentListener] Pending assignment without spool_id found, reopening dialog...');
                        setTimeout(() => showNewSpoolNotification(first), 2000);
                        return;
                    }

                    fetch(`/api/spools/${first.spool_id}`)
                        .then(r => {
                            if (!r.ok) {
                                removePending(key);
                                return;
                            }

                            console.log('[SpoolAssignmentListener] Pending assignment found, reopening dialog...');
                            setTimeout(() => showNewSpoolNotification(first), 2000);
                        })
                        .catch(() => {});
                })
                .catch(() => {});
        } catch (err) {
            console.error('[SpoolAssignmentListener] Error while checking pending assignments:', err);
        }
    }

    function init() {
        connect();
        setTimeout(checkPendingOnPageLoad, 3000);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    window.addEventListener('beforeunload', function() {
        if (eventSource) {
            eventSource.close();
        }
    });

    window.SpoolAssignmentListener = {
        reconnect: connect,
        getPending: () => JSON.parse(localStorage.getItem('pending_spool_assignments') || '[]'),
        clearPending: () => localStorage.removeItem('pending_spool_assignments'),
        checkPending: checkPendingOnPageLoad,
    };

    console.log("[SpoolAssignmentListener] Initialized");
})();
