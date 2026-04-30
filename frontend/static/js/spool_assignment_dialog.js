/**
 * Spool Assignment Dialog
 *
 * Modal dialog that allows users to assign a newly detected AMS spool
 * to an existing storage spool (merge UUID/RFID data).
 */

(function() {
    console.log("[SpoolAssignmentDialog] Initializing...");
    const PENDING_AMS_CREATE_STORAGE_KEY = 'pending_manual_ams_create';

    let currentDetection = null;
    let storageSpools = [];
    let selectedTargetId = null;

    function createModal() {
        const modal = document.createElement('div');
        modal.id = 'spool-assignment-modal';
        modal.className = 'spool-assign-modal';
        modal.innerHTML = `
            <div class="spool-assign-content">
                <div class="spool-assign-header">
                    <h2>Neue Spule erkannt</h2>
                    <button class="spool-assign-close" onclick="window.SpoolAssignmentDialog.close()">&times;</button>
                </div>

                <div class="spool-assign-body">
                    <div class="detected-spool-info">
                        <div class="detected-spool-color" id="sa-detected-color"></div>
                        <div class="detected-spool-details">
                            <strong id="sa-detected-material">Unbekannt</strong>
                            <span id="sa-detected-slot">AMS Slot ?</span>
                            <span id="sa-detected-printer"></span>
                        </div>
                    </div>

                    <div class="spool-assign-description">
                        Eine neue Spule wurde im AMS erkannt. Wähle eine vorhandene Lager-Spule
                        zum Verknüpfen – oder lege eine neue Spule an.
                    </div>

                    <div class="spool-assign-search">
                        <input
                            type="text"
                            id="sa-search-input"
                            placeholder="Suche nach Nummer, Name oder Material..."
                            oninput="window.SpoolAssignmentDialog._filterSpools()"
                        >
                    </div>

                    <div class="spool-assign-list" id="sa-spool-list">
                        <div class="spool-assign-loading">Lade Lager-Spulen...</div>
                    </div>
                </div>

                <div class="spool-assign-footer">
                    <button class="sa-btn sa-btn-assign" id="sa-btn-assign" disabled
                        onclick="window.SpoolAssignmentDialog.merge()">
                        Zuordnen
                    </button>
                    <button class="sa-btn sa-btn-keep" id="sa-btn-create-new"
                        onclick="window.SpoolAssignmentDialog.createNew()">
                        Neue Spule anlegen
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        modal.addEventListener('click', function(e) {
            if (e.target === modal) {
                window.SpoolAssignmentDialog.close();
            }
        });

        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && modal.style.display === 'flex') {
                window.SpoolAssignmentDialog.close();
            }
        });

        return modal;
    }

    function getModal() {
        let modal = document.getElementById('spool-assignment-modal');
        if (!modal) {
            modal = createModal();
        }
        return modal;
    }

    async function open(detectionData) {
        console.log("[SpoolAssignmentDialog] Opening with data:", detectionData);

        currentDetection = detectionData;
        selectedTargetId = null;
        const modal = getModal();

        // Populate detected spool info
        const colorEl = document.getElementById('sa-detected-color');
        const trayColor = detectionData.tray_color || '';
        if (trayColor && trayColor.length >= 6) {
            colorEl.style.backgroundColor = '#' + trayColor.replace(/^#/, '').substring(0, 6);
        } else {
            colorEl.style.backgroundColor = '#666';
        }

        const materialText = detectionData.tray_sub_brands || detectionData.tray_type || 'Unbekannt';
        document.getElementById('sa-detected-material').textContent = materialText;

        const slotText = detectionData.ams_slot != null ? `AMS Slot ${Number(detectionData.ams_slot) + 1}` : 'AMS';
        document.getElementById('sa-detected-slot').textContent = slotText;

        const printerText = detectionData.printer_name || '';
        document.getElementById('sa-detected-printer').textContent = printerText;

        // Reset search
        const searchInput = document.getElementById('sa-search-input');
        if (searchInput) searchInput.value = '';

        // Disable assign button
        document.getElementById('sa-btn-assign').disabled = true;

        // Show modal
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';

        // Load storage spools
        await loadStorageSpools();
    }

    function close() {
        const modal = document.getElementById('spool-assignment-modal');
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }
        // Pending-Eintrag entfernen damit der Dialog nicht bei jedem Seitenaufruf erneut erscheint
        if (currentDetection) {
            removeFromStorage(detection.tray_uuid || detection.tag_uid);
        }
        currentDetection = null;
        selectedTargetId = null;
    }

    async function loadStorageSpools() {
        const listEl = document.getElementById('sa-spool-list');
        listEl.innerHTML = '<div class="spool-assign-loading">Lade Lager-Spulen...</div>';

        try {
            const resp = await fetch('/api/spools/');
            if (!resp.ok) throw new Error('API Fehler');
            storageSpools = await resp.json();

            renderSpoolList(storageSpools);
        } catch (err) {
            console.error("[SpoolAssignmentDialog] Failed to load storage spools:", err);
            listEl.innerHTML = '<div class="spool-assign-empty">Fehler beim Laden der Spulen</div>';
        }
    }

    function renderSpoolList(spools) {
        const listEl = document.getElementById('sa-spool-list');

        if (!spools || spools.length === 0) {
            listEl.innerHTML = '<div class="spool-assign-empty">Keine Lager-Spulen vorhanden</div>';
            return;
        }

        let html = '';
        for (const s of spools) {
            const color = s.color || s.tray_color || '';
            let colorStyle = 'background: #444;';
            if (color && color.length >= 6) {
                colorStyle = `background: #${color.replace(/^#/, '').substring(0, 6)};`;
            }

            const number = s.spool_number != null ? `#${s.spool_number}` : '';
            const name = s.name || s.material_name || 'Unbekannt';
            const brand = s.vendor || s.material_brand || '';
            const weight = s.weight_current != null ? `${Math.round(s.weight_current)}g` : '';
            const status = s.status || 'Lager';
            const isSelected = selectedTargetId === s.id;

            html += `
                <div class="sa-spool-card ${isSelected ? 'sa-selected' : ''}"
                     data-spool-id="${s.id}"
                     onclick="window.SpoolAssignmentDialog._selectSpool('${s.id}')">
                    <div class="sa-spool-color" style="${colorStyle}"></div>
                    <div class="sa-spool-info">
                        <div class="sa-spool-number">${number}</div>
                        <div class="sa-spool-name">${brand ? brand + ' ' : ''}${name}</div>
                    </div>
                    <div class="sa-spool-meta">
                        <span class="sa-spool-weight">${weight}</span>
                        <span class="sa-spool-status">${status}</span>
                    </div>
                </div>
            `;
        }

        listEl.innerHTML = html;
    }

    function _selectSpool(spoolId) {
        selectedTargetId = spoolId;

        // Update visual selection
        document.querySelectorAll('.sa-spool-card').forEach(card => {
            card.classList.toggle('sa-selected', card.dataset.spoolId === spoolId);
        });

        // Enable assign button
        document.getElementById('sa-btn-assign').disabled = false;
    }

    function _filterSpools() {
        const query = (document.getElementById('sa-search-input')?.value || '').toLowerCase().trim();
        if (!query) {
            renderSpoolList(storageSpools);
            return;
        }

        const filtered = storageSpools.filter(s => {
            const searchable = [
                s.spool_number != null ? `#${s.spool_number}` : '',
                s.spool_number != null ? `${s.spool_number}` : '',
                s.name || '',
                s.vendor || '',
                s.material_name || '',
                s.material_brand || '',
                s.label || '',
                s.color || '',
            ].join(' ').toLowerCase();
            return searchable.includes(query);
        });

        renderSpoolList(filtered);
    }

    async function merge() {
        if (!currentDetection || !selectedTargetId) {
            console.error("[SpoolAssignmentDialog] No detection or target selected");
            return;
        }

        const detection = { ...currentDetection };
        const sourceId = currentDetection.spool_id;  // null wenn keine Auto-Spule erstellt

        // Disable buttons
        const assignBtn = document.getElementById('sa-btn-assign');
        assignBtn.disabled = true;
        assignBtn.textContent = 'Zuordnung...';

        try {
            let resp, result;

            if (sourceId) {
                // Alte Methode: Auto-Spule existiert → merge (source → target, source löschen)
                console.log(`[SpoolAssignmentDialog] Merge: source=${sourceId} → target=${selectedTargetId}`);
                resp = await fetch('/api/spools/merge', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        source_spool_id: sourceId,
                        target_spool_id: selectedTargetId,
                    }),
                });
            } else {
                // Neue Methode: Keine Auto-Spule → AMS-Daten direkt auf Lager-Spule übertragen
                console.log(`[SpoolAssignmentDialog] Assign-from-AMS → target=${selectedTargetId}`);
                resp = await fetch(`/api/spools/${selectedTargetId}/assign-from-ams`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        tray_uuid: detection.tray_uuid || null,
                        tag_uid: detection.tag_uid || null,
                        ams_slot: detection.ams_slot,
                        ams_id: detection.ams_id || null,
                        printer_id: detection.printer_id || null,
                        remain_percent: detection.remain_percent,
                        tray_type: detection.tray_type || null,
                        tray_color: detection.tray_color || null,
                        weight_current: detection.weight_current || null,
                        weight_full: detection.weight_full || null,
                        weight_empty: detection.weight_empty || null,
                    }),
                });
            }

            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Fehler bei der Zuordnung');
            }

            result = await resp.json();
            console.log("[SpoolAssignmentDialog] Zuordnung erfolgreich:", result);

            // Remove from localStorage
            removeFromStorage(detection.tray_uuid || detection.tag_uid);

            const spoolNum = result.spool?.spool_number ? `#${result.spool.spool_number}` : '';
            const material = result.spool?.material || result.spool?.name || '';

            close();

            // Show success
            if (typeof window.GlobalNotifications !== 'undefined' &&
                typeof window.GlobalNotifications.triggerAlert === 'function') {
                window.GlobalNotifications.triggerAlert({
                    type: 'success',
                    label: 'Spule zugeordnet',
                    message: `Spule ${spoolNum} (${material}) wurde erfolgreich zugeordnet.`,
                    persistent: false,
                });
            } else {
                alert(`Spule ${spoolNum} wurde erfolgreich zugeordnet.`);
            }

            // Refresh spools page if we're on it
            if (window.location.pathname === '/spools' && typeof window.loadSpools === 'function') {
                setTimeout(() => window.loadSpools(), 200);
            }

        } catch (err) {
            console.error("[SpoolAssignmentDialog] Zuordnung fehlgeschlagen:", err);
            alert(`Fehler: ${err.message}`);
            assignBtn.disabled = false;
            assignBtn.textContent = 'Zuordnen';
        }
    }

    async function createNew() {
        if (!currentDetection) return;

        const detection = { ...currentDetection };
        if (window.location.pathname === '/spools' &&
            typeof window.openAddModalFromAmsDetection === 'function') {
            close();
            window.openAddModalFromAmsDetection(detection);
            return;
        }

        if (typeof window.persistPendingAmsCreatePrefill === 'function') {
            window.persistPendingAmsCreatePrefill(detection);
        }

        close();
        window.location.href = '/spools';
        return;

        try {
            if (detection.spool_id) {
                // Auto-Spule existiert bereits → einfach schließen (Spule bleibt wie sie ist)
                removeFromStorage(detection.tray_uuid || detection.tag_uid);
                close();
                return;
            }

            // Keine Auto-Spule → neue Spule via API anlegen
            const resp = await fetch('/api/spools/create-from-ams', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tray_uuid: detection.tray_uuid || null,
                    tag_uid: detection.tag_uid || null,
                    ams_slot: detection.ams_slot,
                    ams_id: detection.ams_id || null,
                    printer_id: detection.printer_id || null,
                    remain_percent: detection.remain_percent,
                    tray_type: detection.tray_type || null,
                    tray_sub_brands: detection.tray_sub_brands || null,
                    tray_color: detection.tray_color || null,
                    weight_current: detection.weight_current || null,
                    weight_full: detection.weight_full || null,
                    weight_empty: detection.weight_empty || null,
                    material_id: detection.material_id || null,
                    vendor: detection.vendor || null,
                }),
            });

            if (!resp.ok) {
                const err = await resp.json();
                throw new Error(err.detail || 'Fehler beim Anlegen');
            }

            const result = await resp.json();
            console.log("[SpoolAssignmentDialog] Neue Spule angelegt:", result);

            removeFromStorage(detection.tray_uuid || detection.tag_uid);
            close();

            if (typeof window.GlobalNotifications !== 'undefined' &&
                typeof window.GlobalNotifications.triggerAlert === 'function') {
                window.GlobalNotifications.triggerAlert({
                    type: 'success',
                    label: 'Neue Spule angelegt',
                    message: `Neue Spule für Slot ${detection.ams_slot != null ? Number(detection.ams_slot) + 1 : '?'} wurde angelegt.`,
                    persistent: false,
                });
            }

            if (window.location.pathname === '/spools' && typeof window.loadSpools === 'function') {
                setTimeout(() => window.loadSpools(), 200);
            }

        } catch (err) {
            console.error("[SpoolAssignmentDialog] Neue Spule fehlgeschlagen:", err);
            alert(`Fehler: ${err.message}`);
            createBtn.disabled = false;
            createBtn.textContent = 'Neue Spule anlegen';
        }
    }

    function removeFromStorage(key) {
        try {
            let pending = JSON.parse(localStorage.getItem('pending_spool_assignments') || '[]');
            pending = pending.filter(p =>
                p.tray_uuid !== key && p.tag_uid !== key
            );
            localStorage.setItem('pending_spool_assignments', JSON.stringify(pending));
        } catch (err) {
            console.error("[SpoolAssignmentDialog] Failed to update storage:", err);
        }
    }

    createNew = async function() {
        if (!currentDetection) return;

        const detection = { ...currentDetection };
        if (window.location.pathname === '/spools' &&
            typeof window.openAddModalFromAmsDetection === 'function') {
            close();
            window.openAddModalFromAmsDetection(detection);
            return;
        }

        if (typeof window.persistPendingAmsCreatePrefill === 'function') {
            window.persistPendingAmsCreatePrefill(detection);
        } else {
            try {
                localStorage.setItem(PENDING_AMS_CREATE_STORAGE_KEY, JSON.stringify(detection));
            } catch (err) {
                console.error("[SpoolAssignmentDialog] Failed to persist AMS prefill:", err);
            }
        }

        window.location.assign('/spools?openAmsCreate=1');
    };

    // Export
    window.SpoolAssignmentDialog = {
        open,
        close,
        merge,
        createNew,
        _selectSpool,
        _filterSpools,
    };

    console.log("[SpoolAssignmentDialog] Ready");
})();
