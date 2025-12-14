// Debug Center baseline (System + Performance)
const POLL_MS = 5000;
let systemInterval = null;
let backendInterval = null;
let performanceInterval = null;
let activeTab = 'system';
let scannerInitialized = false;
let scannerSuggestedRange = null;
const runningPortTests = new Set();
window.DEBUG_MODE = 'lite';
let probeTarget = null;

function normalizePrinterType(val) {
  const v = (val || '').toLowerCase();
  if (v.includes('bambu')) return 'bambu';
  if (v.includes('klipper')) return 'klipper';
  return 'generic';
}

function setDebugMode(mode) {
  window.DEBUG_MODE = mode === 'pro' ? 'pro' : 'lite';
  document.body.classList.remove('debug-lite', 'debug-pro');
  document.body.classList.add(window.DEBUG_MODE === 'pro' ? 'debug-pro' : 'debug-lite');
  const btnLite = document.getElementById('debugModeLite');
  const btnPro = document.getElementById('debugModePro');
  const label = document.getElementById('debugModeLabel');
  if (btnLite) btnLite.classList.toggle('active', window.DEBUG_MODE === 'lite');
  if (btnPro) btnPro.classList.toggle('active', window.DEBUG_MODE === 'pro');
  if (label) {
    label.textContent = `Mode: ${window.DEBUG_MODE === 'pro' ? 'Pro' : 'Lite'}`;
    label.classList.remove('mode-lite', 'mode-pro');
    label.classList.add(window.DEBUG_MODE === 'pro' ? 'mode-pro' : 'mode-lite');
  }
  document.querySelectorAll('.pro-only, [data-mode="pro"]').forEach(el => {
    el.style.display = window.DEBUG_MODE === 'pro' ? '' : 'none';
  });
  document.querySelectorAll('.pro-only-inline').forEach(el => {
    el.style.display = window.DEBUG_MODE === 'pro' ? '' : 'none';
  });
  updateProbeButtonState();
}

function initDebugModeUI() {
  const btnLite = document.getElementById('debugModeLite');
  const btnPro = document.getElementById('debugModePro');
  if (btnLite) btnLite.addEventListener('click', () => setDebugMode('lite'));
  if (btnPro) btnPro.addEventListener('click', () => setDebugMode('pro'));
  setDebugMode(window.DEBUG_MODE || 'lite');
}

function $(id) {
  return document.getElementById(id);
}

function setText(id, value, fallback = '-') {
  const el = $(id);
  if (!el) return;
  const safe = value === undefined || value === null || value === '' ? fallback : value;
  el.textContent = safe;
}

function fmtMs(n) {
  return Number.isFinite(n) ? `${n} ms` : '-';
}

function fmtReq(n) {
  return Number.isFinite(n) ? n.toString() : '-';
}

function fmtPercent(n) {
  return Number.isFinite(n) ? `${n}%` : '-';
}

function fmtGB(val) {
  if (!Number.isFinite(val)) return null;
  return `${val} GB`;
}

function fmtUptime(val) {
  const num = Number(val);
  if (Number.isFinite(num)) {
    const total = Math.max(0, Math.floor(num));
    const hours = Math.floor(total / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    const seconds = total % 60;
    return [hours, minutes, seconds].map(v => String(v).padStart(2, '0')).join(':');
  }
  if (typeof val === 'string' && val.trim().length > 0) {
    return val;
  }
  return '-';
}

function setBadgeState(el, state) {
  if (!el) return;
  const level = state || 'idle';
  el.classList.remove('status-ok', 'status-warn', 'status-error', 'status-idle');
  if (level === 'ok') el.classList.add('status-ok');
  else if (level === 'warn') el.classList.add('status-warn');
  else if (level === 'error') el.classList.add('status-error');
  else el.classList.add('status-idle');
  if (level === 'ok') el.textContent = 'OK';
  else if (level === 'warn') el.textContent = 'Warn';
  else if (level === 'error') el.textContent = 'Error';
  else el.textContent = 'Idle';
}

function setStatus(id, state) {
  const el = $(id);
  if (!el) return;
  const val = state || 'offline';
  el.textContent = val;
  el.classList.remove('status-ok', 'status-warn', 'status-error', 'status-idle', 'status-info');
  if (val === 'online' || val === 'connected' || val === 'listening') {
    el.classList.add('status-ok');
  } else if (val === 'disabled') {
    el.classList.add('status-idle');
  } else {
    el.classList.add('status-error');
  }
}

function initTabs() {
  document.querySelectorAll('.debug-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      const target = tab.dataset.tab;
      document.querySelectorAll('.debug-panel').forEach(panel => {
        panel.style.display = panel.id === 'panel-' + target ? '' : 'none';
      });
      document.querySelectorAll('.debug-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      activeTab = target;
      if (activeTab === 'performance') {
        startPerformancePolling();
      } else {
        stopPerformancePolling();
      }
      if (activeTab === 'scanner') {
        initScannerTab();
      }
    });
  });
  const initial = document.querySelector('.debug-tab.active');
  activeTab = initial?.dataset?.tab || 'system';
}

