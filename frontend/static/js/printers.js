const cardsContainer = document.getElementById("cardsContainer");
const refreshBtn = document.getElementById("refreshBtn");

// [BETA] Klipper-Support: Cache für geladene Drucker-Objekte (inkl. live_state)
const _klipperPrinterCache = new Map();
// [BETA] Klipper-Support: Server-seitige Temperatur-History (Map: printer_id → Array)
const _klipperTempHistory = new Map();
// [BETA] Klipper-Support: Chart-Instanz
let _kdmChart = null;

async function loadPrinters() {
    if (!cardsContainer) return;
    cardsContainer.innerHTML = '<div class="empty">Lade Drucker…</div>';
    try {
        const res = await fetch("/api/printers/");
        if (!res.ok) throw new Error("Request failed");
        const printers = await res.json();
        const liveRes = await fetch("/api/live-state/");
        const liveData = await liveRes.ok ? await liveRes.json() : {};
        const liveMap = Object.fromEntries(Object.entries(liveData));
        if (!Array.isArray(printers) || printers.length === 0) {
            cardsContainer.innerHTML = '<div class="empty">Keine Drucker konfiguriert.</div>';
            return;
        }
        // [BETA] Klipper-Support: Cache und liveKey pro Drucker bestimmen
        _klipperPrinterCache.clear();
        cardsContainer.innerHTML = printers.map(printer => {
            // [BETA] Klipper-Support: Klipper hat keine cloud_serial → Fallback auf "klipper_{id}"
            const liveKey = printer.cloud_serial || `klipper_${printer.id}`;
            const liveEntry = liveMap[liveKey] || null;
            const enriched = {
                ...printer,
                live: extractLivePayload(liveEntry),
                live_state: liveEntry,
            };
            if (printer.printer_type === 'klipper') {
                _klipperPrinterCache.set(printer.id, enriched);
                // [BETA] Klipper-Support: JS-seitige Temp-History bei jedem Poll aktualisieren
                const s = liveEntry?.payload?.status;
                if (s) {
                    if (!_klipperTempHistory.has(printer.id)) _klipperTempHistory.set(printer.id, []);
                    const hist = _klipperTempHistory.get(printer.id);
                    const nozzle = s.extruder?.temperature ?? null;
                    const bed    = s.heater_bed?.temperature ?? null;
                    if (nozzle != null || bed != null) {
                        hist.push({ ts: Date.now(), nozzle, bed,
                            nozzlePower: s.extruder?.power ?? null,
                            bedPower:    s.heater_bed?.power ?? null });
                        if (hist.length > 600) hist.splice(0, hist.length - 600);
                    }
                }
            }
            return renderCard(enriched);
        }).join("");
    } catch (err) {
        console.error(err);
        cardsContainer.innerHTML = '<div class="empty">Fehler beim Laden der Drucker.</div>';
    }
}

function extractLivePayload(entry) {
    if (!entry || !entry.payload) return null;
    const payload = entry.payload;

    // Bambu: payload.print vorhanden – unveränderter Original-Pfad
    if (payload.print) {
        const live = { ...payload.print };
        if (payload?.ams?.ams && Array.isArray(payload.ams.ams) && payload.ams.ams[0]) {
            live.tray = payload.ams.ams[0].tray;
            live.tray_now = payload.ams.ams[0].tray_now;
        }
        return live;
    }

    // [BETA] Klipper-Support: Moonraker-Payload ist doppelt verschachtelt:
    // entry.payload = { ts, payload: { klippy_state, status: { extruder, heater_bed, ... } } }
    // Daher: payload.payload.status (nicht payload.status)
    const klipperInner = payload.payload;
    if (klipperInner?.status) {
        const s = klipperInner.status;
        return {
            nozzle_temper:  s.extruder?.temperature ?? null,
            bed_temper:     s.heater_bed?.temperature ?? null,
            nozzle_target:  s.extruder?.target ?? null,
            bed_target:     s.heater_bed?.target ?? null,
            nozzle_power:   s.extruder?.power ?? null,
            bed_power:      s.heater_bed?.power ?? null,
            mc_percent:     s.display_status?.progress != null
                                ? Math.round(s.display_status.progress * 100)
                                : null,
            gcode_state:    s.print_stats?.state ?? null,
            subtask_name:   s.print_stats?.filename ?? null,
            print_duration: s.print_stats?.print_duration ?? null,
        };
    }

    return { ...payload };
}

