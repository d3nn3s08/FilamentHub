/**
 * Spool Assignment Listener
 *
 * Connects to SSE stream for new AMS spool detections.
 * Shows toast notifications and opens assignment dialog on click.
 */

(function() {
    console.log("[SpoolAssignmentListener] Initializing...");

    const PENDING_STORAGE_KEY = 'pending_spool_assignments';
    const MAX_RECONNECT_ATTEMPTS = 5;
    const JOB_START_DELAY_MS = 5 * 60 * 1000;
    const PRINTER_STATUS_CACHE_MS = 15 * 1000;
    const SPOOLS_CACHE_MS = 10 * 1000;

    let eventSource = null;
    let reconnectAttempts = 0;
    let printerStatusCache = {
        fetchedAt: 0,
        printers: [],
    };
    let spoolsCache = {
        fetchedAt: 0,
        spools: [],
    };

    function normalizeIdentifier(value) {
        if (value == null) return null;
        const normalized = String(value).trim();
        if (!normalized || /^0+$/.test(normalized)) return null;
        return normalized;
    }

    function normalizeFeederKey(data) {
        if (!data) return null;

        const rawAmsId = data.ams_id;
        if (rawAmsId == null) return null;

        const amsId = String(rawAmsId).trim();
        if (!amsId) return null;
        if (amsId.includes(':')) return amsId;

        const feederType = String(data.feeder_type || '').trim().toUpperCase();
        return feederType ? `${feederType}:${amsId}` : amsId;
    }

    function getDetectionKey(data) {
        if (!data) return null;

        const trayUuid = normalizeIdentifier(data.tray_uuid);
        if (trayUuid) return `tray:${trayUuid}`;

        const tagUid = normalizeIdentifier(data.tag_uid);
        if (tagUid) return `tag:${tagUid}`;

        const printerId = data.printer_id ? String(data.printer_id).trim() : '';
        const feederKey = data.feeder_key ? String(data.feeder_key).trim() : normalizeFeederKey(data);
        const amsSlot = data.ams_slot != null ? Number(data.ams_slot) : null;
        if (printerId && amsSlot != null && !Number.isNaN(amsSlot)) {
            return `slot:${printerId}:${feederKey || 'unknown'}:${amsSlot}`;
        }

        return null;
    }

    function detectionMatchesSpool(data, spool) {
        if (!data || !spool) return false;

        const trayUuid = normalizeIdentifier(data.tray_uuid);
        if (trayUuid && String(spool.tray_uuid || '') === trayUuid) return true;

        const tagUid = normalizeIdentifier(data.tag_uid);
        if (tagUid && String(spool.tag_uid || spool.rfid_uid || '') === tagUid) return true;

        const printerId = data.printer_id ? String(data.printer_id).trim() : '';
        const feederKey = normalizeFeederKey(data);
        const spoolFeederKey = normalizeFeederKey({
            ams_id: spool.ams_id,
            feeder_type: spool.last_seen_in_ams_type
        });
        const amsSlot = data.ams_slot != null ? Number(data.ams_slot) : null;

        return Boolean(
            printerId &&
            amsSlot != null &&
            !Number.isNaN(amsSlot) &&
            String(spool.printer_id || '').trim() === printerId &&
            Number(spool.ams_slot) === amsSlot &&
            (!feederKey || feederKey === spoolFeederKey)
        );
    }

    function getPendingAssignments() {
        try {
            const pending = JSON.parse(localStorage.getItem(PENDING_STORAGE_KEY) || '[]');
            return Array.isArray(pending) ? pending : [];
        } catch (err) {
            console.error('[SpoolAssignmentListener] Failed to read pending assignments:', err);
            return [];
        }
    }

    function setPendingAssignments(pending) {
        localStorage.setItem(PENDING_STORAGE_KEY, JSON.stringify(Array.isArray(pending) ? pending : []));
    }

    function clearSpoolCache() {
        spoolsCache = {
            fetchedAt: 0,
            spools: [],
        };
    }

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
                    clearSpoolCache();
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

    async function fetchSpools() {
        const now = Date.now();
        if ((now - spoolsCache.fetchedAt) < SPOOLS_CACHE_MS && Array.isArray(spoolsCache.spools)) {
            return spoolsCache.spools;
        }

        const response = await fetch('/api/spools/');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const spools = await response.json();
        spoolsCache = {
            fetchedAt: now,
            spools: Array.isArray(spools) ? spools : [],
        };
        return spoolsCache.spools;
    }

    async function isDetectionAlreadyAssigned(data) {
        try {
            const spools = await fetchSpools();
            return spools.some(spool => detectionMatchesSpool(data, spool));
        } catch (err) {
            console.warn('[SpoolAssignmentListener] Assigned-state check failed, showing notification anyway', err);
            return false;
        }
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

    function removePending(keyOrDetection) {
        const key = typeof keyOrDetection === 'string' ? keyOrDetection : getDetectionKey(keyOrDetection);
        if (!key) return;

        try {
            const pending = getPendingAssignments().filter(item => getDetectionKey(item) !== key);
            setPendingAssignments(pending);
        } catch (err) {
            console.error('[SpoolAssignmentListener] Failed to remove pending:', err);
        }
    }

    function storePending(data) {
        try {
            const key = getDetectionKey(data);
            let pending = getPendingAssignments();
            if (key) {
                pending = pending.filter(item => getDetectionKey(item) !== key);
            }

            pending.push({
                ...data,
                identity_key: key,
                timestamp: new Date().toISOString(),
            });

            setPendingAssignments(pending);
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
        const key = getDetectionKey(data);
        const printerOnline = await isPrinterCurrentlyOnline(data);
        if (!printerOnline) {
            console.log('[SpoolAssignmentListener] Skip notification because printer is offline:', data?.printer_name || data?.printer_id);
            removePending(data);
            return;
        }

        if (await isDetectionAlreadyAssigned(data)) {
            console.log('[SpoolAssignmentListener] Skip notification because slot is already assigned:', data);
            removePending(data);
            return;
        }

        const material = data.tray_sub_brands || data.tray_type || 'Unbekannt';
        const slot = data.ams_slot != null ? `Slot ${Number(data.ams_slot) + 1}` : 'AMS';
        const printer = data.printer_name ? ` (${data.printer_name})` : '';

        if (typeof window.GlobalNotifications !== 'undefined' &&
            typeof window.GlobalNotifications.triggerAlert === 'function') {
            window.GlobalNotifications.triggerAlert({
                id: `new_spool_${key || Date.now()}`,
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

    async function checkPendingOnPageLoad() {
        try {
            let pending = getPendingAssignments();
            if (!pending.length) return;

            const unresolved = [];
            for (const item of pending) {
                if (!(await isDetectionAlreadyAssigned(item))) {
                    unresolved.push(item);
                }
            }

            if (unresolved.length !== pending.length) {
                setPendingAssignments(unresolved);
            }

            pending = unresolved;
            if (!pending.length) return;

            const first = pending[0];
            const key = getDetectionKey(first);

            isPrinterCurrentlyOnline(first)
                .then(isOnline => {
                    if (!isOnline) {
                        console.log('[SpoolAssignmentListener] Remove pending assignment for offline printer');
                        removePending(first);
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
                                removePending(first);
                                return;
                            }

                            console.log('[SpoolAssignmentListener] Pending assignment found, reopening dialog...');
                            setTimeout(() => showNewSpoolNotification(first), 2000);
                        })
                        .catch(() => {
                            if (key) removePending(key);
                        });
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
        getPending: getPendingAssignments,
        clearPending: () => localStorage.removeItem(PENDING_STORAGE_KEY),
        checkPending: checkPendingOnPageLoad,
        getIdentityKey: getDetectionKey,
    };

    console.log("[SpoolAssignmentListener] Initialized");
})();