async function loadSystemStatus() {
  try {
    const res = await fetch('/api/system/status');
    if (!res.ok) return;
    const data = await res.json();
    setText('sys_app_name', data?.app?.name || 'FilamentHub');
    setText('sys_app_version', data?.app?.version || '0.0.0');
    setText('sys_app_env', data?.app?.environment || 'development');
    setText('sys_app_uptime', data?.app?.uptime || '0');

    setText('sys_cpu_usage', data?.system?.cpu_percent !== undefined ? data.system.cpu_percent + ' %' : '-');
    setText('sys_cpu_cores', data?.system?.cpu_count !== undefined ? data.system.cpu_count + ' Cores' : 'n/a');
    setText('sys_ram_usage', data?.system?.ram_percent !== undefined ? data.system.ram_percent + ' %' : '-');
    if (data?.system?.ram_used_gb !== undefined && data?.system?.ram_total_gb !== undefined) {
      setText('sys_ram_detail', `${data.system.ram_used_gb} GB / ${data.system.ram_total_gb} GB`);
    } else {
      setText('sys_ram_detail', '-');
    }
    setText('sys_disk_usage', data?.system?.disk_percent !== undefined ? data.system.disk_percent + ' %' : '-');
    if (data?.system?.disk_used_gb !== undefined && data?.system?.disk_total_gb !== undefined) {
      setText('sys_disk_detail', `${data.system.disk_used_gb} GB / ${data.system.disk_total_gb} GB`);
    } else {
      setText('sys_disk_detail', '-');
    }
  } catch (err) {
    // ignore
  }
}

async function loadBackendStatus() {
  console.debug('[debug] loadBackendStatus tick', new Date().toISOString());
  try {
    const res = await fetch('/api/debug/system_status');
    if (!res.ok) return;
    const data = await res.json();
    console.debug('[debug] system_status runtime', data?.runtime);
    const rt = data?.runtime || {};
    const stateRaw = (rt.state || 'idle').toString().toLowerCase();
    const state = stateRaw === 'active' ? 'active' : 'idle';
    setStatus('apiStatus', data?.api?.state || 'offline');
    setStatus('dbStatus', data?.db?.state || 'offline');
    setStatus('mqttStatus', data?.mqtt?.state || 'offline');
    setStatus('wsStatus', data?.websocket?.state || 'offline');
    const clients = data?.websocket?.clients || 0;
    setText('wsClients', clients ? `(${clients} clients)` : '');
    renderSystemHealth({
      api: data?.api?.state,
      db: data?.db?.state,
      mqtt: data?.mqtt?.state,
      ws: data?.websocket?.state,
      wsClients: clients,
      runtimeState: state,
      runtimeAvgMs: rt.avg_response_ms,
      systemHealth: data?.system_health,
    });

    const badges = document.querySelectorAll('#sys_runtime_state');
    console.debug('[debug] runtime state resolved', state, 'rpm', rt?.requests_per_minute, 'avg', rt?.avg_response_ms);
    const isActive = state === 'active';
    if (badges.length > 0) {
      badges.forEach(badge => {
        badge.textContent = isActive ? 'ACTIVE' : 'IDLE';
        badge.classList.remove('status-ok', 'status-warn', 'status-error', 'status-idle');
        badge.classList.add(isActive ? 'status-ok' : 'status-idle');
      });
    } else {
      console.warn('[runtime] sys_runtime_state not found in DOM');
    }
    setText(
      'sys_runtime_rpm',
      (isActive && typeof rt.requests_per_minute === 'number')
        ? Math.round(rt.requests_per_minute)
        : '-'
    );
    setText(
      'sys_runtime_avg',
      (isActive && typeof rt.avg_response_ms === 'number')
        ? `${rt.avg_response_ms.toFixed(2)} ms`
        : '-'
    );
  } catch (err) {
    // ignore
  }
}

async function fetchPerformanceData() {
  try {
    const res = await fetch('/api/debug/performance');
    if (!res.ok) return null;
    return await res.json();
  } catch (err) {
    return null;
  }
}

function classifyPercent(n) {
  if (!Number.isFinite(n)) return 'idle';
  if (n >= 90) return 'error';
  if (n >= 75) return 'warn';
  return 'ok';
}