function renderCard(printer) {
    const liveState = printer.live_state || {};
    const autoConnectEnabled = liveState.auto_connect_enabled ?? printer.auto_connect;
    const mqttConnected = liveState.mqtt_connected === true;
    const online = liveState.printer_online === true;
    const warning = !!(autoConnectEnabled && mqttConnected && !online);
    const statusClass = warning ? "warning" : (online ? "" : "offline");
    const onlineLabel = warning ? "Warning" : (online ? "Online" : "Offline");
    const icon = printer.image_url
        ? `<img src="${printer.image_url}" alt="${printer.name || "Drucker"}" style="width:64px;height:64px;object-fit:cover;border-radius:8px;border:1px solid #2f3a4d;">`
        : renderPrinterIcon(printer.printer_type);
    // Live-Daten bevorzugen, Fallback auf statische Daten
    const nozzle = printer.live?.nozzle_temper ?? printer.live?.nozzle_temp ?? printer.nozzle_temp ?? printer.nozzle_temper ?? printer.live?.nozzle ?? printer.live?.extruder_temp ?? printer.temperature?.nozzle ?? "-";
    const bed = printer.live?.bed_temper ?? printer.live?.bed_temp ?? printer.bed_temp ?? printer.bed_temper ?? printer.live?.bed ?? printer.temperature?.bed ?? "-";

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
        filament = printer.live?.tray_type || printer.live?.filament_material || printer.filament_material || printer.printer_type?.toUpperCase() || "-";
    }
    const progress = (printer.live?.percent != null) ? printer.live.percent : (printer.progress_percent != null ? printer.progress_percent : null);
    const progressColor = pickProgressColor(progress);

    // WiFi Signal: try several common locations in live payloads
    const wifiRaw = printer.live?.wifi_signal || printer.wifi_signal || printer.live?.device?.wifi_signal || printer.live?.net?.wifi_signal || null;

    function rssiToPercent(raw) {
        if (raw == null) return null;
        try {
            let s = String(raw).trim();
            if (s.toLowerCase().endsWith('dbm')) s = s.slice(0, -3);
            const m = s.match(/-?\d+/);
            if (!m) return null;
            let rssi = parseInt(m[0], 10);
            if (isNaN(rssi)) return null;
            // Map -100..-30 dBm -> 0..100%
            rssi = Math.max(-100, Math.min(-30, rssi));
            const pct = Math.round((rssi + 100) / 70 * 100);
            return `${pct}%`;
        } catch (e) {
            return null;
        }
    }

    const wifiPct = rssiToPercent(wifiRaw);
    const wifiPctNum = wifiPct ? parseInt(wifiPct, 10) : null;
    let wifiColor = '#999';
    if (wifiPctNum !== null && !isNaN(wifiPctNum)) {
        if (wifiPctNum >= 80) wifiColor = '#2ecc71';
        else if (wifiPctNum >= 50) wifiColor = '#f39c12';
        else wifiColor = '#e74c3c';
    }
    const lastSeenText = formatCacheAge(liveState.cache_age_sec, liveState.offline_reason);

    return `
    <article class="card ${online ? 'online' : 'offline'}">
        <div class="card__image">${icon}</div>

        <div class="card__head">
            <div class="card__title">${printer.name || "Unbenannt"}</div>
            <div class="card__badges">
                <div class="card__status ${statusClass}">
                    <span class="dot"></span>${onlineLabel}
                </div>
                <div class="card__status ${autoConnectEnabled ? "" : "offline"}">
                    <span class="dot"></span>Auto Connect
                </div>
            </div>
        </div>

        <div class="card__body">
            <div class="card__meta">
                <div class="temp"><span class="label">Filament:</span><span class="value">${filament}</span></div>
                <div class="temp"><span class="label">Düse:</span><span class="value">${nozzle}</span><span style="margin:0 8px;color:var(--text-dim)">·</span><span class="label">Bett:</span><span class="value">${bed}</span></div>
                ${lastSeenText ? `<div class="temp"><span class="label">Letzter Kontakt:</span><span class="value">${lastSeenText}</span></div>` : ''}
                ${printer.printer_type === 'klipper' ? `<div class="temp"><span class="label">Details:</span><span class="value"><button onclick="openKlipperDetailModal(${printer.id})" title="Klipper Detail-Modal öffnen" style="background:rgba(52,152,219,0.18);border:1px solid rgba(52,152,219,0.4);border-radius:6px;padding:2px 10px;color:#5dade2;cursor:pointer;font-size:0.75rem;font-weight:600;font-family:inherit;letter-spacing:0.03em;">Live-Daten ⊕</button></span></div>` : ''}
                ${amsTemp && amsHumidity ? `<div class="temp"><span class="label">AMS:</span><span class="value">🌡️ ${amsTemp}°C 💧 ${amsHumidity}%</span></div>` : ''}
                ${wifiRaw ? `<div class="temp"><span class="label">WiFi:</span><span class="value"><span class="wifi-icon" title="${wifiRaw}" style="display:inline-flex;align-items:center;gap:8px;">` +
                    `<svg width="16" height="16" viewBox="0 0 24 24" fill="${wifiColor}" xmlns="http://www.w3.org/2000/svg"><path d="M12 18c.6 0 1-.4 1-1s-.4-1-1-1-1 .4-1 1 .4 1 1 1zm0-4c2 0 3.8.8 5.2 2.1.2.2.5.2.7 0 .2-.2.2-.5 0-.7C16.8 13.3 14.6 12 12 12s-4.8 1.3-6.9 3.4c-.2.2-.2.5 0 .7.2.2.5.2.7 0C8.2 14.8 10 14 12 14zM12 6c3.9 0 7 1.6 9.4 4.1.2.2.5.2.7 0 .2-.2.2-.5 0-.7C19.1 7.2 15.7 5 12 5s-7.1 2.2-10.1 4.4c-.2.2-.2.5 0 .7.2.2.5.2.7 0C5 7.6 8.1 6 12 6z"/></svg>` +
                    `${wifiPct ? `<span style="color:${wifiColor};font-weight:600;">${wifiPct}</span>` : `<span style="color:${wifiColor};font-weight:600;">${wifiRaw}</span>`}` +
                `</span></span></div>` : ''}
            </div>
        </div>

        <div class="card__progress">
            <div class="progress-bar">
                <div class="progress-bar__fill" style="width:${progress != null ? Math.min(Math.max(progress, 0), 100) : 0}%; background:${progressColor}; ${progress == null ? 'opacity:0.35;' : ''}"></div>
            </div>
            <div class="progress-value">${progress != null ? Math.round(progress) + '%' : '—'}</div>
        </div>

        <div class="kebab">
            <button aria-label="Aktionen" onclick="toggleMenu(event, '${printer.id}')">⋮</button>
            <div class="kebab-menu" id="menu-${printer.id}">
                <button onclick="openEditModal('${printer.id}')">Bearbeiten</button>
                <button onclick="testConnection('${printer.id}')">Verbindung testen</button>
                <button onclick="deletePrinter('${printer.id}')">Löschen</button>
            </div>
        </div>
    </article>
    `;
}

