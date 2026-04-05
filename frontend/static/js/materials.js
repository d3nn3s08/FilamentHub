// === INIT ===
document.addEventListener('DOMContentLoaded', () => {
    console.log('[Materials] Page loaded');
    loadMaterials();
    setInterval(loadMaterials, 30000);

    // Search
    document.getElementById('matSearchInput').addEventListener('input', function() {
        const query = this.value.toLowerCase().trim();
        document.querySelectorAll('.mcard').forEach(card => {
            const name = (card.dataset.name || '').toLowerCase();
            const brand = (card.dataset.brand || '').toLowerCase();
            card.style.display = (!query || name.includes(query) || brand.includes(query)) ? '' : 'none';
        });
    });
});

// === LOAD MATERIALS ===
async function loadMaterials() {
    console.log('[Materials] Loading materials...');
    try {
        const response = await fetch('/api/materials/');
        if (!response.ok) throw new Error('HTTP ' + response.status);
        const materials = await response.json();
        console.log('[Materials] Loaded:', materials.length, 'materials');
        renderMaterialCards(materials);
    } catch (error) {
        console.error('[Materials] Error:', error);
        document.getElementById('matCardGrid').innerHTML =
            '<div class="mat-loading" style="color:var(--error)">Fehler beim Laden der Materialien</div>';
    }
}

// === RENDER CARDS ===
function renderMaterialCards(materials) {
    const grid = document.getElementById('matCardGrid');
    const empty = document.getElementById('matEmptyState');
    document.getElementById('matCount').textContent = materials.length;

    if (!materials || materials.length === 0) {
        grid.innerHTML = '';
        grid.style.display = 'none';
        empty.style.display = 'block';
        return;
    }
    grid.style.display = 'grid';
    empty.style.display = 'none';

    grid.innerHTML = materials.map(m => {
        const abbr = (m.name || '??').slice(0, 2).toUpperCase();
        const tags = [];
        if (m.is_bambu) tags.push('<span class="mcard__tag mcard__tag--bambu">Bambu Lab</span>');
        if (m.notes) tags.push('<span class="mcard__tag mcard__tag--notes">&#128221; Notizen</span>');

        return '<div class="mcard" data-name="' + escapeHtml(m.name || '') + '" data-brand="' + escapeHtml(m.brand || '') + '">' +
            '<div class="mcard__header">' +
                '<div class="mcard__left">' +
                    '<div class="mcard__icon">' + escapeHtml(abbr) + '</div>' +
                    '<div>' +
                        '<div class="mcard__name">' + escapeHtml(m.name || '-') + '</div>' +
                        '<div class="mcard__brand">' + escapeHtml(m.brand || 'Kein Hersteller') + '</div>' +
                    '</div>' +
                '</div>' +
                '<div class="mcard__actions">' +
                    '<button class="mcard__btn" onclick="editMaterial(\'' + m.id + '\')" title="Bearbeiten">&#9998;</button>' +
                    '<button class="mcard__btn mcard__btn--delete" onclick="deleteMaterial(\'' + m.id + '\')" title="Loeschen">&#128465;</button>' +
                '</div>' +
            '</div>' +
            '<div class="mcard__stats">' +
                '<div class="mcard__stat">' +
                    '<span class="mcard__stat-icon" style="color:#f39c12">&#9878;</span>' +
                    '<span class="mcard__stat-label">Dichte:</span>' +
                    '<span class="mcard__stat-value">' + (m.density || '-') + ' g/cm&sup3;</span>' +
                '</div>' +
                '<div class="mcard__stat">' +
                    '<span class="mcard__stat-icon" style="color:#3b82f6">&#8960;</span>' +
                    '<span class="mcard__stat-label">Durchm.:</span>' +
                    '<span class="mcard__stat-value">' + (m.diameter || '-') + ' mm</span>' +
                '</div>' +
                '<div class="mcard__stat">' +
                    '<span class="mcard__stat-icon" style="color:#22c55e">&#9878;</span>' +
                    '<span class="mcard__stat-label">Leer:</span>' +
                    '<span class="mcard__stat-value">' + (m.spool_weight_empty != null ? m.spool_weight_empty + 'g' : '-') + '</span>' +
                '</div>' +
                '<div class="mcard__stat">' +
                    '<span class="mcard__stat-icon" style="color:#a855f7">&#9878;</span>' +
                    '<span class="mcard__stat-label">Voll:</span>' +
                    '<span class="mcard__stat-value">' + (m.spool_weight_full != null ? m.spool_weight_full + 'g' : '-') + '</span>' +
                '</div>' +
            '</div>' +
            (tags.length > 0 ? '<div class="mcard__tags">' + tags.join('') + '</div>' : '') +
        '</div>';
    }).join('');
}

// === EDIT ===
async function editMaterial(materialId) {
    console.log('[Materials] Edit material:', materialId);
    try {
        await loadBrands();
        const response = await fetch('/api/materials/' + materialId);
        if (!response.ok) throw new Error('HTTP ' + response.status);
        const material = await response.json();
        document.getElementById('editForm').dataset.materialId = material.id;
        document.getElementById('editName').value = material.name || '';
        document.getElementById('editBrand').value = material.brand || '';
        document.getElementById('editBrandInput').value = '';
        document.getElementById('editBrandInput').style.display = 'none';
        document.getElementById('editDensity').value = material.density || '';
        document.getElementById('editDiameter').value = material.diameter || '';
        document.getElementById('editSpoolWeightEmpty').value = material.spool_weight_empty != null ? material.spool_weight_empty : '';
        document.getElementById('editSpoolWeightFull').value = material.spool_weight_full != null ? material.spool_weight_full : '';
        document.getElementById('editNotes').value = material.notes || '';
        document.getElementById('editModal').classList.add('active');
    } catch (error) {
        console.error('[Materials] Error loading material:', error);
        alert('Fehler beim Laden des Materials: ' + error.message);
    }
}