function showPerfError() {
  const loading = $('perfLoading');
  const err = $('perfError');
  if (loading) loading.style.display = 'none';
  if (err) err.style.display = '';
  setText('perfCpuValue', '-');
  setText('perfCpuSub', '-');
  setText('perfRamValue', '-');
  setText('perfRamSub', '-');
  setText('perfDiskValue', '-');
  setText('perfDiskSub', '-');
  setText('perfUptimeValue', '-');
  setText('perfUptimeSub', '-');
  setBadgeState($('#perfCpuBadge'), 'idle');
  setBadgeState($('#perfRamBadge'), 'idle');
  setBadgeState($('#perfDiskBadge'), 'idle');
  setBadgeState($('#perfUptimeBadge'), 'idle');
}

function setTestBadge(badge, status, text) {
  if (!badge) return;
  badge.textContent = text || '--';
  badge.classList.remove('status-ok', 'status-warn', 'status-error', 'status-idle', 'badge-ok', 'badge-error', 'badge-warn', 'badge-idle', 'badge-testing', 'badge-failed');
  if (status === 'ok') {
    badge.classList.add('badge', 'badge-ok');
  } else if (status === 'testing') {
    badge.classList.add('badge', 'badge-testing');
  } else if (status === 'fail' || status === 'failed') {
    badge.classList.add('badge', 'badge-failed');
  } else if (status === 'warn') {
    badge.classList.add('badge', 'badge-warn');
  } else {
    badge.classList.add('badge', 'badge-idle');
  }
}

function setScannerStatus(cardEl, state, text, detailText) {
  if (!cardEl) return;
  const badge = cardEl.querySelector('[data-role="statusBadge"]');
  const result = cardEl.querySelector('[data-role="portResult"]');
  if (badge) {
    badge.classList.remove('badge-idle', 'badge-testing', 'badge-ok', 'badge-failed');
    if (state === 'testing') badge.classList.add('badge-testing');
    else if (state === 'ok') badge.classList.add('badge-ok');
    else if (state === 'failed') badge.classList.add('badge-failed');
    else badge.classList.add('badge-idle');
    badge.textContent = text || '--';
  }
  if (result) result.textContent = detailText || '--';
}

async function loadPerformanceLite() {
  const loading = $('perfLoading');
  const err = $('perfError');
  if (err) err.style.display = 'none';
  if (loading) loading.style.display = '';
  try {
    const data = await fetchPerformanceData();
    if (!data) {
      showPerfError();
      console.warn('Performance data not available');
      return;
    }
    const cpu = Number(data.cpu_percent);
    const ramUsedMb = Number(data.ram_used_mb);
    const ramTotalMb = Number(data.ram_total_mb);
    const diskUsedGb = Number(data.disk_used_gb);
    const diskTotalGb = Number(data.disk_total_gb);
    const uptimeSeconds = Number(data.backend_uptime_s);
    if (loading) loading.style.display = 'none';
    if (err) err.style.display = 'none';

    setText('perfCpuValue', fmtPercent(cpu));
    setText('perfCpuSub', '-');
    setBadgeState($('#perfCpuBadge'), classifyPercent(cpu));

    const ramPercent = Number.isFinite(ramUsedMb) && Number.isFinite(ramTotalMb) && ramTotalMb > 0
      ? Math.round((ramUsedMb / ramTotalMb) * 100)
      : null;
    setText('perfRamValue', ramPercent !== null ? fmtPercent(ramPercent) : '-');
    const ramDetail = Number.isFinite(ramUsedMb) && Number.isFinite(ramTotalMb)
      ? `${ramUsedMb} MB / ${ramTotalMb} MB`
      : '-';
    setText('perfRamSub', ramDetail);
    setBadgeState($('#perfRamBadge'), classifyPercent(ramPercent));

    const diskPercent = Number.isFinite(diskUsedGb) && Number.isFinite(diskTotalGb) && diskTotalGb > 0
      ? Math.round((diskUsedGb / diskTotalGb) * 100)
      : null;
    setText('perfDiskValue', diskPercent !== null ? fmtPercent(diskPercent) : '-');
    const diskDetail = Number.isFinite(diskUsedGb) && Number.isFinite(diskTotalGb)
      ? `${diskUsedGb} GB / ${diskTotalGb} GB`
      : '-';
    setText('perfDiskSub', diskDetail);
    setBadgeState($('#perfDiskBadge'), classifyPercent(diskPercent));

    const uptimeText = fmtUptime(uptimeSeconds);
    setText('perfUptimeValue', uptimeText);
    setText('perfUptimeSub', uptimeText === '-' ? '-' : 'backend uptime');
    setBadgeState($('#perfUptimeBadge'), uptimeText === '-' ? 'idle' : 'ok');
  } catch (err) {
    showPerfError();
    console.warn('Performance data not available', err);
  }
}

