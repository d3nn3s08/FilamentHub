const cardsContainer = document.getElementById("cardsContainer");
const refreshBtn = document.getElementById("refreshBtn");

async function loadPrinters() {
    if (!cardsContainer) return;
    cardsContainer.innerHTML = '<div class="empty">Lade Drucker ...</div>';
    try {
        const res = await fetch("/api/printers/");
        if (!res.ok) throw new Error("Request failed");
        const printers = await res.json();
        const liveRes = await fetch("/api/live-state/");
        const liveData = await liveRes.ok ? await liveRes.json() : {};
        // Mappe Live-State nach cloud_serial, nutze payload.print falls vorhanden, sonst payload
        const liveMap = Object.fromEntries(
            Object.entries(liveData).map(([k, v]) => {
                let live = v.payload && v.payload.print ? { ...v.payload.print } : { ...v.payload };
                // AMS Tray-Daten explizit kopieren
                if (v.payload?.ams?.ams && Array.isArray(v.payload.ams.ams) && v.payload.ams.ams[0]) {
                    live.tray = v.payload.ams.ams[0].tray;
                    live.tray_now = v.payload.ams.ams[0].tray_now;
                }
                return [k, live];
            })
        );
        if (!Array.isArray(printers) || printers.length === 0) {
            cardsContainer.innerHTML = '<div class="empty">Keine Drucker konfiguriert.</div>';
            return;
        }
        cardsContainer.innerHTML = printers.map(printer => renderCard({
            ...printer,
            live: liveMap[printer.cloud_serial] || null
        })).join("");
    } catch (err) {
        console.error(err);
        cardsContainer.innerHTML = '<div class="empty">Fehler beim Laden der Drucker.</div>';
    }
}

function renderCard(printer) {
    const online = printer.online === true;
    const onlineLabel = online ? "Online" : printer.online === null ? "Manuell" : "Offline";
    const icon = printer.image_url
        ? `<img src="${printer.image_url}" alt="${printer.name || "Drucker"}" style="width:64px;height:64px;object-fit:cover;border-radius:8px;border:1px solid #2f3a4d;">`
        : renderPrinterIcon(printer.printer_type);
    // Live-Daten bevorzugen, Fallback auf statische Daten
    const nozzle = printer.live?.nozzle_temper ?? printer.nozzle_temp ?? "-";
    const bed = printer.live?.bed_temper ?? printer.bed_temp ?? "-";

    // AMS-Daten extrahieren (Temperatur & Luftfeuchtigkeit)
    let amsTemp = null;
    let amsHumidity = null;
    if (printer.live?.ams?.ams && Array.isArray(printer.live.ams.ams) && printer.live.ams.ams[0]) {
        amsTemp = printer.live.ams.ams[0].temp;
        amsHumidity = printer.live.ams.ams[0].humidity;
    }

    let filament = "-";
    // Robust: tray/tray_now ggf. aus AMS-Daten extrahieren
    let tray = printer.live?.tray;
    let tray_now = printer.live?.tray_now;
    if ((!tray || tray.length === 0) && printer.live?.ams?.ams && Array.isArray(printer.live.ams.ams) && printer.live.ams.ams[0]) {
        tray = printer.live.ams.ams[0].tray;
        tray_now = printer.live.ams.ams[0].tray_now;
    }
    console.log("DEBUG AMS tray_now:", tray_now, "tray:", tray, printer);
    if (tray && Array.isArray(tray) && tray.length > 0) {
        let tray_now_num = Number(tray_now);
        if (!isNaN(tray_now_num) && tray[tray_now_num]) {
            const t = tray[tray_now_num];
            filament = t.tray_sub_brands || t.tray_type || "-";
        } else {
            const t = tray[0];
            filament = t.tray_sub_brands || t.tray_type || "-";
        }
    } else {
        console.log("DEBUG Filament Fallback:", printer.live);
        filament = printer.live?.tray_type || printer.live?.filament_material || printer.filament_material || printer.printer_type?.toUpperCase() || "-";
        if (filament && filament !== "-") filament += "  | Datenbank";
    }
    const progress = printer.live?.percent ?? printer.progress_percent ?? 0;
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
                ${amsTemp && amsHumidity ? `<div class="temp"><span class="label">AMS:</span><span class="value">🌡️ ${amsTemp}°C  💧 ${amsHumidity}%</span></div>` : ''}
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
    loadPrinters();
    if (refreshBtn) {
        refreshBtn.addEventListener("click", loadPrinters);
    }
});

function toggleMenu(evt, id) {
    evt.stopPropagation();
    document.querySelectorAll(".kebab-menu").forEach(m => m.classList.remove("open"));
    const menu = document.getElementById(`menu-${id}`);
    if (menu) menu.classList.toggle("open");
    document.addEventListener("click", () => {
        document.querySelectorAll(".kebab-menu").forEach(m => m.classList.remove("open"));
    }, { once: true });
}

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
        document.getElementById("editPower").value = p.power_consumption_kw ?? "";
        document.getElementById("editMaintenance").value = p.maintenance_cost_yearly ?? "";
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
        power_consumption_kw: document.getElementById("editPower").value ? Number(document.getElementById("editPower").value) : null,
        maintenance_cost_yearly: document.getElementById("editMaintenance").value ? Number(document.getElementById("editMaintenance").value) : null,
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
        loadPrinters();
    } catch (e) {
        alert("Fehler beim Speichern");
    }
}

async function testConnection(id) {
    try {
        const res = await fetch(`/api/printers/${id}/test`, { method: "POST" });
        const data = await res.json();
        alert(data.message || "Test abgeschlossen");
    } catch (e) {
        alert("Fehler beim Verbindungstest");
    }
}

async function deletePrinter(id) {
    if (!confirm("Drucker wirklich löschen?")) return;
    try {
        const res = await fetch(`/api/printers/${id}`, { method: "DELETE" });
        if (!res.ok) throw new Error();
        loadPrinters();
    } catch (e) {
        alert("Fehler beim Löschen");
    }
}
