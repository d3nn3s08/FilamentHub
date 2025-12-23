// === INIT ===
document.addEventListener('DOMContentLoaded', () => {
    console.log('[Materials] Page loaded');
    loadMaterials();
    setInterval(loadMaterials, 30000);
});

// === LOAD MATERIALS ===
async function loadMaterials() {
    console.log('[Materials] Loading materials...');
    try {
        const response = await fetch('/api/materials/');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const materials = await response.json();
        console.log('[Materials] Loaded:', materials.length);
        renderMaterialsTable(materials);
    } catch (error) {
        console.error('[Materials] Error:', error);
        renderError('Fehler beim Laden der Materialien');
    }
}

// === RENDER TABLE ===
function renderMaterialsTable(materials) {
    const tbody = document.getElementById('materialsTableBody');
    if (!materials || materials.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; padding: 20px; color: var(--text-dim);">Keine Materialien vorhanden</td></tr>';
        return;
    }

    tbody.innerHTML = materials.map(material => `
        <tr>
            <td><strong>${escapeHtml(material.name || '-')}</strong></td>
            <td>${escapeHtml(material.brand || '-')}</td>
            <td>${material.density ? material.density + ' g/cm³' : '-'}</td>
            <td>${material.diameter ? material.diameter + ' mm' : '-'}</td>
            <td>
                <div class="actions-inline">
                    <button class="btn-icon edit" onclick="editMaterial('${material.id}')" title="Bearbeiten">✏️</button>
                    <button class="btn-icon delete" onclick="deleteMaterial('${material.id}')" title="Löschen">🗑️</button>
                </div>
            </td>
        </tr>
    `).join('');

    console.log('[Materials] Table rendered');
}

// === ERROR DISPLAY ===
function renderError(message) {
    const tbody = document.getElementById('materialsTableBody');
    tbody.innerHTML = `<tr><td colspan="5" style="text-align: center; padding: 20px; color: var(--error);">${escapeHtml(message)}</td></tr>`;
}

