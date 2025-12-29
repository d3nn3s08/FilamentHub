async function loadAmsDebug() {
    const root = document.getElementById("amsRoot");
    const rawPre = document.getElementById("rawJson");
    const parsedPre = document.getElementById("parsedJson");
    const mappedPre = document.getElementById("mappedJson");
    const toggles = document.querySelectorAll("[data-toggle]");

    try {
        const res = await fetch("/api/debug/ams");
        if (!res.ok) throw new Error("Request failed");
        const data = await res.json();
        if (rawPre) rawPre.textContent = JSON.stringify(data.raw, null, 2);
        if (parsedPre) parsedPre.textContent = JSON.stringify(data.parsed, null, 2);
        if (mappedPre) mappedPre.textContent = JSON.stringify(data.mapped, null, 2);

        renderAmsUnits(root, data.parsed || []);

        toggles.forEach(btn => {
            btn.addEventListener("click", () => toggleBlock(btn.dataset.toggle));
        });
    } catch (e) {
        console.error(e);
        if (root) root.innerHTML = '<div class="panel">Fehler beim Laden der AMS-Daten.</div>';
    }
}

function toggleBlock(target) {
    const blocks = {
        raw: document.getElementById("rawBlock"),
        parsed: document.getElementById("parsedBlock"),
        mapped: document.getElementById("mappedBlock"),
    };
    Object.entries(blocks).forEach(([key, el]) => {
        if (!el) return;
        el.classList.toggle("show", key === target && !el.classList.contains("show"));
        if (key !== target) el.classList.remove("show");
    });
}

function renderAmsUnits(root, units) {
    if (!root) return;
    if (!Array.isArray(units) || units.length === 0) {
        root.innerHTML = '<div class="panel">Keine AMS-Daten gefunden.</div>';
        return;
    }

    root.innerHTML = units
        .map((u) => renderAmsCard(u))
        .join("");
}

function renderAmsCard(u) {
    const trays = Array.isArray(u.trays) ? u.trays : [];
    const trayGrid = trays
        .map((t) => renderTray(t, u.active_tray))
        .join("");
    const badge = u.active_tray !== undefined && u.active_tray !== null
        ? `<span class="badge active">active_tray: ${u.active_tray}</span>`
        : `<span class="badge">no active tray</span>`;
    return `
    <article class="ams-card">
        <div class="ams-card__header">
            <h3 style="margin:0;">AMS #${u.ams_id ?? "?"}</h3>
            ${badge}
        </div>
        <div class="tray-grid">
            ${trayGrid}
        </div>
    </article>`;
}

function renderTray(t, active) {
    const isActive = active === t.tray_id;
    const isEmpty = !t.material && !t.tray_uuid;
    return `
    <div class="tray ${isActive ? "active" : ""} ${isEmpty ? "empty" : ""}">
        <h4>Slot ${t.tray_id ?? "-"}</h4>
        <div class="meta">Material: ${t.material ?? "-"}</div>
        <div class="meta">UUID: ${t.tray_uuid ?? "-"}</div>
    </div>
    `;
}

document.addEventListener("DOMContentLoaded", loadAmsDebug);
