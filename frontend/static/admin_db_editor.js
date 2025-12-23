// Admin DB Editor (SQL) + Tables Overview (simpel)
document.addEventListener('DOMContentLoaded', () => {
    const queryInput = document.getElementById('dbEditorQuery');
    const outputBox = document.getElementById('dbEditorOutput');
    const executeBtn = document.getElementById('dbEditorExecute');
    const clearBtn = document.getElementById('dbEditorClear');
    const overviewBox = document.getElementById('dbTables');
    const exampleButtons = document.querySelectorAll('[data-sql-example]');

    // SQL-Editor
    if (queryInput && outputBox && executeBtn && clearBtn) {
        executeBtn.onclick = async () => {
            const sql = queryInput.value.trim();
            if (!sql) return;
            outputBox.textContent = 'Wird ausgeführt...';
            try {
                const res = await fetch('/api/debug/db/exec', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ sql })
                });
                const data = await res.json();
                outputBox.textContent = data.success ? (data.output || 'OK') : (data.error || 'Fehler');
            } catch (e) {
                outputBox.textContent = 'Fehler beim Ausführen!';
            }
        };
        clearBtn.onclick = () => {
            queryInput.value = '';
            outputBox.textContent = '';
        };
    }

    if (queryInput && exampleButtons.length) {
        const SQL_EXAMPLES = {
            update: "UPDATE material SET notes = 'Beispieltext' WHERE id = 'INSERT_UUID_HERE';",
            insert: "INSERT INTO material (name, brand, density, diameter) VALUES ('Mustermaterial', 'Demo', 1.24, 1.75);",
            delete: "DELETE FROM material WHERE id = 'INSERT_UUID_HERE';"
        };
        exampleButtons.forEach(btn => {
            const key = btn.dataset.sqlExample;
            btn.addEventListener('click', () => {
                if (!key) return;
                queryInput.value = SQL_EXAMPLES[key] || '';
                queryInput.focus();
            });
        });
    }

    // Tables Overview
    if (overviewBox) {
        loadTablesOverview(overviewBox);
    }
});

async function loadTablesOverview(box) {
    const renderError = (msg) => {
        box.innerHTML = `<div style="color:var(--danger);padding:8px;">${msg}</div>`;
    };
    try {
        const res = await fetch('/api/database/tables');
        const data = await res.json();
        const tables = data.tables || [];
        if (!tables.length) {
            box.innerHTML = '<div style="color:var(--text-dim);padding:8px;">Keine Tabellen gefunden.</div>';
            return;
        }
        const cards = tables.map(renderTableCard).join('');
        box.innerHTML = `<div class="table-list">${cards}</div>`;
    } catch (e) {
        renderError('Fehler beim Laden der Tabellenübersicht!');
    }
}

function renderTableCard(t) {
    const cols = (t.columns || []).map(col => `
        <span class="column-pill">
            ${col.name} <span class="type">(${col.type})</span>
            ${col.primary_key ? '<span class="pk-pill">PK</span>' : ''}
        </span>
    `).join('');
    const rowCount = t.row_count ?? 0;
    const colCount = t.column_count ?? (t.columns ? t.columns.length : 0);
    const previewHtml = renderPreviewTable(t.preview);
    return `
        <div class="table-card">
            <div class="table-header">
                <div style="text-transform: lowercase;">${t.name}</div>
                <div class="table-meta">${rowCount} Zeilen • ${colCount} Spalten</div>
            </div>
            <div class="column-pills">${cols}</div>
            ${previewHtml}
        </div>
    `;
}

function renderPreviewTable(preview) {
    if (!preview || !Array.isArray(preview.headers) || !Array.isArray(preview.rows) || preview.rows.length === 0) {
        return '<div class="preview-block"><div class="preview-title" style="color:var(--text-dim);">Keine Einträge</div></div>';
    }
    const headers = preview.headers;
    const rows = preview.rows.slice(0, 5);
    const totalRows = preview.rows.length;
    const more = totalRows > 5 ? `<div class="preview-more">… ${totalRows - 5} weitere Zeilen</div>` : '';
    
    const tableRows = rows.map(r => {
        const cells = headers.map((_, idx) => {
            const value = r[idx];
            // Wandle Werte in lesbares Format um
            let display = value;
            if (value === null || value === undefined) {
                display = '<span style="color:var(--text-dim);">null</span>';
            } else if (typeof value === 'object') {
                display = JSON.stringify(value).substring(0, 50);
            } else {
                display = String(value).substring(0, 100);
            }
            return `<td title="${display}">${display}</td>`;
        }).join('');
        return `<tr>${cells}</tr>`;
    }).join('');
    
    return `
        <div class="preview-block">
            <div class="preview-title">Preview (${totalRows} Zeilen)</div>
            <div class="preview-table-wrapper">
                <table class="preview-table">
                    <thead>
                        <tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr>
                    </thead>
                    <tbody>
                        ${tableRows}
                    </tbody>
                </table>
            </div>
            ${more}
        </div>
    `;
}