function renderScannerEmpty(message) {
  const list = $('scannerResults');
  if (!list) return;
  list.innerHTML = '';
  const empty = document.createElement('div');
  empty.className = 'badge badge-idle';
  empty.textContent = message || 'No printers detected';
  list.appendChild(empty);
}

function renderScannerResults(printers) {
  const list = $('scannerResults');
  if (!list) return;
  list.innerHTML = '';
  // Reset Probe-Ziel bis ein erfolgreicher Port-Test gelaufen ist
  probeTarget = null;
  updateProbeButtonState();
  if (!Array.isArray(printers) || printers.length === 0) {
    renderScannerEmpty('No printers detected');
    return;
  }
  printers.forEach(pr => {
    const card = document.createElement('div');
    card.className = 'scanner-card';
    const iconChar = pr.type === 'bambu' ? '[B]' : pr.type === 'klipper' ? '[K]' : '[P]';
    const typeText = pr.type || 'generic';
    const baseType = normalizePrinterType(typeText);
    const portVal = pr.port || 6000;
    const status = pr.status || (pr.accessible ? 'reachable' : 'idle');
    const statusLabel = status === 'reachable' ? 'ONLINE' : status === 'offline' ? 'OFFLINE' : 'IDLE';
    card.innerHTML = `
      <div class="sc-left">
        <div class="sc-avatar">${iconChar}</div>
      </div>
      <div class="sc-main">
        <div class="sc-title">${pr.ip || '--'}</div>
        <div class="sc-meta">Typ: ${typeText} | Port ${portVal}</div>
      </div>
      <div class="sc-right">
        <span class="badge ${status === 'reachable' ? 'badge-ok' : status === 'offline' ? 'badge-failed' : 'badge-idle'} sc-status" data-role="statusBadge">${statusLabel}</span>
        <div class="sc-actions">
          <button class="btn btn-secondary" data-action="testPort" data-ip="${pr.ip || ''}" data-port="${portVal}">Test</button>
          <button class="btn btn-primary sc-add disabled btn-add-disabled" data-action="addPrinter" data-ip="${pr.ip || ''}" data-port="${portVal}" data-type="${baseType}" disabled title="Port-Test erforderlich">Zum System</button>
        </div>
        <div class="sc-sub"><span class="sc-port-result" data-role="portResult">--</span><span class="sc-save-info" data-role="saveInfo"></span></div>
      </div>
    `;
    const testBtn = card.querySelector('[data-action="testPort"]');
    const addBtn = card.querySelector('[data-action="addPrinter"]');
    if (testBtn) {
      testBtn.addEventListener('click', () => handlePortTest(testBtn, card, pr.ip || '--', portVal));
    }
    if (addBtn) {
      addBtn.addEventListener('click', () => handleAddPrinter(addBtn, card));
    }
    list.appendChild(card);
  });
}

async function loadNetworkInfo() {
  try {
    const res = await fetch('/api/debug/network');
    if (!res.ok) {
      renderScannerEmpty('No printers detected');
      return;
    }
    const data = await res.json();
    setText('netHostname', data?.hostname || '-');
    setText('netLocalIp', data?.local_ip || '-');
    setText('netSuggestedRange', data?.suggested_range || '-');
    scannerSuggestedRange = data?.suggested_range || null;
  } catch (err) {
    renderScannerEmpty('No printers detected');
  }
}

async function handleQuickScanClick() {
  const btn = $('scannerQuickScan');
  if (btn) {
    btn.disabled = true;
    btn.textContent = 'Scanning...';
    btn.classList.add('btn-loading');
  }
  if (!scannerSuggestedRange) {
    renderScannerEmpty('Network range not available');
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Quick Scan (LAN)';
      btn.classList.remove('btn-loading');
    }
    return;
  }
  try {
    renderScannerEmpty('Scanning...');
    const res = await fetch('/api/scanner/scan/quick');
    if (!res.ok) {
      renderScannerEmpty('No printers detected');
    } else {
      const data = await res.json();
      const printers = data?.printers || [];
      renderScannerResults(printers);
    }
  } catch (err) {
    renderScannerEmpty('No printers detected');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Quick Scan (LAN)';
      btn.classList.remove('btn-loading');
    }
  }
}