// === EDIT ===
async function editMaterial(materialId) {
    console.log('[Materials] Edit material:', materialId);
    try {
        await loadBrands();
        const response = await fetch(`/api/materials/${materialId}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const material = await response.json();
        document.getElementById('editForm').dataset.materialId = material.id;
        document.getElementById('editName').value = material.name || '';
        document.getElementById('editBrand').value = material.brand || '';
        document.getElementById('editBrandInput').value = '';
        document.getElementById('editBrandInput').style.display = 'none';
        document.getElementById('editDensity').value = material.density || '';
        document.getElementById('editDiameter').value = material.diameter || '';
        document.getElementById('editNotes').value = material.notes || '';
        document.getElementById('editModal').classList.add('active');
    } catch (error) {
        console.error('[Materials] Error loading material:', error);
        alert('Fehler beim Laden des Materials: ' + error.message);
    }
}

// === LOAD BRANDS ===
async function loadBrands() {
    console.log('[Materials] Loading brands...');
    try {
        const response = await fetch('/api/materials/brands/list');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const brands = await response.json();
        const select = document.getElementById('editBrand');
        const currentValue = select.value;
        select.innerHTML = '';
        const noneOption = document.createElement('option');
        noneOption.value = '';
        noneOption.textContent = '-- Keine --';
        select.appendChild(noneOption);
        const newOption = document.createElement('option');
        newOption.value = '__new__';
        newOption.textContent = '+ Neue Marke...';
        select.appendChild(newOption);
        brands.forEach(brand => {
            const option = document.createElement('option');
            option.value = brand;
            option.textContent = brand;
            select.appendChild(option);
        });
        select.value = currentValue;
    } catch (error) {
        console.error('[Materials] Error loading brands:', error);
    }
}

// === CLOSE MODAL ===
function closeEditModal() {
    document.getElementById('editModal').classList.remove('active');
    document.getElementById('editForm').reset();
}

// === SAVE MATERIAL ===
async function saveMaterial(event) {
    event.preventDefault();
    const materialId = document.getElementById('editForm').dataset.materialId;
    console.log('[Materials] Saving material:', materialId);
    let brand = document.getElementById('editBrand').value;
    if (brand === '__new__') {
        brand = document.getElementById('editBrandInput').value || null;
    }
    const formData = {
        name: document.getElementById('editName').value,
        brand: brand,
        density: parseFloat(document.getElementById('editDensity').value) || 1.24,
        diameter: parseFloat(document.getElementById('editDiameter').value) || 1.75,
        notes: document.getElementById('editNotes').value || null
    };
    try {
        const response = await fetch(`/api/materials/${materialId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        closeEditModal();
        loadMaterials();
    } catch (error) {
        console.error('[Materials] Save error:', error);
        alert('Fehler beim Speichern: ' + error.message);
    }
}

// === TOGGLE EDIT BRAND INPUT ===
function toggleEditBrandInput() {
    const select = document.getElementById('editBrand');
    const input = document.getElementById('editBrandInput');
    if (select.value === '__new__') {
        input.style.display = 'block';
        input.focus();
    } else {
        input.style.display = 'none';
        input.value = '';
    }
}

// === OPEN CREATE MODAL ===
async function openCreateModal() {
    console.log('[Materials] Open create modal');
    try {
        await loadBrandsForCreate();
        document.getElementById('createForm').reset();
        document.getElementById('createDensity').value = '1.24';
        document.getElementById('createDiameter').value = '1.75';
        document.getElementById('createModal').classList.add('active');
    } catch (error) {
        console.error('[Materials] Error opening create modal:', error);
    }
}

// === CLOSE CREATE MODAL ===
function closeCreateModal() {
    document.getElementById('createModal').classList.remove('active');
    document.getElementById('createForm').reset();
}

// === LOAD BRANDS FOR CREATE ===
async function loadBrandsForCreate() {
    console.log('[Materials] Loading brands for create...');
    try {
        const response = await fetch('/api/materials/brands/list');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const brands = await response.json();
        const select = document.getElementById('createBrand');
        select.innerHTML = '';
        const noneOption = document.createElement('option');
        noneOption.value = '';
        noneOption.textContent = '-- Keine --';
        select.appendChild(noneOption);
        const newOption = document.createElement('option');
        newOption.value = '__new__';
        newOption.textContent = '+ Neue Marke...';
        select.appendChild(newOption);
        brands.forEach(brand => {
            const option = document.createElement('option');
            option.value = brand;
            option.textContent = brand;
            select.appendChild(option);
        });
    } catch (error) {
        console.error('[Materials] Error loading brands for create:', error);
    }
}

// === CREATE MATERIAL ===
async function createMaterial(event) {
    event.preventDefault();
    console.log('[Materials] Creating material');
    let brand = document.getElementById('createBrand').value;
    if (brand === '__new__') {
        brand = document.getElementById('createBrandInput').value || null;
    }
    const formData = {
        name: document.getElementById('createName').value,
        brand: brand,
        density: parseFloat(document.getElementById('createDensity').value) || 1.24,
        diameter: parseFloat(document.getElementById('createDiameter').value) || 1.75,
        notes: document.getElementById('createNotes').value || null
    };
    try {
        const response = await fetch('/api/materials/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        closeCreateModal();
        loadMaterials();
    } catch (error) {
        console.error('[Materials] Create error:', error);
        alert('Fehler beim Erstellen: ' + error.message);
    }
}

// === TOGGLE CREATE BRAND INPUT ===
function toggleCreateBrandInput() {
    const select = document.getElementById('createBrand');
    const input = document.getElementById('createBrandInput');
    if (select.value === '__new__') {
        input.style.display = 'block';
        input.focus();
    } else {
        input.style.display = 'none';
        input.value = '';
    }
}

// === DELETE ===
async function deleteMaterial(materialId) {
    console.log('[Materials] Delete material:', materialId);
    if (!confirm('Material wirklich löschen?')) {
        return;
    }
    try {
        const response = await fetch(`/api/materials/${materialId}`, {
            method: 'DELETE'
        });
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        loadMaterials();
    } catch (error) {
        console.error('[Materials] Delete error:', error);
        alert('Fehler beim Löschen: ' + error.message);
    }
}

// === UTILS ===
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>'"]/g, m => map[m]);
}
