/**
 * Weight Conflict Listener
 *
 * Connects to SSE stream and shows red alerts when weight conflicts occur
 */

(function() {
    console.log("[WeightConflictListener] Initializing...");

    let eventSource = null;
    let reconnectAttempts = 0;
    const MAX_RECONNECT_ATTEMPTS = 5;

    function connect() {
        console.log("[WeightConflictListener] Connecting to SSE stream...");

        eventSource = new EventSource('/api/weight/conflicts/stream');

        eventSource.onopen = function() {
            console.log("[WeightConflictListener] Connected to conflict stream");
            reconnectAttempts = 0;
        };

        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);

                if (data.type === 'weight_conflict') {
                    console.log("[WeightConflictListener] Conflict detected:", data);
                    handleWeightConflict(data);
                }
            } catch (err) {
                console.error("[WeightConflictListener] Parse error:", err);
            }
        };

        eventSource.onerror = function(err) {
            console.error("[WeightConflictListener] Connection error:", err);
            eventSource.close();

            // Reconnect with exponential backoff
            if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
                reconnectAttempts++;
                console.log(`[WeightConflictListener] Reconnecting in ${delay}ms (attempt ${reconnectAttempts})...`);
                setTimeout(connect, delay);
            } else {
                console.error("[WeightConflictListener] Max reconnect attempts reached");
            }
        };
    }

    function handleWeightConflict(data) {
        console.log("[WeightConflictListener] handleWeightConflict called with:", data);

        // Store conflict for later
        storeConflict(data);

        // Show toast notification using GlobalNotifications
        if (typeof window.GlobalNotifications !== 'undefined' &&
            typeof window.GlobalNotifications.triggerAlert === 'function') {

            console.log("[WeightConflictListener] Using GlobalNotifications.triggerAlert");

            window.GlobalNotifications.triggerAlert({
                id: `weight_conflict_${data.spool_uuid}`,
                type: 'error',  // RED alert
                label: `⚠️ Gewichts-Konflikt: Spule #${data.spool_number}`,
                message: `Cloud: ${data.cloud_weight?.toFixed(1)}g | DB: ${data.db_weight?.toFixed(1)}g (Δ ${data.difference?.toFixed(1)}g) - Klicken zum Lösen`,
                persistent: true,  // Stay visible until user clicks
                onClick: () => {
                    console.log("[WeightConflictListener] Toast clicked, opening dialog");
                    openConflictDialog(data);
                }
            });

            console.log(`[WeightConflictListener] Toast shown for spool #${data.spool_number}`);
        } else {
            console.warn("[WeightConflictListener] GlobalNotifications not available, using fallback");

            // Fallback: Use local showNotification if available
            if (typeof showNotification === 'function') {
                showNotification(
                    `⚠️ Gewichts-Konflikt: Spule #${data.spool_number} - Cloud: ${data.cloud_weight}g vs DB: ${data.db_weight}g`,
                    'warning'
                );
            }

            // Don't auto-open dialog - user should click the toast
            console.log("[WeightConflictListener] Conflict stored, waiting for user action");
        }
    }

    function openConflictDialog(data) {
        // TODO: Open modal dialog
        console.log("[WeightConflictListener] Opening dialog for:", data);

        // Check if conflict dialog exists
        if (typeof window.WeightConflictDialog !== 'undefined' &&
            typeof window.WeightConflictDialog.open === 'function') {
            window.WeightConflictDialog.open(data);
        } else {
            // Redirect to spools page
            console.log("[WeightConflictListener] Dialog not loaded, redirecting to /spools");
            window.location.href = '/spools?conflict=' + data.spool_uuid;
        }
    }

    function storeConflict(data) {
        try {
            let conflicts = JSON.parse(localStorage.getItem('pending_weight_conflicts') || '[]');

            // Remove duplicate if exists
            conflicts = conflicts.filter(c => c.spool_uuid !== data.spool_uuid);

            // Add new conflict
            conflicts.push({
                ...data,
                timestamp: new Date().toISOString()
            });

            localStorage.setItem('pending_weight_conflicts', JSON.stringify(conflicts));
            console.log(`[WeightConflictListener] Stored conflict, total: ${conflicts.length}`);

            // Update badge if exists
            updateConflictBadge(conflicts.length);
        } catch (err) {
            console.error("[WeightConflictListener] Failed to store conflict:", err);
        }
    }

    function updateConflictBadge(count) {
        // Update spools menu badge
        const spoolsLink = document.querySelector('a[href="/spools"]');
        if (spoolsLink) {
            let badge = spoolsLink.querySelector('.conflict-badge');
            if (count > 0) {
                if (!badge) {
                    badge = document.createElement('span');
                    badge.className = 'conflict-badge';
                    badge.style.cssText = `
                        background: #e74c3c;
                        color: white;
                        border-radius: 10px;
                        padding: 2px 6px;
                        font-size: 11px;
                        margin-left: 5px;
                        font-weight: bold;
                    `;
                    spoolsLink.appendChild(badge);
                }
                badge.textContent = `⚠️ ${count}`;
            } else if (badge) {
                badge.remove();
            }
        }
    }

    // Initialize on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', connect);
    } else {
        connect();
    }

    // Cleanup on page unload
    window.addEventListener('beforeunload', function() {
        if (eventSource) {
            eventSource.close();
        }
    });

    // Export for debugging
    window.WeightConflictListener = {
        reconnect: connect,
        getPendingConflicts: () => JSON.parse(localStorage.getItem('pending_weight_conflicts') || '[]'),
        clearConflicts: () => {
            localStorage.removeItem('pending_weight_conflicts');
            updateConflictBadge(0);
        }
    };

    console.log("[WeightConflictListener] Initialized");
})();