function updateProbeUI(data) {
  const statusEl = document.getElementById('proProbeStatus');
  const latencyEl = document.getElementById('proProbeLatency');
  const typeEl = document.getElementById('proProbeType');
  const msgEl = document.getElementById('proProbeMessage');
  const errEl = document.getElementById('proProbeError');
  const httpEl = document.getElementById('proProbeHttp');
  const badgeEl = document.getElementById('proProbeBadge');
  const statusText = data?.status || 'Unbekannt';
  if (statusEl) statusEl.textContent = 'Status: ' + statusText;
  const latencyText = Number.isFinite(data?.latency_ms) ? 'Antwortzeit: ' + data.latency_ms + ' ms' : 'Antwortzeit: -';
  if (latencyEl) latencyEl.textContent = latencyText;
  if (typeEl) typeEl.textContent = 'Erkannt: ' + (data?.detected_type || '-');
  const errorClass = (data?.error_class || '').toString().trim().toLowerCase();
  const normalizedStatus = (data?.status || '').toString().toUpperCase();
  const httpVal = data?.http_status;
  let httpLabel = '-';
  let httpCode = null;
  if (httpVal !== null && httpVal !== undefined && httpVal !== '') {
    const code = Number(httpVal);
    if (Number.isFinite(code)) {
      httpCode = code;
      const desc =
        code === 200 ? 'Anfrage erfolgreich, Daten werden geliefert' :
        code === 401 ? 'Authentifizierung fehlt oder falsch' :
        code === 404 ? 'Endpunkt existiert nicht' :
        code === 500 ? 'Interner Fehler am Drucker' : '';
      httpLabel = desc ? `${code} (${desc})` : String(code);
    } else {
      httpLabel = String(httpVal);
    }
  }
  // Fehlerklasse-Logik:
  // 1) Wenn HTTP-Code vorhanden:
  //    - 200 -> OK
  //    - alles andere -> WARNUNG
  // 2) Wenn kein HTTP-Code:
  //    - Status != OK -> ERROR
  //    - sonst -> OK
  let errorLabel = 'OK';
  if (httpCode !== null) {
    errorLabel = httpCode === 200 ? 'OK' : 'WARNUNG';
  } else if (normalizedStatus !== 'OK') {
    errorLabel = 'ERROR';
  }
  if (errEl) errEl.textContent = 'Fehlerklasse: ' + errorLabel;
  if (httpLabel === '-' && normalizedStatus === 'OK') {
    httpLabel = '200 (Anfrage erfolgreich, Daten werden geliefert)';
  }
  if (httpEl) httpEl.textContent = 'HTTP-Status: ' + httpLabel;
  const hint = data?.message || (Array.isArray(data?.details) && data.details.length ? data.details[0] : '-');
  if (msgEl) msgEl.textContent = 'Hinweis: ' + hint;
  if (badgeEl) {
    badgeEl.classList.remove('status-ok', 'status-warn', 'status-error', 'status-idle');
    let level = 'status-idle';
    const normalized = (data?.status || '').toString().toUpperCase();
    if (normalized === 'OK') level = 'status-ok';
    else if (normalized === 'WARNUNG' || normalized === 'WARNING') level = 'status-warn';
    else if (normalized === 'FEHLER' || normalized === 'ERROR') level = 'status-error';
    badgeEl.classList.add(level);
    badgeEl.textContent = normalized || 'IDLE';
  }
}

function updateProbeButtonState() {
  const probeBtn = document.getElementById('proProbeStart');
  const fpBtn = document.getElementById('proFingerprintStart');
  const enabled = document.body.classList.contains('debug-pro') && probeTarget && probeTarget.ip;
  if (probeBtn) {
    probeBtn.disabled = !enabled;
    probeBtn.title = enabled ? '' : 'Probe nur im Pro-Modus nach Port-Test verfuegbar';
  }
  if (fpBtn) {
    fpBtn.disabled = !enabled;
    fpBtn.title = enabled ? '' : 'Fingerprint erfordert erfolgreichen Port-Test';
  }
}

function findFirstScannerTarget() {
  const card = document.querySelector('.scanner-card');
  if (!card) return null;
  const testBtn = card.querySelector('[data-action="testPort"]');
  if (testBtn) {
    const ip = testBtn.dataset.ip;
    const port = Number(testBtn.dataset.port || 0) || null;
    if (ip) {
      return { ip, port: port || 6000 };
    }
  }
  return null;
}

async function handleProbe(btn) {
  if (!btn) return;
  if (!document.body.classList.contains('debug-pro')) return;
  let target = probeTarget;
  if (!target) {
    target = findFirstScannerTarget();
    if (target) {
      probeTarget = target;
      updateProbeButtonState();
    }
  }
  if (!target || !target.ip) {
    updateProbeUI({ status: 'FEHLER', message: 'Kein Ziel fuer Probe gesetzt', detected_type: '-', latency_ms: null });
    return;
  }
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Probe laeuft...';
  updateProbeUI({ status: 'LAEUFT', latency_ms: null, detected_type: '-', message: 'Probe laeuft...' });
  try {
    const res = await fetch('/api/debug/printer/probe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ host: target.ip, port: Number(target.port) || 6000 }),
    });
    if (!res.ok) {
      updateProbeUI({ status: 'FEHLER', latency_ms: null, detected_type: '-', message: 'Probe fehlgeschlagen' });
      return;
    }
    const data = await res.json();
    console.debug('[probe] response', data);
    updateProbeUI(data);
  } catch (err) {
    updateProbeUI({ status: 'FEHLER', latency_ms: null, detected_type: '-', message: 'Probe fehlgeschlagen' });
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}

