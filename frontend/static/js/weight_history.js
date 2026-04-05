/**
 * Weight History Page - Complete React Port
 *
 * Features:
 * - Spulen-Grid mit Selektion
 * - Weight History Timeline mit Filtern
 * - Archiv-Support für alte Spulen
 */

(function() {
    console.log("[WeightHistory] Initializing...");

    // State
    let allSpools = [];
    let selectedSpoolNumber = null;
    let selectedSpoolUUID = null;
    let allHistory = {};
    let currentFilter = 'all';
    let showArchive = false;
    let archivedSpools = [];
    let expandedEntries = new Set();

    // Source Config (Icons als Text-Emojis weil wir keine React-Icons haben)
    const sourceConfig = {
        'bambu_cloud': {
            icon: '☁️',
            color: '#4a9eff',
            bg: 'rgba(74, 158, 255, 0.15)',
            label: 'Bambu Cloud'
        },
        'filamenthub_manual': {
            icon: '💾',
            color: '#ff6b35',
            bg: 'rgba(255, 107, 53, 0.15)',
            label: 'Manual'
        },
        'ams_rfid': {
            icon: '📡',
            color: '#a78bfa',
            bg: 'rgba(167, 139, 250, 0.15)',
            label: 'RFID'
        },
        'print_consumed': {
            icon: '🖨️',
            color: '#10b981',
            bg: 'rgba(16, 185, 129, 0.15)',
            label: 'Print'
        },
        'conflict_resolution': {
            icon: '⚖️',
            color: '#f59e0b',
            bg: 'rgba(245, 158, 11, 0.15)',
            label: 'Konflikt'
        }
    };

    // Format helper: max 3 decimals, trim trailing zeros
    function formatNumber(n) {
        if (n === null || n === undefined || Number.isNaN(n)) return '0';
        const fixed = Number(n).toFixed(3);
        return fixed.replace(/\.0+$|(?<=\.[0-9]*?)0+$/g, '').replace(/\.$/, '');
    }
    // Initialize
    async function init() {
        await loadAllSpools();
        renderGrid();
        setupSearch();

        // Auto-select first spool (use tray_uuid when available, fallback to id)
        if (allSpools.length > 0) {
            const first = allSpools[0];
            const uuid = first.tray_uuid || first.id;
            selectSpool(first.spool_number, uuid);
        }
    }

    // Load all active spools
    async function loadAllSpools() {
        try {
            const response = await fetch('/api/spools');
            if (!response.ok) throw new Error('Failed to load spools');

            const data = await response.json();

            console.log(`[WeightHistory] Raw API returned ${data.length} spools`);
            if (data.length > 0) {
                console.log(`[WeightHistory] First spool example:`, data[0]);
            }

            // Filter nur Spulen mit Nummer (API gibt is_active nicht zurück)
            allSpools = data
                .filter(s => s.spool_number !== null && s.spool_number !== undefined)
                .sort((a, b) => a.spool_number - b.spool_number);

            console.log(`[WeightHistory] After filtering: ${allSpools.length} spools`);

        } catch (error) {
            console.error("[WeightHistory] Failed to load spools:", error);
        }
    }

    // Render Spulen-Grid
    function renderGrid() {
        const grid = document.getElementById('spools-grid');
        if (!grid) {
            console.error("[WeightHistory] Grid container not found!");
            return;
        }

        console.log(`[WeightHistory] Rendering ${allSpools.length} spools in grid`);

        grid.innerHTML = allSpools.map(spool => {
            // API gibt remaining_weight_g zurück, nicht weight_current
            const currentWeight = spool.remaining_weight_g || spool.weight_current || 0;
            const status = currentWeight < 200 ? 'low' : 'active';
            const isSelected = spool.spool_number === selectedSpoolNumber;

            // Use tray_uuid if present (history endpoints are keyed by tray_uuid)
            const uuid = spool.tray_uuid || spool.id;

            return `
                <div
                    class="spool-tile ${isSelected ? 'selected' : ''}"
                    data-spool-number="${spool.spool_number}"
                    data-spool-uuid="${uuid}"
                    data-color="${spool.color || ''}"
                    data-vendor="${spool.vendor || ''}"
                    data-weight="${currentWeight}"
                    onclick="window.WeightHistory.selectSpool(${spool.spool_number}, '${uuid}')"
                    onmouseenter="window.WeightHistory.showTooltip(this)"
                    onmouseleave="window.WeightHistory.hideTooltip(this)"
                >
                    <div class="status-dot ${status}"></div>
                    <div class="spool-number">${spool.spool_number}</div>
                </div>
            `;
        }).join('');
    }

    // Show tooltip on hover
    function showTooltip(tile) {
        const color = tile.dataset.color;
        const vendor = tile.dataset.vendor;
        const weight = tile.dataset.weight;

        // Get tile position
        const rect = tile.getBoundingClientRect();

        const tooltip = document.createElement('div');
        tooltip.className = 'spool-tooltip';
        tooltip.innerHTML = `
            <div class="tooltip-title">${color || 'Unbekannt'}</div>
            <div class="tooltip-info">${weight}g • ${vendor || ''}</div>
        `;

        // Append to body instead of tile
        document.body.appendChild(tooltip);

        // Position below the tile
        const tooltipRect = tooltip.getBoundingClientRect();
        tooltip.style.left = `${rect.left + (rect.width / 2) - (tooltipRect.width / 2)}px`;
        tooltip.style.top = `${rect.bottom + 8}px`;

        // Store reference for cleanup
        tile._tooltip = tooltip;
    }

    function hideTooltip(tile) {
        // Remove tooltip from body
        if (tile._tooltip) {
            tile._tooltip.remove();
            tile._tooltip = null;
        }
    }

    // Select spool
    async function selectSpool(spoolNumber, spoolUUID) {
        selectedSpoolNumber = spoolNumber;
        selectedSpoolUUID = spoolUUID;
        showArchive = false; // Reset archive mode

        // Update grid selection
        document.querySelectorAll('.spool-tile').forEach(tile => {
            tile.classList.toggle('selected', parseInt(tile.dataset.spoolNumber) === spoolNumber);
        });

        // Load history
        await loadHistory(spoolUUID);

        // Update header
        updateHeader();

        // Render timeline
        renderTimeline();

        // Render filters
        renderFilters();
    }

    // Load history for spool
    async function loadHistory(spoolUUID) {
        try {
            const response = await fetch(`/api/weight/spools/${spoolUUID}/history`);
            if (!response.ok) throw new Error('Failed to load history');

            const history = await response.json();
            allHistory[spoolUUID] = history;

            console.log(`[WeightHistory] Loaded ${history.length} history entries for ${spoolUUID}`);

        } catch (error) {
            console.error("[WeightHistory] Failed to load history:", error);
            allHistory[spoolUUID] = [];
        }
    }

    // Update header with current spool info
    function updateHeader() {
        const spool = allSpools.find(s => s.spool_number === selectedSpoolNumber);
        if (!spool) return;

        const subtitle = document.getElementById('history-subtitle');
        const weightDisplay = document.getElementById('current-weight-display');

        // API gibt remaining_weight_g zurück
        const currentWeight = spool.remaining_weight_g || spool.weight_current || 0;

        subtitle.textContent = `Spule #${spool.spool_number} - ${spool.color || 'Unbekannt'}`;
        weightDisplay.textContent = `${Math.round(currentWeight)}g`;
    }

    // Render filter buttons
    function renderFilters() {
        const filterContainer = document.getElementById('filter-buttons');
        const currentHistory = allHistory[selectedSpoolUUID] || [];

        // Count per source
        const counts = {
            all: currentHistory.length,
            bambu_cloud: currentHistory.filter(h => h.source === 'bambu_cloud').length,
            filamenthub_manual: currentHistory.filter(h => h.source === 'filamenthub_manual').length,
            ams_rfid: currentHistory.filter(h => h.source === 'ams_rfid').length,
            print_consumed: currentHistory.filter(h => h.source === 'print_consumed').length,
        };

        const buttons = [];

        // All button
        buttons.push(`
            <button
                class="filter-btn ${currentFilter === 'all' && !showArchive ? 'active' : ''}"
                onclick="window.WeightHistory.setFilter('all')"
            >
                Alle (${counts.all})
            </button>
        `);

        // Source buttons
        Object.keys(sourceConfig).forEach(source => {
            const count = counts[source] || 0;
            if (count === 0) return;

            const config = sourceConfig[source];
            buttons.push(`
                <button
                    class="filter-btn source-${source} ${currentFilter === source && !showArchive ? 'active' : ''}"
                    onclick="window.WeightHistory.setFilter('${source}')"
                >
                    ${config.icon} ${config.label} (${count})
                </button>
            `);
        });

        // Archive button (TODO: implement archive loading)
        // buttons.push(`...`);

        filterContainer.innerHTML = buttons.join('');
    }

    // Set filter
    function setFilter(filter) {
        currentFilter = filter;
        showArchive = false;
        renderFilters();
        renderTimeline();
    }

    // Render timeline
    function renderTimeline() {
        const timeline = document.getElementById('history-timeline');
        const emptyState = document.getElementById('empty-state');

        const currentHistory = allHistory[selectedSpoolUUID] || [];

        // Filter
        const filteredHistory = currentFilter === 'all'
            ? currentHistory
            : currentHistory.filter(h => h.source === currentFilter);

        if (filteredHistory.length === 0) {
            timeline.style.display = 'none';
            emptyState.style.display = 'flex';
            return;
        }

        timeline.style.display = 'flex';
        emptyState.style.display = 'none';

        timeline.innerHTML = filteredHistory.map(entry => renderEntry(entry)).join('');
    }

    // Render single entry
    function renderEntry(entry) {
        const config = sourceConfig[entry.source] || sourceConfig['filamenthub_manual'];
        const timestamp = new Date(entry.timestamp).toLocaleString('de-DE');
        const diff = entry.new_weight - entry.old_weight;
        const diffFormatted = (diff >= 0 ? '+' : '') + formatNumber(diff) + 'g';
        const diffClass = diff >= 0 ? 'positive' : 'negative';
        const isExpanded = expandedEntries.has(entry.id);

        return `
            <div class="timeline-entry">
                <div class="entry-main ${isExpanded ? 'expanded' : ''}" onclick="window.WeightHistory.toggleEntry(${entry.id})">
                    <!-- Left: Icon + Time -->
                    <div class="entry-left">
                        <div class="source-icon-box ${entry.source}">
                            ${config.icon}
                        </div>
                        <div>
                            <div class="entry-time">${timestamp}</div>
                            <div class="entry-source-label">
                                ${config.label}${entry.ams_type ? ' • ' + entry.ams_type : ''}
                            </div>
                        </div>
                    </div>

                    <!-- Center: Weight Change -->
                    <div class="entry-center">
                        <div class="weight-display">
                            <div class="weight-value">${formatNumber(entry.old_weight)}g</div>
                            <div class="weight-label">Alt</div>
                        </div>

                        <div class="delta-badge ${diffClass}">
                            ${diff >= 0 ? '📈' : '📉'} ${diffFormatted}
                        </div>

                        <div class="weight-display">
                            <div class="weight-value">${formatNumber(entry.new_weight)}g</div>
                            <div class="weight-label">Neu</div>
                        </div>
                    </div>

                    <!-- Right: Chevron -->
                    <div class="entry-chevron">
                        ${isExpanded ? '▲' : '▼'}
                    </div>
                </div>

                ${isExpanded ? renderEntryDetails(entry) : ''}
            </div>
        `;
    }

    // Render entry details (expanded)
    function renderEntryDetails(entry) {
        return `
            <div class="entry-details">
                <div class="detail-item">
                    <div class="detail-label">Änderungsgrund</div>
                    <div class="detail-value">${(entry.change_reason || 'N/A').replace(/_/g, ' ')}</div>
                </div>

                <div class="detail-item">
                    <div class="detail-label">Benutzer</div>
                    <div class="detail-value">${entry.user || 'System'}</div>
                </div>

                ${entry.details ? `
                    <div class="detail-item full-width">
                        <div class="detail-label">Details</div>
                        <div class="detail-value-box">${entry.details}</div>
                    </div>
                ` : ''}
            </div>
        `;
    }

    // Toggle entry expansion
    function toggleEntry(entryId) {
        if (expandedEntries.has(entryId)) {
            expandedEntries.delete(entryId);
        } else {
            expandedEntries.add(entryId);
        }
        renderTimeline();
    }

    // Setup search
    function setupSearch() {
        const search = document.getElementById('spool-search');
        if (!search) return;

        search.addEventListener('input', (e) => {
            const term = e.target.value.toLowerCase();

            document.querySelectorAll('.spool-tile').forEach(tile => {
                const number = tile.dataset.spoolNumber;
                const color = tile.dataset.color.toLowerCase();
                const vendor = tile.dataset.vendor.toLowerCase();

                const matches = number.includes(term) ||
                                color.includes(term) ||
                                vendor.includes(term);

                tile.style.display = matches ? 'flex' : 'none';
            });
        });
    }

    // Export API
    window.WeightHistory = {
        selectSpool,
        showTooltip,
        hideTooltip,
        setFilter,
        toggleEntry
    };

    // Initialize on load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    console.log("[WeightHistory] Ready");
})();
