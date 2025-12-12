// Spools Management JavaScript

let spools = [];
let materials = [];
let currentSpoolId = null;
let deleteTargetId = null;

function toNumber(val) {
    const n = parseFloat(val);
    return isNaN(n) ? null : n;
}

// === INIT ===
document.addEventListener('DOMContentLoaded', () => {
    loadData();
    setupEventListeners();
});

function setupEventListeners() {
    // Search
    document.getElementById('searchInput').addEventListener('input', filterSpools);
    
    // Filters
    document.getElementById('filterMaterial').addEventListener('change', filterSpools);
    document.getElementById('filterStatus').addEventListener('change', filterSpools);
}

// === LOAD DATA ===
async function loadData() {
    try {
        await Promise.all([
            loadMaterials(),
            loadSpools()
        ]);
    } catch (error) {
        console.error('Fehler beim Laden:', error);
    }
}

async function loadMaterials() {
    try {
        const response = await fetch('/api/materials/');
        materials = await response.json();
        updateMaterialSelects();
    } catch (error) {
        console.error('Fehler beim Laden der Materialien:', error);
    }
}

async function loadSpools() {
    try {
        const response = await fetch('/api/spools/');
        spools = await response.json();
        
        updateStats();
        renderSpools(spools);
        
    } catch (error) {
        console.error('Fehler beim Laden der Spulen:', error);
        showNotification('Fehler beim Laden der Spulen', 'error');
    }
}

function updateMaterialSelects() {
    const select = document.getElementById('spoolMaterial');
    const filter = document.getElementById('filterMaterial');
    
    // Form select
    select.innerHTML = '<option value="">-- Material wählen --</option>';
    materials.forEach(m => {
        const option = document.createElement('option');
        option.value = m.id;
        option.textContent = `${m.name}${m.brand ? ' (' + m.brand + ')' : ''}`;
        select.appendChild(option);
    });
    
    // Filter select
    filter.innerHTML = '<option value="">Alle Materialien</option>';
    materials.forEach(m => {
        const option = document.createElement('option');
        option.value = m.id;
        option.textContent = `${m.name}${m.brand ? ' (' + m.brand + ')' : ''}`;
        filter.appendChild(option);
    });
}

function updateStats() {
    const total = spools.length;
    const active = spools.filter(s => !s.is_empty).length;
    const empty = spools.filter(s => s.is_empty).length;
    const totalWeight = spools.reduce((sum, s) => {
        if (s.is_empty) return sum;
        const wf = toNumber(s.weight_full) || 0;
        const rp = toNumber(s.remain_percent);
        const remaining = (toNumber(s.weight) ?? toNumber(s.weight_current) ?? toNumber(s.weight_remaining) ?? (rp != null && wf ? (rp / 100) * wf : wf)) ?? 0;
        return sum + (remaining || 0);
    }, 0);
    
    document.getElementById('statTotal').textContent = total;
    document.getElementById('statActive').textContent = active;
    document.getElementById('statEmpty').textContent = empty;
    document.getElementById('statWeight').textContent = Math.round(totalWeight);
}

