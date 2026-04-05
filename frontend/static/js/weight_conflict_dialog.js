/**
 * Weight Conflict Resolution Dialog
 *
 * Modal dialog that allows users to resolve weight conflicts between
 * cloud data (from AMS) and local database.
 */

(function() {
    console.log("[WeightConflictDialog] Initializing...");

    let currentConflict = null;

    // Create modal HTML
    function createModal() {
        const modal = document.createElement('div');
        modal.id = 'weight-conflict-modal';
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h2>⚠️ Gewichts-Konflikt lösen</h2>
                    <button class="modal-close" onclick="window.WeightConflictDialog.close()">&times;</button>
                </div>

                <div class="modal-body">
                    <div class="conflict-info">
                        <div class="spool-info">
                            <strong>Spule:</strong> <span id="conflict-spool-number"></span>
                            <br>
                            <strong>Material:</strong> <span id="conflict-material"></span>
                        </div>

                        <div class="weight-comparison">
                            <div class="weight-option cloud-weight">
                                <h3>☁️ Cloud (AMS)</h3>
                                <div class="weight-value" id="cloud-weight-value">-</div>
                                <div class="weight-label">Aktuelles Gewicht</div>
                                <button class="btn-primary" onclick="window.WeightConflictDialog.resolveWith('cloud')">
                                    Cloud-Wert übernehmen
                                </button>
                            </div>

                            <div class="vs-divider">
                                <span>VS</span>
                                <div class="difference-badge" id="difference-badge">Δ -</div>
                            </div>

                            <div class="weight-option db-weight">
                                <h3>💾 Datenbank (Lokal)</h3>
                                <div class="weight-value" id="db-weight-value">-</div>
                                <div class="weight-label">Gespeichertes Gewicht</div>
                                <button class="btn-secondary" onclick="window.WeightConflictDialog.resolveWith('db')">
                                    DB-Wert behalten
                                </button>
                            </div>
                        </div>

                        <div class="manual-input-section">
                            <h3>✏️ Manueller Wert</h3>
                            <div class="input-group">
                                <input
                                    type="number"
                                    id="manual-weight-input"
                                    placeholder="z.B. 850"
                                    min="0"
                                    step="0.1"
                                >
                                <span class="unit">g</span>
                                <button class="btn-manual" onclick="window.WeightConflictDialog.resolveWith('manual')">
                                    Übernehmen
                                </button>
                            </div>
                            <small>Falls beide Werte falsch sind, kannst du hier einen eigenen Wert eingeben.</small>
                        </div>
                    </div>

                    <div class="conflict-timestamp">
                        <small>Konflikt erkannt: <span id="conflict-timestamp"></span></small>
                    </div>
                </div>

                <div class="modal-footer">
                    <button class="btn-cancel" onclick="window.WeightConflictDialog.close()">Abbrechen</button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Close on background click
        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                window.WeightConflictDialog.close();
            }
        });

        // Close on ESC key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && modal.style.display === 'flex') {
                window.WeightConflictDialog.close();
            }
        });

        return modal;
    }

    // Get or create modal
    function getModal() {
        let modal = document.getElementById('weight-conflict-modal');
        if (!modal) {
            modal = createModal();
        }
        return modal;
    }

    // Open dialog with conflict data
    function open(conflictData) {
        console.log("[WeightConflictDialog] Opening with data:", conflictData);

        currentConflict = conflictData;
        const modal = getModal();

        // Populate data
        const spoolNum = conflictData.spool_number || conflictData.number || 'N/A';
        document.getElementById('conflict-spool-number').textContent = `#${spoolNum}`;

        document.getElementById('conflict-material').textContent =
            conflictData.material_name || conflictData.material || 'Unbekannt';

        document.getElementById('cloud-weight-value').textContent =
            `${conflictData.cloud_weight}g`;

        document.getElementById('db-weight-value').textContent =
            `${conflictData.db_weight}g`;

        const diff = Math.abs(conflictData.difference || 0);
        document.getElementById('difference-badge').textContent = `Δ ${diff}g`;

        document.getElementById('conflict-timestamp').textContent =
            new Date(conflictData.timestamp || Date.now()).toLocaleString('de-DE');

        // Reset manual input
        document.getElementById('manual-weight-input').value = '';

        // Show modal
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden'; // Prevent background scroll
    }

    // Close dialog
    function close() {
        const modal = document.getElementById('weight-conflict-modal');
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = ''; // Restore scroll
        }
        currentConflict = null;
    }

    // Resolve conflict with selected option
    async function resolveWith(option) {
        if (!currentConflict) {
            console.error("[WeightConflictDialog] No conflict loaded");
            return;
        }

        let selectedSource = option;
        let cloudWeight = currentConflict.cloud_weight;
        let dbWeight = currentConflict.db_weight;
        let resolvedWeight;

        if (option === 'cloud') {
            resolvedWeight = currentConflict.cloud_weight;
        } else if (option === 'db') {
            resolvedWeight = currentConflict.db_weight;
        } else if (option === 'manual') {
            const manualInput = document.getElementById('manual-weight-input');
            const manualValue = parseFloat(manualInput.value);

            if (isNaN(manualValue) || manualValue < 0) {
                alert('Bitte gib einen gültigen Gewichtswert ein.');
                return;
            }

            resolvedWeight = manualValue;
            // For manual, override cloud weight with manual value
            cloudWeight = manualValue;
            selectedSource = 'cloud';  // Backend expects 'cloud' or 'db'
        } else {
            console.error("[WeightConflictDialog] Invalid option:", option);
            return;
        }

        console.log(`[WeightConflictDialog] Resolving with ${option}: ${resolvedWeight}g`);

        // Debug: Log the request payload
        // Support multiple UUID field names (id, spool_uuid, tray_uuid)
        const spoolUuid = currentConflict.id || currentConflict.spool_uuid || currentConflict.tray_uuid;

        const requestPayload = {
            spool_uuid: spoolUuid,
            selected_source: selectedSource,
            cloud_weight: cloudWeight,
            db_weight: dbWeight
        };
        console.log('[WeightConflictDialog] Request payload:', requestPayload);

        try {
            // Show loading state
            const buttons = document.querySelectorAll('#weight-conflict-modal button');
            buttons.forEach(btn => btn.disabled = true);

            // Send resolution to backend
            const response = await fetch('/api/weight/resolve_conflict', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestPayload)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Fehler beim Auflösen des Konflikts');
            }

            const result = await response.json();
            console.log("[WeightConflictDialog] Resolution successful:", result);

            // Remove from localStorage
            removeConflictFromStorage(spoolUuid);

            // Save data BEFORE closing (close() sets currentConflict = null!)
            const spoolNum = currentConflict.spool_number || currentConflict.number || 'N/A';
            const sourceText = option === 'cloud' ? 'Cloud (AMS)' : option === 'db' ? 'Datenbank (Lokal)' : 'Manuell';

            // Close dialog first (responsive!)
            close();

            // Show SUCCESS CONFIRMATION with alert()
            alert(
                `✅ KONFLIKT ERFOLGREICH GELÖST!\n\n` +
                `Spule #${spoolNum}\n` +
                `Neues Gewicht: ${resolvedWeight}g\n` +
                `Quelle: ${sourceText}\n\n` +
                `Die Änderung wurde in der Datenbank gespeichert.`
            );

            // Refresh spools page in background (non-blocking)
            if (window.location.pathname === '/spools' && typeof window.loadSpools === 'function') {
                setTimeout(() => window.loadSpools(), 100);
            }

        } catch (error) {
            console.error("[WeightConflictDialog] Resolution failed:", error);
            alert(`Fehler: ${error.message}`);

            // Re-enable buttons
            const buttons = document.querySelectorAll('#weight-conflict-modal button');
            buttons.forEach(btn => btn.disabled = false);
        }
    }

    // Remove conflict from localStorage
    function removeConflictFromStorage(spoolUuid) {
        try {
            let conflicts = JSON.parse(localStorage.getItem('pending_weight_conflicts') || '[]');
            conflicts = conflicts.filter(c => c.spool_uuid !== spoolUuid);
            localStorage.setItem('pending_weight_conflicts', JSON.stringify(conflicts));

            // Update badge
            if (typeof window.WeightConflictListener !== 'undefined') {
                const badge = conflicts.length;
                const spoolsLink = document.querySelector('a[href="/spools"]');
                if (spoolsLink) {
                    let badgeElem = spoolsLink.querySelector('.conflict-badge');
                    if (badge > 0) {
                        if (!badgeElem) {
                            badgeElem = document.createElement('span');
                            badgeElem.className = 'conflict-badge';
                            badgeElem.style.cssText = `
                                background: #e74c3c;
                                color: white;
                                border-radius: 10px;
                                padding: 2px 6px;
                                font-size: 11px;
                                margin-left: 5px;
                                font-weight: bold;
                            `;
                            spoolsLink.appendChild(badgeElem);
                        }
                        badgeElem.textContent = `⚠️ ${badge}`;
                    } else if (badgeElem) {
                        badgeElem.remove();
                    }
                }
            }
        } catch (err) {
            console.error("[WeightConflictDialog] Failed to update storage:", err);
        }
    }

    // Export public API
    window.WeightConflictDialog = {
        open,
        close,
        resolveWith
    };

    console.log("[WeightConflictDialog] Ready");
})();