function formatCacheAge(cacheAgeSec, offlineReason) {
    if (cacheAgeSec == null) {
        return offlineReason === "never_seen" ? "nie" : "";
    }
    if (cacheAgeSec < 60) return `${cacheAgeSec}s`;
    const mins = Math.floor(cacheAgeSec / 60);
    const secs = cacheAgeSec % 60;
    if (mins < 60) return `${mins}m ${secs}s`;
    const hours = Math.floor(mins / 60);
    const remMins = mins % 60;
    return `${hours}h ${remMins}m`;
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
    const editType = document.getElementById("editType");
    if (editType) {
        editType.addEventListener("change", () => {
            const currentSeries = document.getElementById("editSeriesValue").value || "UNKNOWN";
            setSeriesUi(editType.value, currentSeries);
            applyKlipperFieldLock(editType.value);
        });
    }
});

function applyKlipperFieldLock(printerType) {
    const isKlipper = String(printerType || "").toLowerCase() === "klipper";
    const lockIds = ["editMqttVersion", "editSerial", "editApiKey"];

    lockIds.forEach((id) => {
        const el = document.getElementById(id);
        if (!el) return;
        // BETA: Sperrt bei Klipper Felder, die dort nicht manuell gepflegt werden sollen.
        el.disabled = isKlipper;
        el.title = isKlipper ? "Feld ist bei Klipper gesperrt" : "";
    });
}

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

