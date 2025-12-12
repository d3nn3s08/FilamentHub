const container = document.getElementById("cardsContainer");
const refreshBtn = document.getElementById("refreshBtn");

async function loadPrintersModern() {
    if (!container) return;
    container.innerHTML = '<div class="empty">Lade Drucker …</div>';
    try {
        const res = await fetch("/api/printers/");
        if (!res.ok) throw new Error("Request failed");
        const data = await res.json();
        if (!Array.isArray(data) || data.length === 0) {
            container.innerHTML = '<div class="empty">Keine Drucker konfiguriert.</div>';
            return;
        }
        container.innerHTML = data.map(renderCard).join("");
    } catch (err) {
        console.error(err);
        container.innerHTML = '<div class="empty">Fehler beim Laden der Drucker.</div>';
    }
}

function renderCard(printer) {
    const online = printer.online === true;
    const onlineLabel = online ? "Online" : printer.online === null ? "Manuell" : "Offline";
    const icon = printer.image_url
        ? `<img src="${printer.image_url}" alt="${printer.name || 'Drucker'}" style="width:64px;height:64px;object-fit:cover;border-radius:8px;border:1px solid #2f3a4d;">`
        : renderPrinterIcon(printer.printer_type);
    const nozzle = printer.nozzle_temp ?? "—";
    const bed = printer.bed_temp ?? "—";
    const filament = printer.filament_material || printer.printer_type?.toUpperCase() || "—";
    const progress = printer.progress_percent ?? 0;
    const progressColor = pickProgressColor(progress);

    return `
    <article class="card">
        <div class="card__head">
            <div class="card__title">${printer.name || "Unbenannt"}</div>
            <div class="card__badges">
                <div class="card__status ${online ? "" : "offline"}">
                    <span class="dot"></span>${onlineLabel}
                </div>
                <div class="card__status ${printer.auto_connect ? "" : "offline"}">
                    <span class="dot"></span>Auto Connect
                </div>
            </div>
            <div class="kebab">
                <button aria-label="Aktionen" onclick="toggleMenu(event, '${printer.id}')">⋮</button>
                <div class="kebab-menu" id="menu-${printer.id}">
                    <button onclick="openEditModal('${printer.id}')">Bearbeiten</button>
                    <button onclick="testConnection('${printer.id}')">Verbindung testen</button>
                    <button onclick="deletePrinter('${printer.id}')">Löschen</button>
                </div>
            </div>
        </div>

        <div class="card__body">
            <div class="card__image">${icon}</div>
            <div class="card__meta">
                <div class="temp"><span class="label">Filament:</span><span class="value">${filament}</span></div>
                <div class="temp"><span class="label">Düse:</span><span class="value">${nozzle}</span></div>
                <div class="temp"><span class="label">Bett:</span><span class="value">${bed}</span></div>
            </div>
        </div>

        <div class="card__progress">
            <div class="progress-bar">
                <div class="progress-bar__fill" style="width:${Math.min(Math.max(progress, 0), 100)}%; background:${progressColor}"></div>
            </div>
            <div class="progress-value">${Math.round(progress)}%</div>
        </div>
    </article>
    `;
}

function pickProgressColor(val) {
    const v = Math.min(Math.max(val ?? 0, 0), 100);
    if (v <= 20) return "linear-gradient(90deg, #e74c3c, #c0392b)";
    if (v <= 80) return "linear-gradient(90deg, #f39c12, #e67e22)";
    return "linear-gradient(90deg, #2ecc71, #27ae60)";
}

function renderPrinterIcon(type) {
    if (type === "bambu" || type === "bambu_lab" || !type) {
        return `<img src="/frontend/img/X1C.png" alt="Bambu X1C">`;
    }
    const accent = type === "klipper" ? "#3498db" : type === "manual" ? "#95a5a6" : "#f39c12";
    return `
    <svg width="64" height="64" viewBox="0 0 64 64" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="8" y="10" width="48" height="44" rx="7" fill="#0f141c" stroke="#2f3a4d" stroke-width="2"/>
      <rect x="14" y="14" width="36" height="12" rx="3" fill="#1b2431" stroke="#2f3a4d" stroke-width="1.5"/>
      <rect x="14" y="28" width="36" height="22" rx="4" fill="#111823" stroke="#2f3a4d" stroke-width="1.5"/>
      <rect x="20" y="32" width="24" height="11" rx="2" fill="#182231"/>
      <rect x="20" y="46" width="24" height="4" rx="2" fill="${accent}"/>
      <circle cx="46" cy="20" r="3" fill="#2ecc71"/>
    </svg>`;
}

document.addEventListener("DOMContentLoaded", () => {
    loadPrintersModern();
    if (refreshBtn) refreshBtn.addEventListener("click", loadPrintersModern);
});

// Kebab-Menü
function toggleMenu(evt, id) {
    evt.stopPropagation();
    document.querySelectorAll(".kebab-menu").forEach(m => m.classList.remove("open"));
    const menu = document.getElementById(`menu-${id}`);
    if (menu) menu.classList.toggle("open");
    document.addEventListener("click", () => {
        document.querySelectorAll(".kebab-menu").forEach(m => m.classList.remove("open"));
    }, { once: true });
}

// Edit-Modal
function closeEditModal() {
    const modal = document.getElementById("printerEditModal");
    if (modal) modal.classList.remove("show");
}

async function openEditModal(id) {
    try {
        const res = await fetch(`/api/printers/${id}`);
        if (!res.ok) throw new Error("Laden fehlgeschlagen");
        const p = await res.json();
        document.getElementById("editId").value = p.id;
        document.getElementById("editName").value = p.name || "";
        document.getElementById("editType").value = p.printer_type || "";
        document.getElementById("editIp").value = p.ip_address || "";
        document.getElementById("editPort").value = p.port || "";
        document.getElementById("editSerial").value = p.cloud_serial || "";
        document.getElementById("editApiKey").value = p.api_key || "";
        document.getElementById("editAutoConnect").checked = !!p.auto_connect;
        document.getElementById("printerEditModal").classList.add("show");
    } catch (e) {
        alert("Fehler beim Laden des Druckers");
    }
}

async function savePrinterEdit(ev) {
    ev.preventDefault();
    const id = document.getElementById("editId").value;
    const payload = {
        name: document.getElementById("editName").value,
        printer_type: document.getElementById("editType").value,
        ip_address: document.getElementById("editIp").value,
        port: document.getElementById("editPort").value ? Number(document.getElementById("editPort").value) : null,
        cloud_serial: document.getElementById("editSerial").value,
        api_key: document.getElementById("editApiKey").value,
        auto_connect: document.getElementById("editAutoConnect").checked
    };
    try {
        const res = await fetch(`/api/printers/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error("Speichern fehlgeschlagen");
        closeEditModal();
        loadPrintersModern();
    } catch (e) {
        alert("Fehler beim Speichern");
    }
}

// Verbindung testen
async function testConnection(id) {
    try {
        const res = await fetch(`/api/printers/${id}/test`, { method: "POST" });
        const data = await res.json();
        alert(data.message || "Test abgeschlossen");
    } catch (e) {
        alert("Fehler beim Verbindungstest");
    }
}

// Löschen
async function deletePrinter(id) {
    if (!confirm("Drucker wirklich löschen?")) return;
    try {
        const res = await fetch(`/api/printers/${id}`, { method: "DELETE" });
        if (!res.ok) throw new Error();
        loadPrintersModern();
    } catch (e) {
        alert("Fehler beim Löschen");
    }
}
