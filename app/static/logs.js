let ws = null;
const output = document.getElementById("logOutput");
const moduleSelect = document.getElementById("moduleSelect");
const dateSelect = document.getElementById("dateSelect");
const filterSelect = document.getElementById("filterSelect");
const zoomSlider = document.getElementById("zoomSlider");


// -------------------------------
// Log normal laden (REST API)
// -------------------------------
async function loadLog() {
    output.innerHTML = "Lade...";

    const module = moduleSelect.value;
    const date = dateSelect.value;

    let lines = [];
    if (module === "mqtt") {
        // MQTT-Log ist zu groß - zeige Warnung und nutze Live-Stream
        output.innerHTML = `
            <div style="padding: 20px; text-align: center; color: #ff6b6b;">
                <h3>⚠️ MQTT-Log zu groß</h3>
                <p>Die MQTT-Logdatei ist zu groß zum vollständigen Laden.</p>
                <p>Nutze den <strong>Live-Stream</strong> Button um neue Nachrichten zu sehen.</p>
                <p style="margin-top: 20px; color: #888;">
                    Oder lösche die alte Logdatei im Services-Tab und lade neu.
                </p>
            </div>
        `;
        return;
    } else {
        const endpoint = date
            ? `/api/logs/date/${date}?module=${module}`
            : `/api/logs/today?module=${module}`;

        const res = await fetch(endpoint);
        const data = await res.json();
        lines = data.lines;
    }

    output.innerHTML = "";
    applyLogLines(lines);
}


// -------------------------------
// Live Log Stream (WebSocket)
// -------------------------------
function startLive() {
    const module = moduleSelect.value;

    if (ws) {
        ws.close();
        ws = null;
    }

    // Für MQTT: Zeige nur neue Zeilen (tail=0), für andere: zeige letzte 100 Zeilen
    const tail = module === "mqtt" ? 0 : 100;
    ws = new WebSocket(`ws://${location.host}/api/mqtt/ws/logs/${module}?tail=${tail}`);

    ws.onopen = () => {
        output.innerHTML = `<div style="color: #4caf50; padding: 10px;">✅ Live-Stream verbunden - warte auf neue Nachrichten...</div>`;
    };

    ws.onmessage = (event) => {
        appendLogLine(event.data);
    };

    ws.onerror = () => {
        output.innerHTML += `<div style="color: #ff6b6b; padding: 10px;">❌ Verbindungsfehler</div>`;
    };
}


// -------------------------------
// Log Rendering + Filter
// -------------------------------
function applyLogLines(lines) {
    output.innerHTML = "";
    lines.forEach(appendLogLine);
}

function appendLogLine(line) {
    const filter = filterSelect.value;

    if (filter !== "ALL" && !line.includes(filter))
        return;

    const div = document.createElement("div");

    if (line.includes("ERROR")) div.className = "error";
    else if (line.includes("WARNING")) div.className = "warning";
    else div.className = "info";

    div.textContent = line;
    output.appendChild(div);

    // Auto-scroll down
    output.scrollTop = output.scrollHeight;
}


// -------------------------------
// Zoom
// -------------------------------
zoomSlider.oninput = () => {
    output.style.fontSize = `${zoomSlider.value}px`;
};


// -------------------------------
// Events
// -------------------------------
document.getElementById("loadBtn").onclick = loadLog;
document.getElementById("liveBtn").onclick = startLive;