function updateFingerprintUI(data) {
  const statusEl = document.getElementById('proFingerprintStatus');
  const typeEl = document.getElementById('proFingerprintType');
  const confEl = document.getElementById('proFingerprintConfidence');
  const portsEl = document.getElementById('proFingerprintPorts');
  const statusText = data?.status || 'Unbekannt';
  if (statusEl) statusEl.textContent = 'Status: ' + statusText;
  if (typeEl) typeEl.textContent = 'Erkannt: ' + (data?.detected_type || '-');
  if (confEl) confEl.textContent = 'Vertrauensgrad: ' + (data?.confidence != null ? data.confidence + '%' : '-');
  if (portsEl) {
    portsEl.innerHTML = '';
    const ports = data?.ports && typeof data.ports === 'object' ? data.ports : {};
    const keys = Object.keys(ports);
    if (!keys.length) {
      const li = document.createElement('li');
      li.textContent = '-';
      portsEl.appendChild(li);
    } else {
      keys.forEach(k => {
        const info = ports[k] || {};
        const reach = info.reachable === true ? 'reachable' : info.reachable === false ? 'not reachable' : '-';
        const err = info.error_class || '-';
        const msg = info.message || '';
        const lat = Number.isFinite(info.latency_ms) ? ` (${info.latency_ms} ms)` : '';
        const li = document.createElement('li');
        li.textContent = `Port ${k}: ${reach}${lat}${msg ? ' - ' + msg : ''} [${err}]`;
        portsEl.appendChild(li);
      });
    }
  }
}

async function handleFingerprint(btn) {
  if (!btn) return;
  if (!document.body.classList.contains('debug-pro')) return;
  let target = probeTarget || findFirstScannerTarget();
  if (target) {
    probeTarget = target;
    updateProbeButtonState();
  }
  if (!target || !target.ip) {
    updateFingerprintUI({ status: 'FEHLER', detected_type: '-', confidence: null, ports: {}, message: 'Kein Ziel fuer Fingerprint gesetzt' });
    return;
  }
  const original = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Fingerprint laeuft...';
  updateFingerprintUI({ status: 'LAEUFT', detected_type: '-', confidence: null, ports: {}, message: 'Fingerprint laeuft...' });
  try {
    console.debug('[fingerprint] target', target);
    const res = await fetch('/api/debug/printer/fingerprint', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      // host reicht; ohne port prueft der Endpoint automatisch 8883/6000/7125
      body: JSON.stringify({ host: target.ip }),
    });
    if (!res.ok) {
      updateFingerprintUI({ status: 'FEHLER', detected_type: '-', confidence: null, ports: {}, message: 'Fingerprint fehlgeschlagen' });
      return;
    }
    const data = await res.json();
    updateFingerprintUI(data);
  } catch (err) {
    updateFingerprintUI({ status: 'FEHLER', detected_type: '-', confidence: null, ports: {}, message: 'Fingerprint fehlgeschlagen' });
  } finally {
    btn.disabled = false;
    btn.textContent = original;
  }
}

