// Materials Management JavaScript

let materials = [];
let currentMaterialId = null;
let deleteTargetId = null;

// === INIT ===
document.addEventListener('DOMContentLoaded', () => {
    loadMaterials();
    setupEventListeners();
});

function setupEventListeners() {
    // Search
    document.getElementById('searchInput').addEventListener('input', filterMaterials);
    
    // Brand filter
    document.getElementById('filterBrand').addEventListener('change', filterMaterials);
    
    // Color picker sync
    const colorPicker = document.getElementById('materialColorPicker');
    const colorInput = document.getElementById('materialColor');
    
    colorPicker.addEventListener('input', (e) => {
        colorInput.value = e.target.value;
    });
    
    colorInput.addEventListener('input', (e) => {
        if (/^#[0-9A-Fa-f]{6}$/.test(e.target.value)) {
            colorPicker.value = e.target.value;
        }
    });
}

// === LOAD MATERIALS ===
async function loadMaterials() {
    try {
        const response = await fetch('/api/materials/');
        materials = await response.json();
        
        updateBrandFilter();
        renderMaterials(materials);
        
    } catch (error) {
        console.error('Fehler beim Laden der Materialien:', error);
        showNotification('Fehler beim Laden der Materialien', 'error');
    }
}

function updateBrandFilter() {
    const brands = [...new Set(materials.map(m => m.brand).filter(b => b))];
    const select = document.getElementById('filterBrand');
    
    // Keep "Alle Marken" option
    select.innerHTML = '<option value="">Alle Marken</option>';
    
    brands.sort().forEach(brand => {
        const option = document.createElement('option');
        option.value = brand;
        option.textContent = brand;
        select.appendChild(option);
    });
}

function renderMaterials(materialsToRender) {
    const container = document.getElementById('materialsTable');
    document.getElementById('materialCount').textContent = materialsToRender.length;
    
    if (materialsToRender.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📦</div>
                <h3>Keine Materialien gefunden</h3>
                <p>Fügen Sie Ihr erstes Material hinzu!</p>
                <button class="btn btn-primary" onclick="openAddModal()">
                    ➕ Material hinzufügen
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
                        <th>Name</th>
                        <th>Marke</th>
                        <th>Farbe</th>
                        <th>Dichte</th>
                        <th>Durchmesser</th>
                        <th>Aktionen</th>
                    </tr>
                </thead>
                <tbody>
                    ${materialsToRender.map(m => `
                        <tr>
                            <td><strong>${m.name}</strong></td>
                            <td>${m.brand || '-'}</td>
                            <td>
                                ${m.color ? `
                                    <span class="color-preview" style="background: ${m.color}"></span>
                                    ${m.color}
                                ` : '-'}
                            </td>
                            <td>${m.density} g/cm³</td>
                            <td>${m.diameter} mm</td>
                            <td>
                                <div class="table-actions">
                                    <button class="btn-icon" onclick="openEditModal('${m.id}')" title="Bearbeiten">
                                        ✏️
                                    </button>
                                    <button class="btn-icon btn-delete" onclick="openDeleteModal('${m.id}')" title="Löschen">
                                        🗑️
                                    </button>
                                </div>
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

// === FILTER ===
function filterMaterials() {
    const searchTerm = document.getElementById('searchInput').value.toLowerCase();
    const brandFilter = document.getElementById('filterBrand').value;
    
    let filtered = materials;
    
    // Search filter
    if (searchTerm) {
        filtered = filtered.filter(m => 
            m.name.toLowerCase().includes(searchTerm) ||
            (m.brand && m.brand.toLowerCase().includes(searchTerm)) ||
            (m.notes && m.notes.toLowerCase().includes(searchTerm))
        );
    }
    
    // Brand filter
    if (brandFilter) {
        filtered = filtered.filter(m => m.brand === brandFilter);
    }
    
    renderMaterials(filtered);
}

function clearFilters() {
    document.getElementById('searchInput').value = '';
    document.getElementById('filterBrand').value = '';
    renderMaterials(materials);
}

// === MODAL MANAGEMENT ===
function openAddModal() {
    currentMaterialId = null;
    document.getElementById('modalTitle').textContent = '➕ Material hinzufügen';
    document.getElementById('materialForm').reset();
    document.getElementById('materialId').value = '';
    document.getElementById('materialDensity').value = '1.24';
    document.getElementById('materialDiameter').value = '1.75';
    document.getElementById('materialModal').classList.add('active');
}

function openEditModal(id) {
    const material = materials.find(m => m.id === id);
    if (!material) return;
    
    currentMaterialId = id;
    document.getElementById('modalTitle').textContent = '✏️ Material bearbeiten';
    
    document.getElementById('materialId').value = material.id;
    document.getElementById('materialName').value = material.name;
    document.getElementById('materialBrand').value = material.brand || '';
    document.getElementById('materialColor').value = material.color || '';
    document.getElementById('materialColorPicker').value = material.color || '#000000';
    document.getElementById('materialDensity').value = material.density;
    document.getElementById('materialDiameter').value = material.diameter;
    document.getElementById('materialNotes').value = material.notes || '';
    
    document.getElementById('materialModal').classList.add('active');
}

function closeModal() {
    document.getElementById('materialModal').classList.remove('active');
    currentMaterialId = null;
}

function openDeleteModal(id) {
    deleteTargetId = id;
    document.getElementById('deleteModal').classList.add('active');
}

function closeDeleteModal() {
    document.getElementById('deleteModal').classList.remove('active');
    deleteTargetId = null;
}

// === SAVE MATERIAL ===
async function saveMaterial(event) {
    event.preventDefault();
    
    const data = {
        name: document.getElementById('materialName').value,
        brand: document.getElementById('materialBrand').value || null,
        color: document.getElementById('materialColor').value || null,
        density: parseFloat(document.getElementById('materialDensity').value),
        diameter: parseFloat(document.getElementById('materialDiameter').value),
        notes: document.getElementById('materialNotes').value || null
    };
    
    try {
        let response;
        
        if (currentMaterialId) {
            // Update existing
            response = await fetch(`/api/materials/${currentMaterialId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        } else {
            // Create new
            response = await fetch('/api/materials/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
        }
        
        if (response.ok) {
            showNotification(
                currentMaterialId ? 'Material aktualisiert!' : 'Material erstellt!', 
                'success'
            );
            closeModal();
            clearFilters(); // Reset filters
            await loadMaterials();
        } else {
            throw new Error('Speichern fehlgeschlagen');
        }
        
    } catch (error) {
        console.error('Fehler beim Speichern:', error);
        showNotification('Fehler beim Speichern', 'error');
    }
}

// === DELETE MATERIAL ===
async function confirmDelete() {
    if (!deleteTargetId) return;
    
    try {
        const response = await fetch(`/api/materials/${deleteTargetId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            showNotification('Material gelöscht', 'success');
            closeDeleteModal();
            clearFilters(); // Reset filters
            await loadMaterials();
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
document.getElementById('materialModal').addEventListener('click', (e) => {
    if (e.target.id === 'materialModal') closeModal();
});

document.getElementById('deleteModal').addEventListener('click', (e) => {
    if (e.target.id === 'deleteModal') closeDeleteModal();
});