// === LOAD BRANDS ===
async function loadBrands() {
    try {
        const response = await fetch('/api/materials/brands/list');
        if (!response.ok) throw new Error('HTTP ' + response.status);
        const brands = await response.json();
        populateBrandSelect('editBrand', brands);
    } catch (error) {
        console.error('[Materials] Error loading brands:', error);
    }
}

function populateBrandSelect(selectId, brands) {
    const select = document.getElementById(selectId);
    const currentValue = select.value;
    select.innerHTML = '<option value="">-- Keine --</option><option value="__new__">+ Neue Marke...</option>';
    brands.forEach(brand => {
        const option = document.createElement('option');
        option.value = brand;
        option.textContent = brand;
        select.appendChild(option);
    });
    select.value = currentValue;
}

// === CLOSE MODALS ===
function closeEditModal() {
    document.getElementById('editModal').classList.remove('active');
    document.getElementById('editForm').reset();
}
function closeCreateModal() {
    document.getElementById('createModal').classList.remove('active');
    document.getElementById('createForm').reset();
}

// === SAVE MATERIAL ===
async function saveMaterial(event) {
    event.preventDefault();
    const materialId = document.getElementById('editForm').dataset.materialId;
    const sweVal = document.getElementById('editSpoolWeightEmpty').value;
    const swfVal = document.getElementById('editSpoolWeightFull').value;
    let brand = document.getElementById('editBrand').value;
    if (brand === '__new__') brand = document.getElementById('editBrandInput').value || null;

    const formData = {
        name: document.getElementById('editName').value,
        brand: brand,
        density: parseFloat(document.getElementById('editDensity').value) || 1.24,
        diameter: parseFloat(document.getElementById('editDiameter').value) || 1.75,
        spool_weight_empty: sweVal === '' ? null : parseFloat(sweVal),
        spool_weight_full: swfVal === '' ? null : parseFloat(swfVal),
        notes: document.getElementById('editNotes').value || null
    };
    try {
        const response = await fetch('/api/materials/' + materialId, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'HTTP ' + response.status);
        }
        closeEditModal();
        loadMaterials();
    } catch (error) {
        console.error('[Materials] Save error:', error);
        alert('Fehler beim Speichern: ' + error.message);
    }
}

// === TOGGLE BRAND INPUTS ===
function toggleEditBrandInput() {
    const select = document.getElementById('editBrand');
    const input = document.getElementById('editBrandInput');
    if (select.value === '__new__') { input.style.display = 'block'; input.focus(); }
    else { input.style.display = 'none'; input.value = ''; }
}
function toggleCreateBrandInput() {
    const select = document.getElementById('createBrand');
    const input = document.getElementById('createBrandInput');
    if (select.value === '__new__') { input.style.display = 'block'; input.focus(); }
    else { input.style.display = 'none'; input.value = ''; }
}

// === OPEN CREATE MODAL ===
async function openCreateModal() {
    try {
        const response = await fetch('/api/materials/brands/list');
        if (response.ok) {
            const brands = await response.json();
            populateBrandSelect('createBrand', brands);
        }
    } catch (e) { /* ignore */ }
    document.getElementById('createForm').reset();
    document.getElementById('createDensity').value = '1.24';
    document.getElementById('createDiameter').value = '1.75';
    document.getElementById('createModal').classList.add('active');
}

// === CREATE MATERIAL ===
async function createMaterial(event) {
    event.preventDefault();
    const sweVal = document.getElementById('createSpoolWeightEmpty').value;
    const swfVal = document.getElementById('createSpoolWeightFull').value;
    let brand = document.getElementById('createBrand').value;
    if (brand === '__new__') brand = document.getElementById('createBrandInput').value || null;

    const formData = {
        name: document.getElementById('createName').value,
        brand: brand,
        density: parseFloat(document.getElementById('createDensity').value) || 1.24,
        diameter: parseFloat(document.getElementById('createDiameter').value) || 1.75,
        spool_weight_empty: sweVal === '' ? null : parseFloat(sweVal),
        spool_weight_full: swfVal === '' ? null : parseFloat(swfVal),
        notes: document.getElementById('createNotes').value || null
    };
    try {
        const response = await fetch('/api/materials/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'HTTP ' + response.status);
        }
        closeCreateModal();
        loadMaterials();
    } catch (error) {
        console.error('[Materials] Create error:', error);
        alert('Fehler beim Erstellen: ' + error.message);
    }
}

// === DELETE ===
async function deleteMaterial(materialId) {
    if (!confirm('Material wirklich loeschen?')) return;
    try {
        const response = await fetch('/api/materials/' + materialId, { method: 'DELETE' });
        if (!response.ok) throw new Error('HTTP ' + response.status);
        loadMaterials();
    } catch (error) {
        console.error('[Materials] Delete error:', error);
        alert('Fehler beim Loeschen: ' + error.message);
    }
}

// === UTILS ===
function escapeHtml(text) {
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return String(text).replace(/[&<>'"]/g, m => map[m]);
}