function normalizeSeries(value) {
    if (!value) return "UNKNOWN";
    return String(value).toUpperCase();
}

function setSeriesSelection(seriesValue) {
    const radios = document.querySelectorAll('input[name="editSeries"]');
    const target = normalizeSeries(seriesValue);
    radios.forEach(radio => {
        radio.checked = radio.value === target;
    });
}

function setSeriesUi(printerType, seriesValue) {
    const wrap = document.getElementById("editSeriesWrap");
    const hint = document.getElementById("editSeriesHint");
    const radios = document.querySelectorAll('input[name="editSeries"]');
    if (!wrap) return;

    const isBambu = printerType === "bambu" || printerType === "bambu_lab";
    if (!isBambu) {
        wrap.style.display = "none";
        radios.forEach(radio => {
            radio.disabled = false;
        });
        return;
    }

    const normalized = normalizeSeries(seriesValue);
    wrap.style.display = "block";
    setSeriesSelection(normalized);

    const isLocked = normalized !== "UNKNOWN";
    radios.forEach(radio => {
        radio.disabled = isLocked;
    });
    if (hint) {
        hint.textContent = isLocked
            ? "Serie ist bereits festgelegt."
            : "Bitte waehle die Serie dieses Druckers.";
    }
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
        document.getElementById("editMqttVersion").value = p.mqtt_version ?? "";
        document.getElementById("editPower").value = p.power_consumption_kw ?? "";
        document.getElementById("editMaintenance").value = p.maintenance_cost_yearly ?? "";
        document.getElementById("editSerial").value = p.cloud_serial || "";
        document.getElementById("editApiKey").value = p.api_key || "";
        document.getElementById("editAutoConnect").checked = !!p.auto_connect;
        document.getElementById("editSeriesValue").value = normalizeSeries(p.series);
        setSeriesUi(p.printer_type || "", normalizeSeries(p.series));
        applyKlipperFieldLock(p.printer_type || "");

        // Bild laden
        const currentImageUrl = p.image_url || "";
        document.getElementById("currentImageUrl").value = currentImageUrl;
        const imagePreview = document.getElementById("imagePreview");
        const removeBtn = document.getElementById("removeImageBtn");

        if (currentImageUrl) {
            imagePreview.innerHTML = `<img src="${currentImageUrl}" alt="Drucker Bild">`;
            imagePreview.classList.add("has-image");
            removeBtn.style.display = "inline-block";
        } else {
            resetImagePreview();
        }

        // File input zurücksetzen
        document.getElementById("editImage").value = "";

        document.getElementById("printerEditModal").classList.add("show");
    } catch (e) {
        alert("Fehler beim Laden des Druckers");
    }
}