async function handlePortTest(btn, card, ip, port) {
  if (!btn || !card || !ip) return;
  const key = `${ip}-${port}`;
  if (runningPortTests.has(key)) return;
  runningPortTests.add(key);
  btn.disabled = true;
  btn.textContent = 'Teste...';
  setScannerStatus(card, 'testing', 'TESTING', `Port ${port}: testing...`);
  const addBtn = card.querySelector('[data-action="addPrinter"]');
  try {
    const res = await fetch('/api/debug/printer/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        ip,
        port: Number(port) || 6000,
        timeout_ms: 1500,
      }),
    });
    if (!res.ok) {
      setScannerStatus(card, 'failed', 'FAIL', `Port ${port}: error`);
      if (addBtn) {
        addBtn.disabled = true;
        addBtn.classList.add('btn-add-disabled', 'disabled');
        addBtn.classList.remove('btn-add-active');
        addBtn.title = 'Port-Test erforderlich';
      }
      return;
    }
    const data = await res.json();
    const reachable = data?.reachable === true;
    const latency = Number(data?.latency_ms);
    if (reachable) {
      const latText = Number.isFinite(latency) ? ` (${latency} ms)` : '';
      setScannerStatus(card, 'ok', 'OK', `Port ${port}: OK${latText}`);
      probeTarget = { ip, port: Number(port) || 6000 };
      updateProbeButtonState();
      if (addBtn) {
        addBtn.disabled = false;
        addBtn.classList.remove('btn-add-disabled', 'disabled');
        addBtn.classList.add('btn-add-active');
        addBtn.title = '';
      }
    } else {
      const reason = data?.error || 'fail';
      setScannerStatus(card, 'failed', 'FAIL', `Port ${port}: ${reason}`);
      if (addBtn) {
        addBtn.disabled = true;
        addBtn.classList.add('btn-add-disabled', 'disabled');
        addBtn.classList.remove('btn-add-active');
        addBtn.title = 'Port-Test erforderlich';
      }
    }
  } catch (err) {
    setScannerStatus(card, 'failed', 'FAIL', `Port ${port}: error`);
    if (addBtn) {
      addBtn.disabled = true;
      addBtn.classList.add('btn-add-disabled', 'disabled');
      addBtn.classList.remove('btn-add-active');
      addBtn.title = 'Port-Test erforderlich';
    }
  } finally {
    btn.disabled = false;
    btn.textContent = 'Test';
    runningPortTests.delete(key);
  }
}

async function handleAddPrinter(btn, card) {
  if (!btn || !card) return;
  const ip = btn.dataset.ip;
  const port = Number(btn.dataset.port || 6000);
  const baseType = normalizePrinterType(btn.dataset.type || 'generic');
  const saveInfo = card.querySelector('[data-role="saveInfo"]');
  if (!ip) return;
  btn.disabled = true;
  btn.textContent = 'Speichere...';
  try {
    const payload = {
      name: `${baseType}-${ip}`,
      printer_type: baseType,
      ip_address: ip,
      port,
      model: "Lite",
      mqtt_version: "311",
      active: true
    };
    const res = await fetch('/api/printers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json().catch(() => ({}));
    if (data?.status === 'exists') {
      btn.classList.add('btn-add-disabled', 'disabled');
      btn.classList.remove('btn-add-active');
      btn.disabled = true;
      if (saveInfo) saveInfo.textContent = 'Bereits im System vorhanden';
      setScannerStatus(card, 'ok', 'OK', 'info');
      return;
    }
    if (res.ok) {
      btn.classList.remove('btn-add-disabled', 'disabled');
      btn.classList.add('btn-add-active');
      btn.disabled = true;
      btn.title = '';
      if (saveInfo) saveInfo.textContent = 'Gespeichert';
      setScannerStatus(card, 'ok', 'OK', `Port ${port}: OK`);
    } else {
      btn.disabled = false;
      btn.textContent = 'Zum System';
      if (saveInfo) saveInfo.textContent = 'Fehler beim Speichern';
      setScannerStatus(card, 'failed', 'FAIL', `Port ${port}: error`);
    }
  } catch (err) {
    btn.disabled = false;
    btn.textContent = 'Zum System';
    if (saveInfo) saveInfo.textContent = 'Fehler beim Speichern';
    setScannerStatus(card, 'failed', 'FAIL', `Port ${port}: error`);
  }
}

function initScannerTab() {
  if (scannerInitialized) return;
  const btn = $('scannerQuickScan');
  if (btn) {
    btn.addEventListener('click', handleQuickScanClick);
  }
  renderScannerEmpty('No printers detected');
  loadNetworkInfo();
  scannerInitialized = true;
}

function renderSystemHealth(statusData) {
  const badges = document.querySelectorAll('#healthBadge');
  const texts = document.querySelectorAll('#healthText');
  const reasonsEl = document.getElementById('healthReasons');
  const whyBadge = document.getElementById('whyBadgePro');
  const whyList = document.getElementById('whyReasonsPro');
  const setHealth = (id, ok, warn) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = ok ? 'OK' : 'Attention';
    el.classList.remove('health-ok', 'health-warn', 'health-bad');
    if (ok) el.classList.add('health-ok');
    else if (warn) el.classList.add('health-warn');
    else el.classList.add('health-bad');
  };
  if (!badges.length || !texts.length) {
    console.warn('[health] healthBadge or healthText not found in DOM');
    return;
  }
  const applyClass = (el, level) => {
    el.classList.remove('status-ok', 'status-warn', 'status-error', 'status-idle');
    if (level === 'ok') el.classList.add('status-ok');
    else if (level === 'critical') el.classList.add('status-error');
    else el.classList.add('status-warn');
  };
  // ensure text has no status classes
  texts.forEach(t => t.classList.remove('status-ok', 'status-warn', 'status-error', 'status-idle'));
  const api = (statusData?.api || '').toLowerCase();
  const db = (statusData?.db || '').toLowerCase();
  const ws = (statusData?.ws || '').toLowerCase();
  const mqtt = (statusData?.mqtt || '').toLowerCase();

  const sysHealth = statusData?.systemHealth || {};
  let level = sysHealth.status || 'warning';
  const textMap = {
    ok: 'All core services operational',
    warning: 'Warning due to service status or response time.',
    critical: 'Critical system services unavailable',
  };
  let reasons = Array.isArray(sysHealth.reasons) ? sysHealth.reasons.filter(Boolean) : [];
  if (!statusData?.systemHealth) {
    const avgMs = Number(statusData?.runtimeAvgMs);
    const wsClients = Number(statusData?.wsClients);
    if (Number.isFinite(avgMs) && avgMs >= 600) {
      reasons.push(`High average response time (${Math.round(avgMs)} ms)`);
    }
    if (mqtt === 'disabled') {
      reasons.push('MQTT service is disabled');
    }
    if (ws === 'listening' && (!Number.isFinite(wsClients) || wsClients === 0)) {
      reasons.push('WebSocket has no active clients');
    }
    if (db === 'disconnected' || db === 'offline') {
      reasons.push('Database is not connected');
    }
    level = reasons.length ? 'warning' : 'ok';
  }
  if (level === 'warning' && !reasons.length) {
    reasons = ['Some services require attention'];
  }
  if (level === 'ok' && !reasons.length) {
    reasons = ['System is operating normally'];
  }

  badges.forEach(b => {
    applyClass(b, level);
    b.textContent = level === 'ok' ? 'OK' : level === 'critical' ? 'Critical' : 'Warning';
  });
  texts.forEach(t => {
    t.textContent = level === 'warning' && reasons.length ? reasons[0] : (textMap[level] || textMap.warning);
  });

  // Mirror to pro detail placeholders
  setText('proApiStatus', statusData?.api || '-');
  setText('proDbStatus', statusData?.db || '-');
  setText('proWsStatus', statusData?.ws || '-');
  setText('proMqttStatus', statusData?.mqtt || '-');

  if (whyBadge && whyList) {
    whyBadge.classList.remove('status-ok', 'status-warn', 'status-error', 'status-idle');
    if (level === 'ok') whyBadge.classList.add('status-ok');
    else if (level === 'critical') whyBadge.classList.add('status-error');
    else whyBadge.classList.add('status-warn');

    whyList.innerHTML = '';
    let whyReasons = Array.isArray(reasons) ? [...reasons] : [];
    if (level === 'ok') {
      if (!whyReasons.length || whyReasons[0] === 'System is operating normally') {
        whyReasons = ['Keine Warnungen aktiv.'];
      }
    } else {
      if (!whyReasons.length) {
        whyReasons = ['Warnung aktiv, Ursache nicht ermittelt.'];
      }
    }
    whyReasons.forEach(msg => {
      const li = document.createElement('li');
      li.textContent = msg;
      whyList.appendChild(li);
    });
  }

  if (reasonsEl) {
    reasonsEl.innerHTML = '';
    reasons.forEach(msg => {
      const li = document.createElement('li');
      li.textContent = msg;
      reasonsEl.appendChild(li);
    });
    reasonsEl.style.display = document.body.classList.contains('debug-pro') ? '' : 'none';
  }
}

