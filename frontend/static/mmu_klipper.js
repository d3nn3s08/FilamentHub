(function () {
  var root = document.getElementById("hhMmuRoot");
  if (!root) return;

  var state = {
    printers: [],
    selectedPrinter: null,
    ok: false,
    err: "",
    spin: false,
    selectedGate: null,
    logs: [],
    data: null,
    timer: null,
    lastUpd: "-"
  };

  function nowTS() { return new Date().toLocaleTimeString("de-DE"); }

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function stateChip(d) {
    if (!d || !d.enabled) return '<span class="hh-chip" style="color:#9ab4d8">-</span>';
    if (d.is_paused)   return '<span class="hh-chip" style="color:#ff7a7a;border-color:rgba(255,122,122,.35);background:rgba(255,122,122,.08)">Pausiert</span>';
    if (d.is_locked)   return '<span class="hh-chip" style="color:#ff7a7a;border-color:rgba(255,122,122,.35);background:rgba(255,122,122,.08)">Fehler</span>';
    if (d.is_in_print) return '<span class="hh-chip" style="color:#ffc165;border-color:rgba(255,193,101,.35);background:rgba(255,193,101,.08)">Druckt</span>';
    if (d.is_homed)    return '<span class="hh-chip" style="color:#6ae485;border-color:rgba(106,228,133,.35);background:rgba(106,228,133,.08)">Bereit</span>';
    return '<span class="hh-chip" style="color:#9ab4d8">' + esc(d.print_state || "-") + '</span>';
  }

  function addLog(msg, t) {
    state.logs.unshift({ ts: nowTS(), msg: msg, t: t || "info" });
    if (state.logs.length > 80) state.logs = state.logs.slice(0, 80);
  }

  async function loadPrinters() {
    try {
      var res = await fetch("/api/mmu/printers");
      if (!res.ok) throw new Error("HTTP " + res.status);
      var json = await res.json();
      state.printers = json.printers || [];
      var withMmu = state.printers.filter(function (p) { return p.has_mmu || p.mmu_detected; });
      if (withMmu.length === 1 && !state.selectedPrinter) {
        state.selectedPrinter = withMmu[0];
        startPolling();
        return;
      }
    } catch (e) {
      state.err = (e && e.message) || "Fehler beim Laden der Drucker";
    }
    render();
  }

  function startPolling() {
    if (state.timer) clearInterval(state.timer);
    poll();
    state.timer = setInterval(poll, 2500);
  }

  async function poll() {
    if (!state.selectedPrinter) return;
    state.spin = true;
    render();

    var ctrl = new AbortController();
    var tid = setTimeout(function () { ctrl.abort(); }, 3500);

    try {
      var res = await fetch("/api/mmu/" + state.selectedPrinter.printer_id + "/status", { signal: ctrl.signal });
      if (!res.ok) throw new Error("HTTP " + res.status);
      var json = await res.json();
      if (json.status === "pending") {
        state.err = "MMU-Erkennung läuft noch...";
        state.ok = false;
      } else {
        state.data = json;
        state.ok = true;
        state.err = "";
        state.lastUpd = nowTS();
      }
    } catch (e) {
      state.ok = false;
      state.err = (e && e.message) || "Verbindungsfehler";
    } finally {
      clearTimeout(tid);
      state.spin = false;
      render();
    }
  }

  async function send(script, label) {
    if (!state.selectedPrinter) return false;
    addLog("-> " + label);

    var ctrl = new AbortController();
    var tid = setTimeout(function () { ctrl.abort(); }, 5000);

    try {
      var res = await fetch("/api/mmu/" + state.selectedPrinter.printer_id + "/gcode", {
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

  function renderGate(gate, curGate, selected) {
    var status = gate.status != null ? gate.status : -1;
    var color  = gate.color || "#2d3c59";
    var mat    = gate.material || "-";
    var name   = gate.filament_name || "-";
    var temp   = gate.temperature || 0;
    var sid    = gate.spool_id_spoolman != null ? gate.spool_id_spoolman : -1;
    var isActive = gate.gate === curGate;
    var tag = status === 0 ? '<span class="hh-pill empty">Leer</span>' : '<span class="hh-pill ok">Spule</span>';

    return '' +
      '<div class="hh-gate ' + (selected ? "active" : "") + '" data-gate="' + gate.gate + '">' +
      '<div class="hh-gate-top"><div class="hh-gate-name">Gate ' + gate.gate + '</div>' + tag + '</div>' +
      '<div class="hh-spool" style="background:' + (status === 0 ? "#2d3a54" : color) + ';border-color:' + (isActive ? "#f1a45b" : "rgba(255,255,255,.22)") + '"></div>' +
      '<div class="hh-meta">' +
      '<div>Material: <b>' + esc(mat) + '</b></div>' +
      '<div>' + esc(name) + '</div>' +
      '<div class="hh-meta-sub"><span>Spool ' + (sid > 0 ? "#" + sid : "-") + '</span><span>' + (temp > 0 ? temp + "C" : "-") + '</span></div>' +
      '</div>' +
      '</div>';
  }

  function render() {
    var d      = state.data || {};
    var gates  = d.gates || [];
    var n      = state.data ? gates.length : 0;
    var curGate = d.gate != null ? Number(d.gate) : -1;

    if (state.selectedGate != null && state.selectedGate >= n) state.selectedGate = null;
    if (state.data && state.selectedGate == null) {
      state.selectedGate = Math.max(0, Math.min(n - 1, curGate >= 0 ? curGate : 0));
    }

    var emptyCount  = gates.filter(function (g) { return g.status === 0; }).length;
    var loadedCount = n - emptyCount;

    // Printer selector
    var withMmu = state.printers.filter(function (p) { return p.has_mmu || p.mmu_detected; });
    var printerHtml = "";
    if (withMmu.length === 0) {
      printerHtml = '<span style="color:var(--text-dim);font-size:13px">Kein Drucker mit MMU gefunden</span>';
    } else if (withMmu.length === 1) {
      printerHtml = '<span style="color:var(--text-primary);font-size:14px;font-weight:600">' + esc(withMmu[0].printer_name) + '</span>';
    } else {
      var opts = withMmu.map(function (p) {
        var isSel = state.selectedPrinter && state.selectedPrinter.printer_id === p.printer_id ? " selected" : "";
        return '<option value="' + esc(p.printer_id) + '"' + isSel + '>' + esc(p.printer_name) + '</option>';
      }).join("");
      printerHtml = '<select class="hh-input" id="hhMmuPrinterSel">' + opts + '</select>';
    }

    // Gates
    var gatesHtml = "";
    if (n === 0) {
      gatesHtml = '<div style="padding:24px;color:var(--text-dim);font-size:13px;">' +
        (state.selectedPrinter ? "Warte auf MMU-Daten\u2026" : "Drucker ausw\u00e4hlen um Daten zu laden.") + '</div>';
    } else {
      for (var i = 0; i < n; i++) gatesHtml += renderGate(gates[i], curGate, i === state.selectedGate);
    }

    // Selected gate detail
    var sel     = state.selectedGate;
    var selGate = (sel != null && gates[sel]) ? gates[sel] : {};
    var selStatus = selGate.status != null ? selGate.status : -1;
    var selMat    = selGate.material || "-";
    var selName   = selGate.filament_name || "-";
    var selTool   = (d.ttg_map && sel != null && d.ttg_map[sel] != null) ? d.ttg_map[sel] : (sel != null ? sel : "-");
    var selTemp   = selGate.temperature || 0;
    var selSpool  = selGate.spool_id_spoolman != null ? selGate.spool_id_spoolman : -1;
    var selSpeed  = selGate.speed_override != null ? selGate.speed_override : 100;
    var selDis    = sel == null ? "disabled " : "";

    // Tool buttons
    var toolsHtml = "";
    for (var t = 0; t < n; t++) {
      var mapped    = (d.ttg_map && d.ttg_map[t] != null) ? d.ttg_map[t] : t;
      var mGate     = gates[mapped];
      var available = mGate && (mGate.status === 1 || mGate.status === 2);
      var active    = t === Number(d.tool != null ? d.tool : -1);
      toolsHtml += '<button class="hh-tool ' + (active ? "active" : "") + '" ' +
        (available ? "" : "disabled ") +
        'data-cmd="T' + t + '" data-label="T' + t + ' aktivieren">T' + t + '</button>';
    }

    var logsHtml = state.logs.length
      ? state.logs.map(function (l) {
          var c = l.t === "err" ? "#ff7a7a" : l.t === "ok" ? "#6ae485" : "#9eb5d8";
          return '<div class="hh-log-row"><span class="hh-ts">' + esc(l.ts) + '</span><span style="color:' + c + '">' + esc(l.msg) + '</span></div>';
        }).join("")
      : '<div class="hh-log-row"><span class="hh-ts"></span><span>Keine Befehle bisher\u2026</span></div>';

    root.innerHTML = '' +
      '<div class="hh-wrap">' +

      '<div class="hh-card hh-toolbar">' +
      '<div class="hh-title">MMU \u00b7 Happy Hare</div>' +
      '<div class="hh-controls">' + printerHtml +
      '<button class="hh-btn ' + (state.spin ? "hh-spin" : "") + '" id="hhMmuRefresh" ' + (!state.data ? "disabled " : "") + '>&#8635;</button>' +
      '</div>' +
      '</div>' +

      '<div class="hh-stats">' +
      '<div class="hh-card hh-stat"><div class="hh-k">MMU Status</div><div class="hh-v small">' + stateChip(d) + '</div><div class="hh-s">Action: ' + esc(d.action_label || "none") + '</div></div>' +
      '<div class="hh-card hh-stat"><div class="hh-k">Aktiv Gate</div><div class="hh-v">' + (curGate >= 0 ? "G" + curGate : "-") + '</div><div class="hh-s">Tool: T' + esc(d.tool != null ? d.tool : "-") + '</div></div>' +
      '<div class="hh-card hh-stat"><div class="hh-k">Geladene Gates</div><div class="hh-v">' + loadedCount + '</div><div class="hh-s">Leer: ' + emptyCount + '</div></div>' +
      '<div class="hh-card hh-stat"><div class="hh-k">Toolwechsel</div><div class="hh-v">' + Number(d.num_toolchanges || 0) + '</div><div class="hh-s">Homed: ' + (d.is_homed ? "Ja" : "Nein") + '</div></div>' +
      '</div>' +

      '<div class="hh-card hh-gates">' +
      '<div class="hh-gates-head"><span>Gate Deck</span><span>Aktualisiert ' + esc(state.lastUpd) + (state.err ? " \u00b7 " + esc(state.err) : "") + '</span></div>' +
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
      '<div class="hh-k">Gate ' + (sel != null ? sel : "-") + ' Detail</div>' +
      '<div class="hh-detail-list">' +
      '<div>Status: ' + (selStatus === 0 ? "Leer" : selStatus === 1 ? "Spule" : selStatus === 2 ? "Spule (Buffer)" : "Unbekannt") + '</div>' +
      '<div>Material: ' + esc(selMat) + '</div>' +
      '<div>Name: ' + esc(selName) + '</div>' +
      '<div>Tool: T' + esc(selTool) + '</div>' +
      '<div>Temperatur: ' + (selTemp > 0 ? selTemp + "C" : "-") + '</div>' +
      '<div>Spool ID: ' + (selSpool > 0 ? "#" + selSpool : "-") + '</div>' +
      '<div>Speed: ' + selSpeed + '%</div>' +
      '</div>' +
      '<div class="hh-detail-actions">' +
      '<button class="hh-btn" ' + selDis + 'data-cmd="MMU_SELECT GATE=' + sel + '" data-label="Gate auswaehlen">Gate ausw\u00e4hlen</button>' +
      '<button class="hh-btn" ' + selDis + 'data-cmd="MMU_LOAD GATE=' + sel + '" data-label="Filament laden">Filament laden</button>' +
      '<button class="hh-btn" ' + selDis + 'data-cmd="MMU_GATE_MAP GATE=' + sel + ' AVAILABLE=0" data-label="Als leer markieren">Als leer</button>' +
      '</div>' +
      '</div>' +
      '</div>' +

      '<div class="hh-card hh-log-wrap">' +
      '<div class="hh-log-head"><div class="hh-k">Kommando Log</div><button class="hh-btn" data-log-clear>L\u00f6schen</button></div>' +
      '<div class="hh-log">' + logsHtml + '</div>' +
      '</div>' +
      '</div>' +

      '</div>';

    bind();
  }

  function bind() {
    var elPrinterSel = document.getElementById("hhMmuPrinterSel");
    if (elPrinterSel) {
      elPrinterSel.onchange = function () {
        var found = state.printers.find(function (p) { return p.printer_id === elPrinterSel.value; });
        if (found) {
          state.selectedPrinter = found;
          state.data = null;
          state.selectedGate = null;
          startPolling();
        }
      };
    }

    var elRefresh = document.getElementById("hhMmuRefresh");
    if (elRefresh) {
      elRefresh.onclick = function () { poll(); };
    }

    root.querySelectorAll("[data-gate]").forEach(function (el) {
      el.onclick = function () {
        state.selectedGate = Number(el.getAttribute("data-gate"));
        render();
      };
    });

    root.querySelectorAll("[data-cmd]").forEach(function (el) {
      el.onclick = function () {
        if (el.disabled) return;
        send(el.getAttribute("data-cmd"), el.getAttribute("data-label") || el.getAttribute("data-cmd"));
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
  loadPrinters();
})();