async function savePrinterEdit(ev) {
    ev.preventDefault();
    const id = document.getElementById("editId").value;
    const mqttVersion = document.getElementById("editMqttVersion").value;
    const printerType = document.getElementById("editType").value;
    const storedSeries = document.getElementById("editSeriesValue").value || "UNKNOWN";
    let seriesValue = normalizeSeries(storedSeries);
    const isBambu = printerType === "bambu" || printerType === "bambu_lab";
    if (isBambu) {
        const selected = document.querySelector('input[name="editSeries"]:checked');
        if (!selected) {
            alert("Bitte Serie waehlen");
            return;
        }
        seriesValue = normalizeSeries(selected.value);
        document.getElementById("editSeriesValue").value = seriesValue;
    }
    const payload = {
        name: document.getElementById("editName").value,
        printer_type: printerType,
        ip_address: document.getElementById("editIp").value,
        port: document.getElementById("editPort").value ? Number(document.getElementById("editPort").value) : null,
        mqtt_version: mqttVersion || null, // Leerer String → null für Auto-Erkennung
        power_consumption_kw: document.getElementById("editPower").value ? Number(document.getElementById("editPower").value) : null,
        maintenance_cost_yearly: document.getElementById("editMaintenance").value ? Number(document.getElementById("editMaintenance").value) : null,
        cloud_serial: document.getElementById("editSerial").value,
        api_key: document.getElementById("editApiKey").value,
        auto_connect: document.getElementById("editAutoConnect").checked,
        series: seriesValue
    };
    try {
        // 1. Drucker-Daten speichern
        const res = await fetch(`/api/printers/${id}`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error("Speichern fehlgeschlagen");

        // 2. Bild hochladen (falls vorhanden)
        const imageFile = document.getElementById("editImage").files[0];
        if (imageFile) {
            const formData = new FormData();
            formData.append("file", imageFile);

            const imgRes = await fetch(`/api/printers/${id}/image`, {
                method: "POST",
                body: formData
            });

            if (!imgRes.ok) {
                console.error("Bild-Upload fehlgeschlagen");
                alert("Drucker gespeichert, aber Bild-Upload fehlgeschlagen");
            }
        }

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

// Image Upload Helper Functions
function handleImagePreview(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Validierung
    const maxSize = 5 * 1024 * 1024; // 5MB
    if (file.size > maxSize) {
        alert("Bild ist zu groß. Maximal 5MB erlaubt.");
        event.target.value = "";
        return;
    }

    const allowedTypes = ["image/png", "image/jpeg", "image/webp"];
    if (!allowedTypes.includes(file.type)) {
        alert("Ungültiges Bildformat. Nur PNG, JPG und WebP erlaubt.");
        event.target.value = "";
        return;
    }

    // Preview anzeigen
    const reader = new FileReader();
    reader.onload = function(e) {
        const imagePreview = document.getElementById("imagePreview");
        imagePreview.innerHTML = `<img src="${e.target.result}" alt="Vorschau">`;
        imagePreview.classList.add("has-image");
        document.getElementById("removeImageBtn").style.display = "inline-block";
    };
    reader.readAsDataURL(file);
}

function removeImage() {
    const id = document.getElementById("editId").value;
    if (!confirm("Bild wirklich entfernen?")) return;

    // Bild auf Server löschen
    fetch(`/api/printers/${id}/image`, { method: "DELETE" })
        .then(res => {
            if (res.ok) {
                resetImagePreview();
                document.getElementById("currentImageUrl").value = "";
                document.getElementById("editImage").value = "";
                loadPrinters();
            } else {
                alert("Fehler beim Entfernen des Bildes");
            }
        })
        .catch(e => {
            console.error("Fehler beim Entfernen des Bildes", e);
            alert("Fehler beim Entfernen des Bildes");
        });
}

function resetImagePreview() {
    const imagePreview = document.getElementById("imagePreview");
    imagePreview.innerHTML = `
        <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <circle cx="8.5" cy="8.5" r="1.5"></circle>
            <polyline points="21 15 16 10 5 21"></polyline>
        </svg>
        <span class="image-preview-text">Kein Bild</span>
    `;
    imagePreview.classList.remove("has-image");
    document.getElementById("removeImageBtn").style.display = "none";
}

// =============================================================================
// [BETA] Klipper-Support: Detail-Modal Funktionen
// =============================================================================

// [BETA] Klipper-Support: Detail-Modal öffnen — lädt Server-History und rendert Chart
async function openKlipperDetailModal(printerId) {
    const printer = _klipperPrinterCache.get(printerId);
    if (!printer) return;

    const liveState = printer.live_state || {};
    const live      = printer.live || {};
    const raw       = liveState.payload?.status || {};

    const online       = liveState.printer_online === true;
    const cacheAge     = formatCacheAge(liveState.cache_age_sec, liveState.offline_reason);
    const nozzle       = live.nozzle_temper ?? raw.extruder?.temperature ?? '-';
    const nozzleTarget = raw.extruder?.target ?? null;
    const bed          = live.bed_temper    ?? raw.heater_bed?.temperature ?? '-';
    const bedTarget    = raw.heater_bed?.target ?? null;
    const state        = live.gcode_state ?? raw.print_stats?.state ?? '-';
    const filename     = live.subtask_name ?? raw.print_stats?.filename ?? '-';
    const progress     = live.mc_percent ??
                         (raw.display_status?.progress != null
                             ? Math.round(raw.display_status.progress * 100) : null);
    const filUsedM     = raw.print_stats?.filament_used;
    const filUsed      = filUsedM != null ? (filUsedM).toFixed(2) + ' m' : '—';
    const nozzlePower  = live.nozzle_power ?? raw.extruder?.power ?? null;
    const bedPower     = live.bed_power    ?? raw.heater_bed?.power ?? null;
    const ip           = printer.ip_address ?? '—';
    const port         = printer.port ?? 7125;

    const fmtTemp = (val, target) => {
        let s = val !== '-' && val != null ? `${Number(val).toFixed(1)}°C` : '—';
        if (target != null && Number(target) > 0) s += ` → ${Number(target).toFixed(0)}°`;
        return s;
    };
    const setPower = (barId, pctId, val) => {
        const pct = val != null ? Math.round(val * 100) : null;
        const el  = document.getElementById(pctId);
        const bar = document.getElementById(barId);
        if (el)  el.textContent  = pct != null ? `${pct}%` : '—';
        if (bar) bar.style.width = (pct ?? 0) + '%';
    };

    document.getElementById('kdm-name').textContent     = printer.name || 'Klipper-Drucker';
    document.getElementById('kdm-ip').textContent       = `${ip}:${port}`;
    document.getElementById('kdm-status').textContent   = online ? 'Online' : 'Offline';
    document.getElementById('kdm-status').className     = 'kdm-badge ' + (online ? 'kdm-online' : 'kdm-offline');
    document.getElementById('kdm-last').textContent     = cacheAge || '—';
    document.getElementById('kdm-nozzle').textContent   = fmtTemp(nozzle, nozzleTarget);
    document.getElementById('kdm-bed').textContent      = fmtTemp(bed, bedTarget);
    document.getElementById('kdm-state').textContent    = state;
    document.getElementById('kdm-file').textContent     = filename;
    document.getElementById('kdm-progress').textContent = progress != null ? `${progress}%` : '—';
    document.getElementById('kdm-filament').textContent = filUsed;
    const bar = document.getElementById('kdm-progress-bar');
    if (bar) bar.style.width = (progress ?? 0) + '%';
    setPower('kdm-nozzle-power-bar', 'kdm-nozzle-power-pct', nozzlePower);
    setPower('kdm-bed-power-bar',    'kdm-bed-power-pct',    bedPower);

    document.getElementById('klipperDetailModal').classList.add('show');

    // [BETA] Klipper-Support: Server-seitige Temp-History laden (sofortiger Chart mit Verlauf)
    try {
        const resp = await fetch(`/api/live-state/klipper/${printerId}/temp-history`);
        if (resp.ok) {
            const data = await resp.json();
            if (data.history && data.history.length > 1) {
                _klipperTempHistory.set(printerId, data.history.map(h => ({
                    ts:          new Date(h.ts).getTime(),
                    nozzle:      h.nozzle,
                    bed:         h.bed,
                    nozzlePower: h.nozzle_power,
                    bedPower:    h.bed_power,
                })));
            }
        }
    } catch (_e) { /* Fallback: JS-seitige History */ }

    _renderKlipperTempChart(printerId);
}

function closeKlipperDetailModal() {
    document.getElementById('klipperDetailModal').classList.remove('show');
}

// [BETA] Klipper-Support: ESC-Taste schließt Klipper-Detail-Modal
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeKlipperDetailModal();
});

// [BETA] Klipper-Support: Temperaturverlauf-Chart mit Heizleistungs-Linien (duale Y-Achse)
function _renderKlipperTempChart(printerId) {
    const canvas = document.getElementById('kdm-chart');
    if (!canvas) return;

    const hist = _klipperTempHistory.get(printerId) || [];

    if (_kdmChart) { _kdmChart.destroy(); _kdmChart = null; }

    if (hist.length < 2) {
        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = 'rgba(167,178,195,0.3)';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Kein Temperaturverlauf (noch zu wenig Daten)', canvas.width / 2, 60);
        return;
    }

    const labels      = hist.map(h => {
        const d = new Date(h.ts);
        return `${d.getHours().toString().padStart(2,'0')}:${d.getMinutes().toString().padStart(2,'0')}:${d.getSeconds().toString().padStart(2,'0')}`;
    });
    const nozzleTemps = hist.map(h => h.nozzle);
    const bedTemps    = hist.map(h => h.bed);
    const nozzlePows  = hist.map(h => h.nozzlePower != null ? Math.round(h.nozzlePower * 100) : null);
    const bedPows     = hist.map(h => h.bedPower    != null ? Math.round(h.bedPower    * 100) : null);
    const hasPower    = nozzlePows.some(v => v != null) || bedPows.some(v => v != null);

    const tickStyle = { color: 'rgba(167,178,195,0.5)', font: { size: 9 } };
    const gridStyle = { color: 'rgba(255,255,255,0.04)' };

    _kdmChart = new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets: [
                {
                    label: 'Nozzle °C',
                    data: nozzleTemps,
                    borderColor: '#f39c12',
                    backgroundColor: 'rgba(243,156,18,0.08)',
                    borderWidth: 1.8,
                    pointRadius: 0,
                    tension: 0.3,
                    yAxisID: 'yTemp',
                    fill: true,
                },
                {
                    label: 'Bett °C',
                    data: bedTemps,
                    borderColor: '#3498db',
                    backgroundColor: 'rgba(52,152,219,0.06)',
                    borderWidth: 1.8,
                    pointRadius: 0,
                    tension: 0.3,
                    yAxisID: 'yTemp',
                    fill: true,
                },
                {
                    label: 'Nozzle %',
                    data: nozzlePows,
                    borderColor: 'rgba(243,156,18,0.55)',
                    borderDash: [4, 3],
                    borderWidth: 1.2,
                    pointRadius: 0,
                    tension: 0.3,
                    yAxisID: 'yPower',
                },
                {
                    label: 'Bett %',
                    data: bedPows,
                    borderColor: 'rgba(52,152,219,0.55)',
                    borderDash: [4, 3],
                    borderWidth: 1.2,
                    pointRadius: 0,
                    tension: 0.3,
                    yAxisID: 'yPower',
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            animation: { duration: 0 },
            plugins: {
                legend: {
                    display: true,
                    labels: { color: 'rgba(167,178,195,0.6)', font: { size: 9 }, boxWidth: 12, padding: 8 },
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(15,21,32,0.92)',
                    borderColor: 'rgba(255,255,255,0.1)',
                    borderWidth: 1,
                    titleColor: 'rgba(167,178,195,0.8)',
                    bodyColor: '#e0e6f0',
                    padding: 8,
                },
            },
            scales: {
                x: {
                    ticks: { ...tickStyle, maxTicksLimit: 6, maxRotation: 0 },
                    grid:  gridStyle,
                },
                yTemp: {
                    position: 'left',
                    ticks: { ...tickStyle, callback: v => `${v}°` },
                    grid:  gridStyle,
                },
                yPower: {
                    position: 'right',
                    display: hasPower,
                    min: 0, max: 100,
                    ticks: { ...tickStyle, callback: v => `${v}%` },
                    grid: { display: false },
                },
            },
        },
    });
}












