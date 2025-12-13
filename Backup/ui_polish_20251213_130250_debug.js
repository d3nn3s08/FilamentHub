// Debug Center baseline (System + Performance)
const POLL_MS = 5000;
let systemInterval = null;
let backendInterval = null;
let performanceInterval = null;
let activeTab = 'system';
let scannerInitialized = false;
let scannerSuggestedRange = null;
const runningPortTests = new Set();

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
  try {
    const res = await fetch('/api/debug/system_status');
    if (!res.ok) return;
    const data = await res.json();
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
    });

    const runtimeState = data?.runtime?.state;
    const req = Number(data?.runtime?.requests_per_minute);
    const avg = Number(data?.runtime?.avg_response_ms);
    const badge = $('#sys_runtime_state');
    if (badge) {
      const isActive = runtimeState === 'active';
      badge.textContent = isActive ? 'Active' : 'Idle';
      badge.classList.remove('status-ok', 'status-warn', 'status-error', 'status-idle');
      badge.classList.add(isActive ? 'status-ok' : 'status-idle');
    }
    if (runtimeState === 'active') {
      setText('sys_runtime_rpm', fmtReq(req));
      setText('sys_runtime_avg', fmtMs(avg));
    } else {
      setText('sys_runtime_rpm', '-');
      setText('sys_runtime_avg', '-');
      if (badge) {
        badge.textContent = 'Idle';
        badge.classList.remove('status-ok', 'status-warn', 'status-error', 'status-idle');
        badge.classList.add('status-idle');
      }
    }
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
  badge.classList.remove('status-ok', 'status-warn', 'status-error', 'status-idle');
  if (status === 'ok') {
    badge.classList.add('status-ok');
  } else if (status === 'fail') {
    badge.classList.add('status-error');
  } else if (status === 'warn') {
    badge.classList.add('status-warn');
  } else {
    badge.classList.add('status-idle');
  }
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
  empty.className = 'status-badge status-idle';
  empty.textContent = message || 'No printers detected';
  list.appendChild(empty);
}