function startPolling() {
  loadSystemStatus();
  loadBackendStatus();
  if (systemInterval) clearInterval(systemInterval);
  if (backendInterval) clearInterval(backendInterval);
  systemInterval = setInterval(loadSystemStatus, POLL_MS);
  backendInterval = setInterval(loadBackendStatus, POLL_MS);
}

function startPerformancePolling() {
  stopPerformancePolling();
  loadPerformanceLite();
  performanceInterval = setInterval(loadPerformanceLite, POLL_MS);
}

function stopPerformancePolling() {
  if (performanceInterval) {
    clearInterval(performanceInterval);
    performanceInterval = null;
  }
}

document.addEventListener('DOMContentLoaded', () => {
  initDebugModeUI();
  initTabs();
  startPolling();
  const probeBtn = document.getElementById('proProbeStart');
  if (probeBtn) {
    probeBtn.addEventListener('click', () => handleProbe(probeBtn));
    updateProbeButtonState();
  }
  const fpBtn = document.getElementById('proFingerprintStart');
  if (fpBtn) {
    fpBtn.addEventListener('click', () => handleFingerprint(fpBtn));
    updateProbeButtonState();
  }
  if (activeTab === 'performance') {
    startPerformancePolling();
  }
  if (activeTab === 'scanner') {
    initScannerTab();
  }
});