function renderSpools(spoolsToRender) {
    const container = document.getElementById('spoolsTable');
    document.getElementById('spoolCount').textContent = spoolsToRender.length;
    
    if (spoolsToRender.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">🧵</div>
                <h3>Keine Spulen gefunden</h3>
                <p>Fügen Sie Ihre erste Spule hinzu!</p>
                <button class="btn btn-primary" onclick="openAddModal()">
                    ➕ Spule hinzufügen
                </button>
            </div>
        `;
        return;
    }
    
    container.innerHTML = `
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Bezeichnung</th>
                        <th>Material</th>
                        <th>Restgewicht</th>
                        <th>Füllstand</th>
                        <th>AMS Slot</th>
                        <th>Status</th>
                        <th>Aktionen</th>
                    </tr>
                </thead>
                <tbody>
                    ${spoolsToRender.map(s => {
                        const material = materials.find(m => m.id === s.material_id);
                        const weightFull = toNumber(s.weight_full) ?? 0;
                        const remainPercent = toNumber(s.remain_percent);
                    const remaining = toNumber(s.weight) ?? toNumber(s.weight_current) ?? toNumber(s.weight_remaining) ?? ((remainPercent != null && weightFull) ? (remainPercent / 100) * weightFull : (weightFull || 0));
                    const percentage = (remainPercent != null)
                        ? Math.max(0, Math.min(100, remainPercent))
                        : (weightFull ? Math.max(0, Math.min(100, (remaining / weightFull) * 100)) : 0);
                    const displayName = s.label || `Spule #${s.id.substring(0, 8)}`;
                    const trayColor = s.tray_color ? `#${s.tray_color.substring(0, 6)}` : null;
                    const statusText = s.used_count && s.used_count > 0 ? 'Gebraucht' : 'Neu';
                    const statusBadgeExtra = s.used_count && s.used_count > 0 ? '<span class="status-badge status-secondary" style="margin-left:6px;">Gebraucht</span>' : '';
                    
                        let statusBadge = '';
                        let statusColor = '';

                        if (remainPercent === 0 || (remaining || 0) <= 0 || s.is_empty) {
                            statusBadge = '<span class="status-badge status-offline">Leer</span>';
                            statusColor = 'var(--error)';
                        } else if (s.used_count && s.used_count > 0) {
                            statusBadge = '<span class="status-badge status-secondary">Gebraucht</span>';
                            statusColor = 'var(--warning)';
                        } else if (remainPercent != null && remainPercent <= 20) {
                            statusBadge = '<span class="status-badge" style="background: rgba(255, 167, 38, 0.2); color: var(--warning);">Fast leer</span>';
                            statusColor = 'var(--warning)';
                        } else if (remaining < 200) {
                            statusBadge = '<span class="status-badge" style="background: rgba(255, 167, 38, 0.2); color: var(--warning);">Wenig</span>';
                            statusColor = 'var(--warning)';
                        } else if (s.is_open) {
                            statusBadge = '<span class="status-badge status-printing">Offen</span>';
                            statusColor = 'var(--accent)';
                        } else {
                            statusBadge = '<span class="status-badge status-online">Neu</span>';
                            statusColor = 'var(--success)';
                        }

                    return `
                            <tr>
                                <td>
                                    <strong>${displayName}</strong>
                                    ${s.manufacturer_spool_id ? `<br><small style="color: var(--text-dim);">RFID: ${s.manufacturer_spool_id}</small>` : ''}
                                </td>
                                <td>
                                    ${material ? `
                                        <div style="display: flex; align-items: center; gap: 8px;">
                                            ${trayColor ? `<span class="color-preview" style="background: ${trayColor}; width: 20px; height: 20px;"></span>` : (material.color ? `<span class="color-preview" style="background: ${material.color}; width: 20px; height: 20px;"></span>` : '')}
                                            <div>
                                                <strong>${material.name}</strong>
                                                ${material.brand ? `<br><small style="color: var(--text-dim);">${material.brand}</small>` : ''}
                                            </div>
                                        </div>
                                    ` : '<span style="color: var(--error);">Unbekannt</span>'}
                                </td>
                                <td>
                                    <strong>${Math.round(remaining || 0)}g</strong>
                                    <small style="color: var(--text-dim);"> / ${weightFull}g</small>
                                </td>
                                <td style="min-width: 150px;">
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${percentage}%; 
                                     background: ${statusColor || 'var(--accent)'}"></div>
                            </div>
                            <small style="color: var(--text-dim);">${Math.round(percentage)}%</small>
                        </td>
                        <td>${s.ams_slot ?? '-'}</td>
                        <td>${statusBadge}${statusBadgeExtra}</td>
                        <td>
                            <div class="table-actions">
                                <button class="btn-icon" onclick="openEditModal('${s.id}')" title="Bearbeiten">
                                    ✏️
                                </button>
                                        <button class="btn-icon btn-delete" onclick="openDeleteModal('${s.id}')" title="Löschen">
                                            🗑️
                                        </button>
                                    </div>
                                </td>
                            </tr>
                        `;
                    }).join('')}
                </tbody>
            </table>
        </div>
    `;
}

// === FILTER ===
function filterSpools() {
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    const materialFilter = document.getElementById('filterMaterial').value;
    const statusFilter = document.getElementById('filterStatus').value;
    
    let filtered = spools;
    
    // Search filter
    if (searchTerm) {
        filtered = filtered.filter(s => {
            const material = materials.find(m => m.id === s.material_id);
            return (s.label && s.label.toLowerCase().includes(searchTerm)) ||
                   (material && material.name.toLowerCase().includes(searchTerm)) ||
                   (s.manufacturer_spool_id && s.manufacturer_spool_id.toLowerCase().includes(searchTerm));
        });
    }
    
    // Material filter
    if (materialFilter) {
        filtered = filtered.filter(s => s.material_id === materialFilter);
    }
    
    // Status filter
    if (statusFilter === 'active') {
        filtered = filtered.filter(s => !s.is_empty);
    } else if (statusFilter === 'empty') {
        filtered = filtered.filter(s => s.is_empty);
    } else if (statusFilter === 'low') {
        filtered = filtered.filter(s => {
            const wf = toNumber(s.weight_full) || 0;
            const rp = toNumber(s.remain_percent);
            const remaining = toNumber(s.weight) ?? toNumber(s.weight_current) ?? toNumber(s.weight_remaining) ?? (rp != null && wf ? (rp / 100) * wf : wf);
            return (rp === 0) || (!s.is_empty && (remaining || 0) < 200);
        });
    }
    
    renderSpools(filtered);
}

function clearFilters() {
    document.getElementById('searchInput').value = '';
    document.getElementById('filterMaterial').value = '';
    document.getElementById('filterStatus').value = '';
    renderSpools(spools);
}

// === MODAL MANAGEMENT ===
function openAddModal() {
    if (materials.length === 0) {
        showNotification('Bitte erst ein Material anlegen!', 'warning');
        setTimeout(() => window.location.href = '/materials', 2000);
        return;
    }
    
    currentSpoolId = null;
    document.getElementById('modalTitle').textContent = '➕ Spule hinzufügen';
    document.getElementById('spoolForm').reset();
    document.getElementById('spoolId').value = '';
    document.getElementById('spoolWeightFull').value = '1000';
    document.getElementById('spoolWeightEmpty').value = '250';
    document.getElementById('spoolIsOpen').checked = true;
    document.getElementById('spoolIsEmpty').checked = false;
    document.getElementById('spoolModal').classList.add('active');
}

function openEditModal(id) {
    const spool = spools.find(s => s.id === id);
    if (!spool) return;
    
    currentSpoolId = id;
    document.getElementById('modalTitle').textContent = '✏️ Spule bearbeiten';
    
    document.getElementById('spoolId').value = spool.id;
    document.getElementById('spoolMaterial').value = spool.material_id;
    document.getElementById('spoolLabel').value = spool.label || '';
    document.getElementById('spoolWeightFull').value = spool.weight_full;
    document.getElementById('spoolWeightEmpty').value = spool.weight_empty;
    document.getElementById('spoolWeightRemaining').value = (toNumber(spool.weight) ?? toNumber(spool.weight_current) ?? toNumber(spool.weight_remaining)) ?? '';
    document.getElementById('spoolManufacturerId').value = spool.manufacturer_spool_id || '';
    document.getElementById('spoolAmsSlot').value = spool.ams_slot || '';
    document.getElementById('spoolIsOpen').checked = spool.is_open;
    document.getElementById('spoolIsEmpty').checked = spool.is_empty;
    
    document.getElementById('spoolModal').classList.add('active');
}

function closeModal() {
    document.getElementById('spoolModal').classList.remove('active');
    currentSpoolId = null;
}

function openDeleteModal(id) {
    deleteTargetId = id;
    document.getElementById('deleteModal').classList.add('active');
}

function closeDeleteModal() {
    document.getElementById('deleteModal').classList.remove('active');
    deleteTargetId = null;
}

// === SAVE SPOOL ===
async function saveSpool(event) {
    event.preventDefault();
    
    const weightRemaining = document.getElementById('spoolWeightRemaining').value;
    const amsSlot = document.getElementById('spoolAmsSlot').value;
    
    const data = {
        material_id: document.getElementById('spoolMaterial').value,
        weight_full: parseFloat(document.getElementById('spoolWeightFull').value),
        weight_empty: parseFloat(document.getElementById('spoolWeightEmpty').value),
        weight_current: weightRemaining ? parseFloat(weightRemaining) : null,
        label: document.getElementById('spoolLabel').value || null,
        manufacturer_spool_id: document.getElementById('spoolManufacturerId').value || null,
        ams_slot: amsSlot ? parseInt(amsSlot) : null,
        is_open: document.getElementById('spoolIsOpen').checked,
        is_empty: document.getElementById('spoolIsEmpty').checked
    };
    
    try {
        let response;
        
        if (currentSpoolId) {
            // Update existing
            response = await fetch(`/api/spools/${currentSpoolId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        } else {
            // Create new
            response = await fetch('/api/spools/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        }
        
        if (response.ok) {
            showNotification(
                currentSpoolId ? 'Spule aktualisiert!' : 'Spule erstellt!', 
                'success'
            );
            closeModal();
            clearFilters();
            await loadSpools();
        } else {
            throw new Error('Speichern fehlgeschlagen');
        }
        
    } catch (error) {
        console.error('Fehler beim Speichern:', error);
        showNotification('Fehler beim Speichern', 'error');
    }
}

// === DELETE SPOOL ===
async function confirmDelete() {
    if (!deleteTargetId) return;
    
    try {
        const response = await fetch(`/api/spools/${deleteTargetId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showNotification('Spule gelöscht', 'success');
            closeDeleteModal();
            clearFilters();
            await loadSpools();
        } else {
            throw new Error('Löschen fehlgeschlagen');
        }
        
    } catch (error) {
        console.error('Fehler beim Löschen:', error);
        showNotification('Fehler beim Löschen', 'error');
    }
}

// Close modals on ESC key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeModal();
        closeDeleteModal();
    }
});

// Close modals on background click
document.getElementById('spoolModal').addEventListener('click', (e) => {
    if (e.target.id === 'spoolModal') closeModal();
});

document.getElementById('deleteModal').addEventListener('click', (e) => {
    if (e.target.id === 'deleteModal') closeDeleteModal();
});
