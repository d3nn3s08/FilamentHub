(function () {
  var root = document.getElementById("hhMmuRoot");
  if (!root) return;

  var DEMO = {
    num_gates: 8,
    gate: 2,
    tool: 2,
    ttg_map: [0, 1, 2, 3, 4, 5, 6, 7],
    gate_status: [1, 0, 1, 1, 1, 0, 1, 1],
    gate_material: ["PLA", "", "PETG", "ABS", "ASA", "", "TPU", "PA-CF"],
    gate_color: ["ff5e4d", "", "45b4ff", "f3cd23", "4cde8a", "", "b06fe8", "f29a37"],
    gate_filament_name: ["Rot Silk", "", "Ozean Blau", "Gelb Gold", "Gruen Matt", "", "Flex Lila", "Nylon Orange"],
    gate_temperature: [215, 0, 240, 250, 255, 0, 228, 275],
    gate_spool_id: [12, -1, 47, 3, 18, -1, 122, 31],
    gate_speed_override: [100, 100, 85, 100, 100, 100, 90, 100],
    state: "idle",
    action: "none",
    filament_pos: 3,
    total_tool_changes: 47,
    total_errors: 0,
    total_time: 14580
  };

  var state = {
    baseUrl: "http://mainsailos.local",
    demoMode: true,
    ok: true,
    err: "",
    spin: false,
    selectedGate: 2,
    logs: [],
    data: clone(DEMO),
    timer: null,
    lastUpd: nowTS()
  };

  function clone(v) { return JSON.parse(JSON.stringify(v)); }
  function nowTS() { return new Date().toLocaleTimeString("de-DE"); }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function toCssColor(v) {
    if (!v) return "#2d3c59";
    if (/^[0-9a-fA-F]{6}$/.test(String(v).trim())) return "#" + String(v).trim();
    return String(v);
  }

  function fmtTime(sec) {
    var s = Number(sec || 0);
    return Math.floor(s / 3600) + "h " + Math.floor((s % 3600) / 60) + "m";
  }

  function stateChip(st) {
    if (st === "idle") return '<span class="hh-chip" style="color:#6ae485;border-color:rgba(106,228,133,.35);background:rgba(106,228,133,.08)">Bereit</span>';
    if (st === "printing") return '<span class="hh-chip" style="color:#ffc165;border-color:rgba(255,193,101,.35);background:rgba(255,193,101,.08)">Druckt</span>';
    if (st === "error") return '<span class="hh-chip" style="color:#ff7a7a;border-color:rgba(255,122,122,.35);background:rgba(255,122,122,.08)">Fehler</span>';
    return '<span class="hh-chip" style="color:#9ab4d8">' + esc(st || "-") + '</span>';
  }

  function addLog(msg, t) {
    state.logs.unshift({ ts: nowTS(), msg: msg, t: t || "info" });
    if (state.logs.length > 80) state.logs = state.logs.slice(0, 80);
  }

  async function poll() {
    if (state.demoMode) {
      state.data = clone(DEMO);
      state.ok = true;
      state.err = "";
      state.lastUpd = nowTS();
      render();
      return;
    }

    state.spin = true;
    render();

    var ctrl = new AbortController();
    var tid = setTimeout(function () { ctrl.abort(); }, 3500);

    try {
      var res = await fetch(state.baseUrl + "/printer/objects/query?mmu", { signal: ctrl.signal });
      if (!res.ok) throw new Error("HTTP " + res.status);
      var json = await res.json();
      var mmu = json && json.result && json.result.status && json.result.status.mmu;
      if (!mmu) throw new Error("Kein mmu-Objekt");
      state.data = mmu;
      state.ok = true;
      state.err = "";
      state.lastUpd = nowTS();
    } catch (e) {
      state.ok = false;
      state.err = (e && e.message) || "Unbekannter Fehler";
    } finally {
      clearTimeout(tid);
      state.spin = false;
      render();
    }
  }

  async function send(script, label) {
    addLog("-> " + label);

    if (state.demoMode) {
      addLog("OK " + label + " (Demo)", "ok");
      render();
      return true;
    }

    var ctrl = new AbortController();
    var tid = setTimeout(function () { ctrl.abort(); }, 5000);

    try {
      var res = await fetch(state.baseUrl + "/printer/gcode/script", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ script: script }),
        signal: ctrl.signal
      });
      if (!res.ok) throw new Error("HTTP " + res.status);
      addLog("OK " + label, "ok");
      setTimeout(poll, 500);
      return true;
    } catch (e) {
      addLog("Fehler " + label + ": " + ((e && e.message) || "-"), "err");
      return false;
    } finally {
      clearTimeout(tid);
      render();
    }
  }

  function renderGate(i, data, active, selected) {
    var status = data.gate_status && data.gate_status[i] != null ? data.gate_status[i] : -1;
    var color = toCssColor(data.gate_color && data.gate_color[i]);
    var mat = data.gate_material && data.gate_material[i] ? data.gate_material[i] : "-";
    var name = data.gate_filament_name && data.gate_filament_name[i] ? data.gate_filament_name[i] : "-";
    var temp = data.gate_temperature && data.gate_temperature[i] ? data.gate_temperature[i] : 0;
    var sid = data.gate_spool_id && data.gate_spool_id[i] != null ? data.gate_spool_id[i] : -1;
    var tag = status === 0 ? '<span class="hh-pill empty">Leer</span>' : '<span class="hh-pill ok">Spule</span>';

    return '' +
      '<div class="hh-gate ' + (selected ? "active" : "") + '" data-gate="' + i + '">' +
      '<div class="hh-gate-top"><div class="hh-gate-name">Gate ' + i + '</div>' + tag + '</div>' +
      '<div class="hh-spool" style="background:' + (status === 0 ? "#2d3a54" : color) + ';border-color:' + (active ? "#f1a45b" : "rgba(255,255,255,.22)") + '"></div>' +
      '<div class="hh-meta">' +
      '<div>Material: <b>' + esc(mat) + '</b></div>' +
      '<div>' + esc(name) + '</div>' +
      '<div class="hh-meta-sub"><span>Spool ' + (sid > 0 ? "#" + sid : "-") + '</span><span>' + (temp > 0 ? temp + 'C' : '-') + '</span></div>' +
      '</div>' +
      '</div>';
  }

  function render() {
    var d = state.data || DEMO;
    var n = Math.max(1, Number(d.num_gates || 8));
    if (state.selectedGate != null && state.selectedGate >= n) state.selectedGate = null;
    if (state.selectedGate == null) state.selectedGate = Math.max(0, Math.min(n - 1, Number(d.gate || 0)));

    var emptyCount = (d.gate_status || []).filter(function (s) { return s === 0; }).length;
    var loadedCount = n - emptyCount;
    var cur = d.gate != null ? Number(d.gate) : -1;

    var gatesHtml = "";
    for (var i = 0; i < n; i++) gatesHtml += renderGate(i, d, i === cur, i === state.selectedGate);

    var sel = state.selectedGate;
    var selStatus = d.gate_status && d.gate_status[sel] != null ? d.gate_status[sel] : -1;
    var selMat = d.gate_material && d.gate_material[sel] ? d.gate_material[sel] : "-";
    var selName = d.gate_filament_name && d.gate_filament_name[sel] ? d.gate_filament_name[sel] : "-";
    var selTool = d.ttg_map && d.ttg_map[sel] != null ? d.ttg_map[sel] : sel;
    var selTemp = d.gate_temperature && d.gate_temperature[sel] ? d.gate_temperature[sel] : 0;
    var selSpool = d.gate_spool_id && d.gate_spool_id[sel] != null ? d.gate_spool_id[sel] : -1;
    var selSpeed = d.gate_speed_override && d.gate_speed_override[sel] != null ? d.gate_speed_override[sel] : 100;

    var toolsHtml = "";
    for (var t = 0; t < n; t++) {
      var mapped = d.ttg_map && d.ttg_map[t] != null ? d.ttg_map[t] : t;
      var available = d.gate_status && (d.gate_status[mapped] === 1 || d.gate_status[mapped] === 2);
      var active = t === Number(d.tool != null ? d.tool : -1);
      toolsHtml += '<button class="hh-tool ' + (active ? "active" : "") + '" ' + (available ? '' : 'disabled ') + 'data-cmd="T' + t + '" data-label="T' + t + ' aktivieren">T' + t + '</button>';
    }

    var logsHtml = state.logs.length
      ? state.logs.map(function (l) {
          var c = l.t === "err" ? "#ff7a7a" : l.t === "ok" ? "#6ae485" : "#9eb5d8";
          return '<div class="hh-log-row"><span class="hh-ts">' + esc(l.ts) + '</span><span style="color:' + c + '">' + esc(l.msg) + '</span></div>';
        }).join("")
      : '<div class="hh-log-row"><span class="hh-ts"></span><span>Keine Befehle bisher...</span></div>';

    root.innerHTML = '' +
      '<div class="hh-wrap">' +

      '<div class="hh-card hh-top-note">' +
      '<div class="hh-note-grid">' +
      '<div class="hh-note-head"><span class="hh-dev-pill">In Entwicklung</span><span>Wichtiger Hinweis</span></div>' +
      '<div class="hh-note-row"><b>Datenquelle:</b> Live-Daten kommen direkt von Moonraker (<code>printer/objects/query?mmu</code>).</div>' +
      '<div class="hh-note-row"><b>CORS:</b> Bei Browser-Blockade bitte Proxy oder Backend-Route verwenden.</div>' +
      '<div class="hh-note-row"><b>Status:</b> Diese MMU-Seite ist aktuell in aktiver Entwicklung.</div>' +
      '</div>' +
      '</div>' +

      '<div class="hh-card hh-toolbar">' +
      '<div class="hh-title">MMU Klipper · Happy Hare</div>' +
      '<div class="hh-controls">' +
      '<input class="hh-input" id="hhMmuUrl" value="' + esc(state.baseUrl) + '" placeholder="http://mainsailos.local">' +
      '<button class="hh-btn primary" id="hhMmuConnect">Verbinden</button>' +
      '<button class="hh-btn" id="hhMmuDemo">Demo</button>' +
      '<button class="hh-btn ' + (state.spin ? "hh-spin" : "") + '" id="hhMmuRefresh">?</button>' +
      '</div>' +
      '</div>' +

      '<div class="hh-stats">' +
      '<div class="hh-card hh-stat"><div class="hh-k">MMU Status</div><div class="hh-v small">' + stateChip(d.state || "idle") + '</div><div class="hh-s">Action: ' + esc(d.action || "none") + '</div></div>' +
      '<div class="hh-card hh-stat"><div class="hh-k">Aktiv Gate</div><div class="hh-v">' + (cur >= 0 ? "G" + cur : "-") + '</div><div class="hh-s">Tool: T' + esc(d.tool != null ? d.tool : cur) + '</div></div>' +
      '<div class="hh-card hh-stat"><div class="hh-k">Geladene Gates</div><div class="hh-v">' + loadedCount + '</div><div class="hh-s">Leer: ' + emptyCount + '</div></div>' +
      '<div class="hh-card hh-stat"><div class="hh-k">Gesamtzeit</div><div class="hh-v">' + fmtTime(d.total_time || 0) + '</div><div class="hh-s">Toolchanges: ' + Number(d.total_tool_changes || 0) + '</div></div>' +
      '</div>' +

      '<div class="hh-card hh-gates">' +
      '<div class="hh-gates-head"><span>Gate Deck</span><span>Aktualisiert ' + esc(state.lastUpd) + (state.err ? ' · ' + esc(state.err) : '') + '</span></div>' +
      '<div class="hh-gates-row">' + gatesHtml + '</div>' +
      '</div>' +

      '<div class="hh-bottom">' +
      '<div class="hh-left-stack">' +
      '<div class="hh-card hh-panel">' +
      '<div class="hh-k">Schnell-Steuerung</div>' +
      '<div class="hh-s" style="margin-bottom:6px">Tool wechseln</div>' +
      '<div class="hh-tool-grid">' + toolsHtml + '</div>' +
      '<div class="hh-s" style="margin-bottom:6px">System</div>' +
      '<div class="hh-sys">' +
      '<button class="hh-mini-btn" data-cmd="MMU_HOME" data-label="MMU Home">Home</button>' +
      '<button class="hh-mini-btn" data-cmd="MMU_EJECT" data-label="Filament entladen">Eject</button>' +
      '<button class="hh-mini-btn" data-cmd="MMU_RECOVER" data-label="MMU Recover">Recover</button>' +
      '</div>' +
      '</div>' +

      '<div class="hh-card hh-panel">' +
      '<div class="hh-k">Gate ' + sel + ' Detail</div>' +
      '<div class="hh-detail-list">' +
      '<div>Status: ' + (selStatus === 0 ? 'Leer' : selStatus === 1 ? 'Spule' : 'Unbekannt') + '</div>' +
      '<div>Material: ' + esc(selMat) + '</div>' +
      '<div>Name: ' + esc(selName) + '</div>' +
      '<div>Tool: T' + esc(selTool) + '</div>' +
      '<div>Temperatur: ' + (selTemp > 0 ? selTemp + 'C' : '-') + '</div>' +
      '<div>Spool ID: ' + (selSpool > 0 ? '#' + selSpool : '-') + '</div>' +
      '<div>Speed: ' + selSpeed + '%</div>' +
      '</div>' +
      '<div class="hh-detail-actions">' +
      '<button class="hh-btn" data-cmd="MMU_SELECT GATE=' + sel + '" data-label="Gate auswaehlen">Gate auswaehlen</button>' +
      '<button class="hh-btn" data-cmd="MMU_LOAD GATE=' + sel + '" data-label="Filament laden">Filament laden</button>' +
      '<button class="hh-btn" data-cmd="MMU_GATE_MAP GATE=' + sel + ' AVAILABLE=0" data-label="Als leer markieren">Als leer</button>' +
      '</div>' +
      '</div>' +
      '</div>' +

      '<div class="hh-card hh-log-wrap">' +
      '<div class="hh-log-head"><div class="hh-k">Kommando Log</div><button class="hh-btn" data-log-clear>Loeschen</button></div>' +
      '<div class="hh-log">' + logsHtml + '</div>' +
      '</div>' +
      '</div>' +

      '</div>';

    bind();
  }

  function bind() {
    var elUrl = document.getElementById("hhMmuUrl");
    var elConnect = document.getElementById("hhMmuConnect");
    var elDemo = document.getElementById("hhMmuDemo");
    var elRefresh = document.getElementById("hhMmuRefresh");

    if (elConnect) {
      elConnect.onclick = function () {
        state.baseUrl = (elUrl && elUrl.value ? elUrl.value.trim() : "") || state.baseUrl;
        state.demoMode = false;
        addLog("Moonraker verbinden: " + state.baseUrl);
        poll();
        if (state.timer) clearInterval(state.timer);
        state.timer = setInterval(poll, 2500);
      };
    }

    if (elDemo) {
      elDemo.onclick = function () {
        state.demoMode = true;
        addLog("Demo-Modus aktiviert");
        if (state.timer) clearInterval(state.timer);
        state.timer = setInterval(poll, 2500);
        poll();
      };
    }

    if (elRefresh) {
      elRefresh.onclick = function () { poll(); };
    }

    root.querySelectorAll("[data-gate]").forEach(function (el) {
      el.onclick = function () {
        var idx = Number(el.getAttribute("data-gate"));
        state.selectedGate = idx;
        render();
      };
    });

    root.querySelectorAll("[data-cmd]").forEach(function (el) {
      el.onclick = function () {
        if (el.disabled) return;
        var cmd = el.getAttribute("data-cmd");
        var label = el.getAttribute("data-label") || cmd;
        send(cmd, label);
      };
    });

    var clear = root.querySelector("[data-log-clear]");
    if (clear) {
      clear.onclick = function () {
        state.logs = [];
        render();
      };
    }
  }

  render();
  poll();
  state.timer = setInterval(poll, 2500);
})();