function renderScannerResults(printers) {
  const list = $('scannerResults');
  if (!list) return;
  list.innerHTML = '';
  if (!Array.isArray(printers) || printers.length === 0) {
    renderScannerEmpty('No printers detected');
    return;
  }
  printers.forEach(pr => {
    const card = document.createElement('div');
    card.style.display = 'flex';
    card.style.flexDirection = 'column';
    card.style.gap = '8px';
    card.style.padding = '10px 12px';
    card.style.border = '1px solid rgba(255,255,255,0.08)';
    card.style.borderRadius = '10px';
    card.style.background = 'rgba(255,255,255,0.03)';

    const header = document.createElement('div');
    header.style.display = 'flex';
    header.style.alignItems = 'center';
    header.style.gap = '10px';

    const ipBlock = document.createElement('div');
    ipBlock.style.display = 'flex';
    ipBlock.style.flexDirection = 'column';
    ipBlock.style.gap = '2px';

    const ipLine = document.createElement('div');
    ipLine.textContent = pr.ip || '-';
    ipLine.style.fontWeight = '700';

    const info = document.createElement('div');
    info.style.color = 'var(--text-dim, #a7b2c3)';
    const typeText = pr.type || 'generic';
    const portText = pr.port ? `:${pr.port}` : '';
    info.textContent = `Typ: ${typeText}${portText}`;
    ipBlock.appendChild(ipLine);
    ipBlock.appendChild(info);
    header.appendChild(ipBlock);

    const badge = document.createElement('span');
    badge.classList.add('status-badge');
    const status = pr.status || (pr.accessible ? 'reachable' : 'idle');
    if (status === 'reachable') {
      badge.classList.add('status-ok');
    } else if (status === 'offline') {
      badge.classList.add('status-error');
    } else {
      badge.classList.add('status-idle');
    }
    badge.textContent = status;
    badge.style.marginLeft = 'auto';
    header.appendChild(badge);

    card.appendChild(header);

    const actions = document.createElement('div');
    actions.style.display = 'flex';
    actions.style.alignItems = 'center';
    actions.style.gap = '10px';
    actions.style.flexWrap = 'wrap';

    const testBadge = document.createElement('span');
    testBadge.className = 'status-badge status-idle';
    testBadge.textContent = '--';

    const testBtn = document.createElement('button');
    testBtn.textContent = 'Test (Port 6000)';
    testBtn.style.padding = '6px 10px';
    testBtn.style.borderRadius = '8px';
    testBtn.style.border = '1px solid rgba(255,255,255,0.15)';
    testBtn.style.background = 'rgba(255,255,255,0.05)';
    testBtn.style.color = '#fff';
    testBtn.dataset.ip = pr.ip || '';

    const addBtn = document.createElement('button');
    addBtn.textContent = 'Zum System hinzufuegen';
    addBtn.disabled = true;
    addBtn.style.padding = '6px 10px';
    addBtn.style.borderRadius = '8px';
    addBtn.style.border = '1px solid rgba(255,255,255,0.15)';
    addBtn.style.background = 'rgba(255,255,255,0.02)';
    addBtn.style.color = '#fff';

    const saveInfo = document.createElement('span');
    saveInfo.style.color = 'var(--text-dim, #a7b2c3)';
    saveInfo.style.fontSize = '0.9rem';

    testBtn.addEventListener('click', () => {
      handlePortTest(testBtn, testBadge, addBtn, pr.ip || '-', 6000);
    });

    addBtn.addEventListener('click', () => {
      saveInfo.textContent = 'Save kommt spaeter';
    });

    actions.appendChild(testBadge);
    actions.appendChild(testBtn);
    actions.appendChild(addBtn);
    actions.appendChild(saveInfo);

    card.appendChild(actions);

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
  }
  if (!scannerSuggestedRange) {
    renderScannerEmpty('Network range not available');
    if (btn) {
      btn.disabled = false;
      btn.textContent = 'Quick Scan (LAN)';
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
    }
  }
}

async function handlePortTest(btn, badge, addBtn, ip, port) {
  if (!btn || !badge) return;
  if (!ip) return;
  const key = `${ip}-${port}`;
  if (runningPortTests.has(key)) return;
  runningPortTests.add(key);
  btn.disabled = true;
  btn.textContent = 'Teste...';
  setTestBadge(badge, 'idle', 'Testing...');
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
      setTestBadge(badge, 'fail', `Port ${port}: FAIL (error)`);
      if (addBtn) addBtn.disabled = true;
      return;
    }
    const data = await res.json();
    const reachable = data?.reachable === true;
    const latency = Number(data?.latency_ms);
    if (reachable) {
      const latText = Number.isFinite(latency) ? ` (${latency} ms)` : '';
      setTestBadge(badge, 'ok', `Port ${port}: OK${latText}`);
      if (addBtn) addBtn.disabled = false;
    } else {
      const reason = data?.error || 'fail';
      setTestBadge(badge, 'fail', `Port ${port}: FAIL (${reason})`);
      if (addBtn) addBtn.disabled = true;
    }
  } catch (err) {
    setTestBadge(badge, 'fail', `Port ${port}: FAIL (error)`);
    if (addBtn) addBtn.disabled = true;
  } finally {
    btn.disabled = false;
    btn.textContent = 'Test (Port 6000)';
    runningPortTests.delete(key);
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
  const badge = $('#healthBadge');
  const text = $('#healthText');
  if (!badge || !text) return;
  const applyClass = (el, level) => {
    el.classList.remove('status-ok', 'status-warn', 'status-error', 'status-idle');
    if (level === 'ok') el.classList.add('status-ok');
    else if (level === 'critical') el.classList.add('status-error');
    else el.classList.add('status-warn');
  };
  // ensure text has no status classes
  text.classList.remove('status-ok', 'status-warn', 'status-error', 'status-idle');
  const api = (statusData?.api || '').toLowerCase();
  const db = (statusData?.db || '').toLowerCase();
  const ws = (statusData?.ws || '').toLowerCase();
  const mqtt = (statusData?.mqtt || '').toLowerCase();

  let level = 'warning';
  if (api === 'offline' || db === 'offline') {
    level = 'critical';
  } else if (api === 'online' && db === 'connected' && ws !== 'offline') {
    level = 'ok';
  } else {
    level = 'warning';
  }
  const textMap = {
    ok: 'All core services operational',
    warning: 'Some services require attention',
    critical: 'Critical system services unavailable',
  };
  applyClass(badge, level);
  badge.textContent = level === 'ok' ? 'OK' : level === 'critical' ? 'Critical' : 'Warning';
  text.textContent = textMap[level] || textMap.warning;
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
  initTabs();
  startPolling();
  if (activeTab === 'performance') {
    startPerformancePolling();
  }
  if (activeTab === 'scanner') {
    initScannerTab();
  }
});
