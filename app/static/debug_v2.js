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
let configLoaded = false;
let configSnapshot = {};
let logViewerState = { module: 'app', lastCount: 0 };

function setConfigEditable(enabled) {
  document.querySelectorAll('#panel-config input, #panel-config select, #panel-config button').forEach(el => {
    if (el.id && el.id.startsWith('cfg_')) {
      el.disabled = !enabled;
    }
  });

  if (enabled) {
    applyConfigEnableStates();
  }
}

function applyConfigEnableStates() {
  // Health gate
  const healthEnabled = document.getElementById('cfg_health_enabled')?.checked;
  ['cfg_health_warn_latency', 'cfg_health_error_latency'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = !healthEnabled;
  });
  ['cfg_health_cancel', 'cfg_health_save'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = !healthEnabled;
  });

  // Runtime gate
  const runtimeEnabled = document.getElementById('cfg_runtime_enabled')?.checked;
  ['cfg_runtime_poll_interval'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = !runtimeEnabled;
  });
  ['cfg_runtime_cancel', 'cfg_runtime_save'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = !runtimeEnabled;
  });

  // JSON Inspector gate: Buttons immer aktiv wenn Felder gesetzt
  const jsonMaxSize = document.getElementById('cfg_json_max_size')?.value;
  const jsonMaxDepth = document.getElementById('cfg_json_max_depth')?.value;
  const jsonEnabled = !!(jsonMaxSize || jsonMaxDepth);
  ['cfg_json_cancel', 'cfg_json_save'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = !jsonEnabled;
  });
}

function renderLogViewer(data) {
  const statusEl = document.getElementById('log-overview-status');
  const entriesEl = document.getElementById('log-entries');
  const detailEl = document.getElementById('log-detail');
  if (!statusEl || !entriesEl || !detailEl) return;
  const safeData = data && typeof data === 'object' ? data : {};
  const module = safeData.module || logViewerState.module || 'app';
  const items = Array.isArray(safeData.items) ? safeData.items : [];
  const count = Number.isFinite(safeData.count) ? safeData.count : items.length;
  logViewerState.lastCount = count;
  statusEl.textContent = `Modul: ${module} • Einträge: ${items.length} / ${count}`;
  if (items.length === 0) {
    entriesEl.textContent = 'Keine Logs verfuegbar.';
    detailEl.textContent = 'Noch kein Eintrag ausgewaehlt.';
    return;
  }
  const listText = items.join('\n');
  entriesEl.textContent = listText;
  detailEl.textContent = items[0] || 'Noch kein Eintrag ausgewaehlt.';
}

async function loadLogViewer(module = 'app') {
  if (window.DEBUG_MODE !== 'pro') return;
  const statusEl = document.getElementById('log-overview-status');
  const entriesEl = document.getElementById('log-entries');
  const detailEl = document.getElementById('log-detail');
  if (!statusEl || !entriesEl || !detailEl) return;
  logViewerState.module = module;
  statusEl.textContent = 'Lade Logs...';
  entriesEl.textContent = '...';
  detailEl.textContent = 'Noch kein Eintrag ausgewaehlt.';
  try {
    const resp = await fetch(`/api/debug/logs?module=${encodeURIComponent(module)}&limit=200`);
    if (!resp.ok) {
      const txt = await resp.text();
      throw new Error(txt || 'Fehler beim Laden');
    }
    const json = await resp.json();
    renderLogViewer(json);
  } catch (err) {
    statusEl.textContent = 'Fehler beim Laden der Logs.';
    entriesEl.textContent = (err && err.message) || 'Unbekannter Fehler';
    detailEl.textContent = 'Keine Details verfuegbar.';
  }
}

function setActiveTab(target) {
  if (!target) return;
  activeTab = target;
  document.querySelectorAll('.debug-panel').forEach(panel => {
    const isActive = panel.id === `panel-${activeTab}`;
    panel.classList.toggle('active-panel', isActive);
    panel.style.display = isActive ? '' : 'none';
  });
  document.querySelectorAll('.debug-tab').forEach(tab => {
    tab.classList.toggle('active', tab.dataset.tab === activeTab);
  });
  if (activeTab === 'performance') {
    startPerformancePolling();
  } else {
    stopPerformancePolling();
  }
  if (activeTab === 'scanner') {
    initScannerTab();
  }
  if (activeTab === 'config') {
    loadConfigData();
  }
  if (activeTab === 'json' && window.DEBUG_MODE === 'pro') {
    loadJsonInspectorLimits();
    if (typeof initJsonInspector === 'function') {
      initJsonInspector();
    }
  }
  if (activeTab === 'services' && window.DEBUG_MODE === 'pro') {
    loadServicesData();
  }
  if (activeTab === 'logs' && window.DEBUG_MODE === 'pro') {
    loadLogViewer();
  }
}

function normalizePrinterType(val) {
  const v = (val || '').toLowerCase();
  if (v.includes('bambu')) return 'bambu';
  if (v.includes('klipper')) return 'klipper';
  return 'generic';
}

function setDebugMode(mode) {
  window.DEBUG_MODE = mode === 'pro' ? 'pro' : 'lite';
  document.body.classList.remove('debug-lite', 'pro-mode');
  if (window.DEBUG_MODE === 'pro') {
    document.body.classList.add('pro-mode');
  } else {
    document.body.classList.add('debug-lite');
  }
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
  setConfigEditable(window.DEBUG_MODE === 'pro');
  document.querySelectorAll('.pro-only, [data-mode="pro"]').forEach(el => {
    const isPanel = el.classList.contains('debug-panel');
    if (window.DEBUG_MODE === 'pro') {
      if (isPanel) {
        const target = el.id?.replace('panel-', '');
        el.style.display = target === activeTab ? '' : 'none';
      } else {
        el.style.display = '';
      }
    } else {
      el.style.display = 'none';
    }
  });
  document.querySelectorAll('.pro-only-inline').forEach(el => {
    el.style.display = window.DEBUG_MODE === 'pro' ? '' : 'none';
  });
  updateProbeButtonState();
  if (window.DEBUG_MODE === 'lite') {
    const activeTabEl = document.querySelector(`.debug-tab[data-tab="${activeTab}"]`);
    if (activeTabEl && activeTabEl.dataset.mode === 'pro') {
      setActiveTab('system');
      return;
    }
  }
  setActiveTab(activeTab);
}

function initDebugModeUI() {
  const btnLite = document.getElementById('debugModeLite');
  const btnPro = document.getElementById('debugModePro');
  if (btnLite) btnLite.addEventListener('click', () => setDebugMode('lite'));
  if (btnPro) btnPro.addEventListener('click', () => setDebugMode('pro'));
  setDebugMode(window.DEBUG_MODE || 'lite');
  initConfigActions();
}

function $(id) {
  return document.getElementById(id);
}

function setText(id, value, fallback = '-') {
  // Nur MQTT-Status-BADGES werden geschützt, nicht die Daten-Felder
  // Status-Badges werden von mqtt-connect-handler.js verwaltet
  const mqttStatusBadges = ['mqttStatus', 'mqttStatusBadge', 'mqttConnBadge', 'proMqttStatus'];
  if (mqttStatusBadges.includes(id)) return;
  
  const el = $(id);
  if (!el) return;
  const safe = value === undefined || value === null || value === '' ? fallback : value;
  el.textContent = safe;
}

function setCheckbox(id, value) {
  const el = $(id);
  if (!el) return;
  el.checked = Boolean(value);
}

function setInputValue(id, value) {
  const el = $(id);
  if (!el) return;
  el.value = value !== undefined && value !== null ? value : '';
}

function setSelectValue(id, value, allowed = []) {
  const el = $(id);
  if (!el) return;
  const normalized = (value || '').toString().toLowerCase();
  if (allowed.length === 0 || allowed.includes(normalized)) {
    el.value = normalized;
  }
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

function populateConfigFields(data) {
  const cfg = data && typeof data === 'object' ? data : {};
  const cm = cfg.config_manager && typeof cfg.config_manager === 'object' ? cfg.config_manager : {};
  const debug = cfg.debug && typeof cfg.debug === 'object' ? cfg.debug : {};
  const systemHealth = debug.system_health && typeof debug.system_health === 'object' ? debug.system_health : {};
  const runtime = debug.runtime && typeof debug.runtime === 'object' ? debug.runtime : {};
  const logging = cfg.logging && typeof cfg.logging === 'object' ? cfg.logging : {};
  const scanner = cfg.scanner && typeof cfg.scanner === 'object' ? cfg.scanner : {};
  const scannerPro = scanner.pro && typeof scanner.pro === 'object' ? scanner.pro : {};
  const fp = cfg.fingerprint && typeof cfg.fingerprint === 'object' ? cfg.fingerprint : {};
  const jsonInspector = cfg.json_inspector && typeof cfg.json_inspector === 'object' ? cfg.json_inspector : {};

  setCheckbox('cfg_health_enabled', systemHealth.enabled ?? cm.health_enabled);
  setInputValue('cfg_health_warn_latency', systemHealth.warn_latency_ms ?? cm.health_latency_warn_ms);
  setInputValue('cfg_health_error_latency', systemHealth.error_latency_ms ?? cm.health_latency_error_ms);

  const systemLoggingModules = logging.modules && typeof logging.modules === 'object' ? logging.modules : {};
  setCheckbox('cfg_system_logging_enabled', logging.enabled ?? true);
  setSelectValue('cfg_system_logging_level', logging.level ?? 'info', ['debug', 'info', 'warning', 'error']);
  setInputValue('cfg_system_logging_max_size', logging.max_size_mb ?? 10);
  setInputValue('cfg_system_logging_backup_count', logging.backup_count ?? 3);
  setInputValue('cfg_system_logging_keep_days', logging.keep_days ?? 14);
  ['app', 'bambu', 'errors', 'klipper', 'mqtt'].forEach(module => {
    setCheckbox(`cfg_system_logging_module_${module}`, systemLoggingModules[module]?.enabled ?? false);
  });

  setCheckbox('cfg_runtime_enabled', runtime.enabled ?? cm.runtime_enabled);
  setInputValue('cfg_runtime_poll_interval', runtime.poll_interval_ms ?? cm.runtime_poll_interval_ms);

  setInputValue('cfg_json_max_size', jsonInspector.max_size_mb);
  setInputValue('cfg_json_max_depth', jsonInspector.max_depth);
  setCheckbox('cfg_json_allow_override', jsonInspector.allow_override);

  // MQTT Logging Config
  const mqttLogging = cfg.mqtt_logging && typeof cfg.mqtt_logging === 'object' ? cfg.mqtt_logging : {};
  const mqttSmartLog = mqttLogging.smart_logging && typeof mqttLogging.smart_logging === 'object' ? mqttLogging.smart_logging : {};
  const mqttLimits = mqttLogging.limits && typeof mqttLogging.limits === 'object' ? mqttLogging.limits : {};

  setCheckbox('cfg_mqtt_logging_enabled', mqttLogging.enabled ?? true);
  setCheckbox('cfg_mqtt_smart_logging', mqttSmartLog.enabled ?? false);
  setSelectValue('cfg_mqtt_trigger_type', mqttSmartLog.trigger_type ?? 'command', ['command', 'temperature']);
  setInputValue('cfg_mqtt_trigger_command', mqttSmartLog.trigger_type === 'command' ? mqttSmartLog.trigger_value : 'printing');
  setInputValue('cfg_mqtt_trigger_temp', mqttSmartLog.trigger_type === 'temperature' ? mqttSmartLog.trigger_value : 220);
  setInputValue('cfg_mqtt_max_duration', mqttSmartLog.max_duration_hours ?? 4);
  setInputValue('cfg_mqtt_buffer_minutes', mqttSmartLog.buffer_minutes ?? 5);
  setInputValue('cfg_mqtt_max_size', mqttLimits.max_size_mb ?? 100);
  setInputValue('cfg_mqtt_max_payload', mqttLimits.max_payload_chars ?? 1000);
  setCheckbox('cfg_mqtt_full_payload', mqttLimits.full_payload_enabled ?? false);

  // Trigger UI visibility
  updateMqttTriggerUI();

  const normalizedSystemLoggingLevel = (logging.level || 'info').toString().toLowerCase();
  configSnapshot = {
    health_enabled: systemHealth.enabled ?? cm.health_enabled,
    health_warn_latency: systemHealth.warn_latency_ms ?? cm.health_latency_warn_ms,
    health_error_latency: systemHealth.error_latency_ms ?? cm.health_latency_error_ms,
    system_logging_enabled: logging.enabled ?? true,
    system_logging_level: normalizedSystemLoggingLevel,
    system_logging_max_size: logging.max_size_mb ?? 10,
    system_logging_backup_count: logging.backup_count ?? 3,
    system_logging_keep_days: logging.keep_days ?? 14,
    system_logging_module_app: systemLoggingModules.app?.enabled ?? false,
    system_logging_module_bambu: systemLoggingModules.bambu?.enabled ?? false,
    system_logging_module_errors: systemLoggingModules.errors?.enabled ?? false,
    system_logging_module_klipper: systemLoggingModules.klipper?.enabled ?? false,
    system_logging_module_mqtt: systemLoggingModules.mqtt?.enabled ?? false,
    runtime_enabled: runtime.enabled ?? cm.runtime_enabled,
    runtime_poll_interval: runtime.poll_interval_ms ?? cm.runtime_poll_interval_ms,
    json_max_size: jsonInspector.max_size_mb,
    json_max_depth: jsonInspector.max_depth,
    json_allow_override: jsonInspector.allow_override,
    mqtt_logging_enabled: mqttLogging.enabled ?? true,
    mqtt_smart_logging: mqttSmartLog.enabled ?? false,
    mqtt_trigger_type: mqttSmartLog.trigger_type ?? 'command',
    mqtt_trigger_command: mqttSmartLog.trigger_type === 'command' ? mqttSmartLog.trigger_value : 'printing',
    mqtt_trigger_temp: mqttSmartLog.trigger_type === 'temperature' ? mqttSmartLog.trigger_value : 220,
    mqtt_max_duration: mqttSmartLog.max_duration_hours ?? 4,
    mqtt_buffer_minutes: mqttSmartLog.buffer_minutes ?? 5,
    mqtt_max_size: mqttLimits.max_size_mb ?? 100,
    mqtt_max_payload: mqttLimits.max_payload_chars ?? 1000,
    mqtt_full_payload: mqttLimits.full_payload_enabled ?? false,
  };
  setConfigEditable(true);
  applyConfigEnableStates();
}

function resetConfigCard(card) {
  if (!configSnapshot || Object.keys(configSnapshot).length === 0) return;
  if (card === 'health' || card === 'all') {
    setCheckbox('cfg_health_enabled', configSnapshot.health_enabled);
    setInputValue('cfg_health_warn_latency', configSnapshot.health_warn_latency);
    setInputValue('cfg_health_error_latency', configSnapshot.health_error_latency);
  }
  if (card === 'system_logging' || card === 'all') {
    setCheckbox('cfg_system_logging_enabled', configSnapshot.system_logging_enabled);
    setSelectValue('cfg_system_logging_level', configSnapshot.system_logging_level, ['debug', 'info', 'warning', 'error']);
    setInputValue('cfg_system_logging_max_size', configSnapshot.system_logging_max_size);
    setInputValue('cfg_system_logging_backup_count', configSnapshot.system_logging_backup_count);
    setInputValue('cfg_system_logging_keep_days', configSnapshot.system_logging_keep_days);
    ['app', 'bambu', 'errors', 'klipper', 'mqtt'].forEach(module => {
      setCheckbox(`cfg_system_logging_module_${module}`, configSnapshot[`system_logging_module_${module}`]);
    });
  }
  if (card === 'runtime' || card === 'all') {
    setCheckbox('cfg_runtime_enabled', configSnapshot.runtime_enabled);
    setInputValue('cfg_runtime_poll_interval', configSnapshot.runtime_poll_interval);
  }
  if (card === 'json' || card === 'all') {
    setInputValue('cfg_json_max_size', configSnapshot.json_max_size);
    setInputValue('cfg_json_max_depth', configSnapshot.json_max_depth);
    setCheckbox('cfg_json_allow_override', configSnapshot.json_allow_override);
  }
  if (card === 'mqtt_logging' || card === 'all') {
    setCheckbox('cfg_mqtt_logging_enabled', configSnapshot.mqtt_logging_enabled);
    setCheckbox('cfg_mqtt_smart_logging', configSnapshot.mqtt_smart_logging);
    setSelectValue('cfg_mqtt_trigger_type', configSnapshot.mqtt_trigger_type, ['command', 'temperature']);
    setInputValue('cfg_mqtt_trigger_command', configSnapshot.mqtt_trigger_command);
    setInputValue('cfg_mqtt_trigger_temp', configSnapshot.mqtt_trigger_temp);
    setInputValue('cfg_mqtt_max_duration', configSnapshot.mqtt_max_duration);
    setInputValue('cfg_mqtt_buffer_minutes', configSnapshot.mqtt_buffer_minutes);
    setInputValue('cfg_mqtt_max_size', configSnapshot.mqtt_max_size);
    setInputValue('cfg_mqtt_max_payload', configSnapshot.mqtt_max_payload);
    setCheckbox('cfg_mqtt_full_payload', configSnapshot.mqtt_full_payload);
    updateMqttTriggerUI();
  }
}

function parseIntOrUndefined(val) {
  const parsed = parseInt(val, 10);
  return Number.isFinite(parsed) ? parsed : undefined;
}

async function saveConfigSection(section) {
  const payload = {};
  if (section === 'health') {
    payload['debug.system_health.enabled'] = document.getElementById('cfg_health_enabled').checked;
    payload['debug.system_health.warn_latency_ms'] = parseInt(document.getElementById('cfg_health_warn_latency').value, 10);
    payload['debug.system_health.error_latency_ms'] = parseInt(document.getElementById('cfg_health_error_latency').value, 10);
  }
  if (section === 'system_logging') {
    payload['logging.enabled'] = document.getElementById('cfg_system_logging_enabled').checked;
    payload['logging.level'] = document.getElementById('cfg_system_logging_level').value;
    const maxSizeVal = parseIntOrUndefined(document.getElementById('cfg_system_logging_max_size').value);
    const backupVal = parseIntOrUndefined(document.getElementById('cfg_system_logging_backup_count').value);
    const keepDaysVal = parseIntOrUndefined(document.getElementById('cfg_system_logging_keep_days').value);
    if (maxSizeVal !== undefined) payload['logging.max_size_mb'] = maxSizeVal;
    if (backupVal !== undefined) payload['logging.backup_count'] = backupVal;
    if (keepDaysVal !== undefined) payload['logging.keep_days'] = keepDaysVal;
    ['app', 'bambu', 'errors', 'klipper', 'mqtt'].forEach(module => {
      payload[`logging.modules.${module}`] = document.getElementById(`cfg_system_logging_module_${module}`).checked;
    });
  }
  if (section === 'runtime') {
    payload['debug.runtime.enabled'] = document.getElementById('cfg_runtime_enabled').checked;
    payload['debug.runtime.poll_interval_ms'] = parseInt(document.getElementById('cfg_runtime_poll_interval').value, 10);
  }
  if (section === 'json') {
    payload['json_inspector.max_size_mb'] = parseInt(document.getElementById('cfg_json_max_size').value, 10);
    payload['json_inspector.max_depth'] = parseInt(document.getElementById('cfg_json_max_depth').value, 10);
    payload['json_inspector.allow_override'] = document.getElementById('cfg_json_allow_override').checked;
  }
  if (section === 'mqtt_logging') {
    payload['mqtt_logging.enabled'] = document.getElementById('cfg_mqtt_logging_enabled').checked;
    payload['mqtt_logging.smart_logging.enabled'] = document.getElementById('cfg_mqtt_smart_logging').checked;
    payload['mqtt_logging.smart_logging.trigger_type'] = document.getElementById('cfg_mqtt_trigger_type').value;
    const triggerType = document.getElementById('cfg_mqtt_trigger_type').value;
    if (triggerType === 'command') {
      payload['mqtt_logging.smart_logging.trigger_value'] = document.getElementById('cfg_mqtt_trigger_command').value;
    } else {
      payload['mqtt_logging.smart_logging.trigger_value'] = parseInt(document.getElementById('cfg_mqtt_trigger_temp').value, 10);
    }
    payload['mqtt_logging.smart_logging.max_duration_hours'] = parseInt(document.getElementById('cfg_mqtt_max_duration').value, 10);
    payload['mqtt_logging.smart_logging.buffer_minutes'] = parseInt(document.getElementById('cfg_mqtt_buffer_minutes').value, 10);
    payload['mqtt_logging.limits.max_size_mb'] = parseInt(document.getElementById('cfg_mqtt_max_size').value, 10);
    payload['mqtt_logging.limits.max_payload_chars'] = parseInt(document.getElementById('cfg_mqtt_max_payload').value, 10);
    payload['mqtt_logging.limits.full_payload_enabled'] = document.getElementById('cfg_mqtt_full_payload').checked;
  }
  try {
    const res = await fetch('/api/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) return;
    const data = await res.json();
    populateConfigFields(data);
  } catch (err) {
    // ignore save errors for now
  }
}


async function loadConfigData() {
  if (!document.body.classList.contains('pro-mode')) return;
  if (configLoaded) return;
  try {
    const res = await fetch('/api/config/current');
    if (!res.ok) return;
    const data = await res.json();
    populateConfigFields(data);
    configLoaded = true;
  } catch (err) {
    // ignore load errors
  }
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
  // MQTT-Status wird ausschließlich von mqtt-connect-handler.js verwaltet
  // Schütze ALLE MQTT-Status-Elemente vor Überschreibung
  const mqttElements = ['mqttStatus', 'mqttStatusBadge', 'mqttConnBadge', 'proMqttStatus'];
  if (mqttElements.includes(id)) return;
  
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
      if (window.DEBUG_MODE === 'lite' && tab.dataset.mode === 'pro') {
        return;
      }
      setActiveTab(target);
    });
  });
  const initial = document.querySelector('.debug-tab.active');
  activeTab = initial?.dataset?.tab || 'system';
  setActiveTab(activeTab);
}

function initConfigActions() {
  const bind = (id, section, handler) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('click', handler.bind(null, section));
  };
  const watch = (id) => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('change', applyConfigEnableStates);
  };
  bind('cfg_health_cancel', 'health', () => resetConfigCard('health'));
  bind('cfg_health_save', 'health', saveConfigSection);
  bind('cfg_runtime_cancel', 'runtime', () => resetConfigCard('runtime'));
  bind('cfg_runtime_save', 'runtime', saveConfigSection);
  bind('cfg_json_cancel', 'json', () => resetConfigCard('json'));
  bind('cfg_json_save', 'json', saveConfigSection);
  bind('cfg_mqtt_cancel', 'mqtt_logging', () => resetConfigCard('mqtt_logging'));
  bind('cfg_mqtt_save', 'mqtt_logging', saveConfigSection);
  bind('cfg_system_logging_cancel', 'system_logging', () => resetConfigCard('system_logging'));
  bind('cfg_system_logging_save', 'system_logging', saveConfigSection);
  watch('cfg_health_enabled');
  watch('cfg_runtime_enabled');

  // MQTT Smart Logging UI watchers
  const smartLoggingCheckbox = document.getElementById('cfg_mqtt_smart_logging');
  if (smartLoggingCheckbox) {
    smartLoggingCheckbox.addEventListener('change', updateMqttTriggerUI);
  }
  const triggerTypeSelect = document.getElementById('cfg_mqtt_trigger_type');
  if (triggerTypeSelect) {
    triggerTypeSelect.addEventListener('change', updateMqttTriggerUI);
  }
}

function updateMqttTriggerUI() {
  const smartEnabled = document.getElementById('cfg_mqtt_smart_logging')?.checked ?? false;
  const triggerType = document.getElementById('cfg_mqtt_trigger_type')?.value ?? 'command';

  const optionsBox = document.getElementById('cfg_mqtt_smart_logging_options');
  const commandBox = document.getElementById('cfg_mqtt_trigger_command_box');
  const tempBox = document.getElementById('cfg_mqtt_trigger_temp_box');

  if (optionsBox) {
    optionsBox.style.display = smartEnabled ? 'block' : 'none';
  }

  if (commandBox && tempBox) {
    if (smartEnabled) {
      commandBox.style.display = triggerType === 'command' ? 'block' : 'none';
      tempBox.style.display = triggerType === 'temperature' ? 'block' : 'none';
    } else {
      commandBox.style.display = 'none';
      tempBox.style.display = 'none';
    }
  }
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
    const rt = data?.runtime || {};
    const stateRaw = (rt.state || 'idle').toString().toLowerCase();
    const state = stateRaw === 'active' ? 'active' : 'idle';
    setStatus('apiStatus', data?.api?.state || 'offline');
    setStatus('dbStatus', data?.db?.state || 'offline');
    // MQTT-Status wird NICHT mehr hier gesetzt - mqtt-connect-handler.js ist zuständig
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
  const statusText = (data?.status || 'Unbekannt').toString();
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
  const probeBadge = document.getElementById('proProbeBadge');
  const fpBadge = document.getElementById('proFingerprintBadge');
  const enabled = probeTarget && probeTarget.ip;

  if (probeBtn) {
    probeBtn.disabled = !enabled;
    probeBtn.title = enabled ? '' : 'Probe erfordert erfolgreichen Port-Test';

    // Update button styling
    if (enabled) {
      probeBtn.classList.remove('pro-btn-disabled');
      probeBtn.classList.add('btn-secondary');
    } else {
      probeBtn.classList.add('pro-btn-disabled');
      probeBtn.classList.remove('btn-secondary');
    }
  }

  if (fpBtn) {
    fpBtn.disabled = !enabled;
    fpBtn.title = enabled ? '' : 'Fingerprint erfordert erfolgreichen Port-Test';

    // Update button styling
    if (enabled) {
      fpBtn.classList.remove('pro-btn-disabled');
      fpBtn.classList.add('btn-secondary');
    } else {
      fpBtn.classList.add('pro-btn-disabled');
      fpBtn.classList.remove('btn-secondary');
    }
  }

  // Update badge states
  if (probeBadge) {
    probeBadge.textContent = enabled ? 'BEREIT' : 'IDLE';
    probeBadge.className = enabled ? 'status-badge status-ok' : 'status-badge status-idle';
  }

  if (fpBadge) {
    fpBadge.textContent = enabled ? 'BEREIT' : 'IDLE';
    fpBadge.className = enabled ? 'status-badge status-ok' : 'status-badge status-idle';
  }

  // Log for debugging
  if (enabled) {
    console.log('[Scanner] Deep Probe & Fingerprint aktiviert für:', probeTarget);
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
  // badge styling
  try {
    const badgeEl = document.querySelector('.scanner-pro-head .status-badge');
    if (badgeEl) {
      badgeEl.classList.remove('status-ok', 'status-warn', 'status-error', 'status-idle');
      const normalized = statusText.toUpperCase();
      if (normalized === 'OK') badgeEl.classList.add('status-ok');
      else if (normalized === 'FEHLER' || normalized === 'ERROR') badgeEl.classList.add('status-error');
      else if (normalized === 'NICHT_VERFUEGBAR' || normalized === 'UNBEKANNT') badgeEl.classList.add('status-idle');
      else badgeEl.classList.add('status-warn');
    }
  } catch (e) {
    // ignore
  }
}

async function handleFingerprint(btn) {
  if (!btn) return;
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
    // Determine whether a usable fingerprint was found
    const hasFingerprint =
      data &&
      (data.detected_type ||
       data.confidence != null ||
       (data.ports && Object.keys(data.ports).some(
         k => data.ports[k]?.reachable === true
       )));

    if (hasFingerprint) {
      updateFingerprintUI({ ...data, status: 'OK' });
    } else {
      updateFingerprintUI({
        status: 'NICHT_VERFUEGBAR',
        detected_type: '-',
        confidence: null,
        ports: data?.ports || {},
        message: 'Fingerprint technisch nicht moeglich oder keine verwertbaren Daten'
      });
    }
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
  if (!ip) return;

  // Open dialog instead of directly saving
  openScannerPrinterDialog(ip, port, baseType, card, btn);
}

function initScannerTab() {
  if (scannerInitialized) return;
  const btn = $('scannerQuickScan');
  if (btn) {
    btn.addEventListener('click', handleQuickScanClick);
  }
  const addManualBtn = $('scannerAddManual');
  if (addManualBtn) {
    addManualBtn.addEventListener('click', openManualPrinterDialog);
  }
  const closeDialogBtn = $('closeManualDialog');
  if (closeDialogBtn) {
    closeDialogBtn.addEventListener('click', closeManualPrinterDialog);
  }
  const testBtn = $('manualTestBtn');
  if (testBtn) {
    testBtn.addEventListener('click', handleManualTest);
  }
  const saveBtn = $('manualSaveBtn');
  if (saveBtn) {
    saveBtn.addEventListener('click', handleManualSave);
  }
  const typeSelect = $('manualType');
  if (typeSelect) {
    typeSelect.addEventListener('change', toggleBambuCredentials);
  }

  // Scanner Dialog Event Listeners
  const closeScannerDialogBtn = $('closeScannerDialog');
  if (closeScannerDialogBtn) {
    closeScannerDialogBtn.addEventListener('click', closeScannerPrinterDialog);
  }
  const scannerCancelBtn = $('scannerCancelBtn');
  if (scannerCancelBtn) {
    scannerCancelBtn.addEventListener('click', closeScannerPrinterDialog);
  }
  const scannerConfirmBtn = $('scannerConfirmBtn');
  if (scannerConfirmBtn) {
    scannerConfirmBtn.addEventListener('click', handleScannerConfirm);
  }
  const scannerTypeSelect = $('scannerDialogType');
  if (scannerTypeSelect) {
    scannerTypeSelect.addEventListener('change', toggleScannerBambuCredentials);
  }

  renderScannerEmpty('No printers detected');
  loadNetworkInfo();
  scannerInitialized = true;
}

function toggleBambuCredentials() {
  const typeSelect = $('manualType');
  const bambuCreds = $('bambuCredentials');
  const bambuAccess = $('bambuAccessCode');
  const portInput = $('manualPort');

  if (!typeSelect || !bambuCreds || !bambuAccess) return;

  const isBambu = typeSelect.value === 'bambu';
  bambuCreds.style.display = isBambu ? 'block' : 'none';
  bambuAccess.style.display = isBambu ? 'block' : 'none';

  // Set default port based on printer type
  if (portInput && !portInput.value) {
    if (isBambu) {
      portInput.value = '8883';
      portInput.placeholder = 'Standard: 8883 (MQTT TLS)';
    } else if (typeSelect.value === 'klipper') {
      portInput.value = '7125';
      portInput.placeholder = 'Standard: 7125 (Moonraker)';
    } else {
      portInput.value = '';
      portInput.placeholder = 'z.B. 80 oder 443';
    }
  }
}

function toggleScannerBambuCredentials() {
  const typeSelect = $('scannerDialogType');
  const bambuCreds = $('scannerBambuCredentials');
  const bambuAccess = $('scannerAccessCode');

  if (!typeSelect || !bambuCreds || !bambuAccess) return;

  const isBambu = typeSelect.value === 'bambu';
  bambuCreds.style.display = isBambu ? 'block' : 'none';
  bambuAccess.style.display = isBambu ? 'block' : 'none';
}

function openManualPrinterDialog() {
  const dialog = $('manualPrinterDialog');
  if (!dialog) return;

  // Reset form
  const ipInput = $('manualIp');
  const portInput = $('manualPort');
  const typeSelect = $('manualType');
  const serialInput = $('manualSerial');
  const accessCodeInput = $('manualAccessCode');
  const testResult = $('manualTestResult');
  const saveBtn = $('manualSaveBtn');

  if (ipInput) ipInput.value = '';
  if (portInput) portInput.value = '';
  if (typeSelect) typeSelect.value = 'bambu';
  if (serialInput) serialInput.value = '';
  if (accessCodeInput) accessCodeInput.value = '';
  if (testResult) {
    testResult.style.display = 'none';
    testResult.innerHTML = '';
  }
  if (saveBtn) saveBtn.disabled = true;

  // Show Bambu credentials and set default port
  toggleBambuCredentials();

  dialog.style.display = 'flex';
}

function closeManualPrinterDialog() {
  const dialog = $('manualPrinterDialog');
  if (!dialog) return;
  dialog.style.display = 'none';
}

// Scanner Dialog State
let scannerDialogData = {
  ip: '',
  port: 0,
  type: 'bambu',
  card: null,
  btn: null
};

function openScannerPrinterDialog(ip, port, type, card, btn) {
  const dialog = $('scannerPrinterDialog');
  if (!dialog) return;

  // Store data for later use
  scannerDialogData = { ip, port, type, card, btn };

  // Set values
  const ipEl = $('scannerDialogIp');
  const portEl = $('scannerDialogPort');
  const typeSelect = $('scannerDialogType');
  const serialInput = $('scannerSerial');
  const apiKeyInput = $('scannerApiKey');
  const saveResult = $('scannerSaveResult');

  // Für Bambu-Drucker wird IMMER Port 8883 verwendet (MQTT TLS)
  // Port 6000 ist nur für Tests, nicht für die tatsächliche Verbindung
  const displayPort = type === 'bambu' ? '8883 (MQTT TLS)' : port;
  const infoText = type === 'bambu' ? 'Port 6000 für Tests OK, 8883 wird für MQTT verwendet' : '';

  if (ipEl) ipEl.textContent = ip;
  if (portEl) {
    portEl.textContent = displayPort;
    if (infoText) {
      portEl.title = infoText;
      portEl.style.cursor = 'help';
    }
  }
  if (typeSelect) typeSelect.value = type;
  if (serialInput) serialInput.value = '';
  if (apiKeyInput) apiKeyInput.value = '';
  if (saveResult) {
    saveResult.style.display = 'none';
    saveResult.innerHTML = '';
  }

  // Show/hide Bambu credentials based on type
  toggleScannerBambuCredentials();

  dialog.style.display = 'flex';
}

function closeScannerPrinterDialog() {
  const dialog = $('scannerPrinterDialog');
  if (!dialog) return;
  dialog.style.display = 'none';
}

async function handleScannerConfirm() {
  const { ip, port, card, btn } = scannerDialogData;
  const typeSelect = $('scannerDialogType');
  const serialInput = $('scannerSerial');
  const apiKeyInput = $('scannerApiKey');
  const saveResult = $('scannerSaveResult');
  const confirmBtn = $('scannerConfirmBtn');

  if (!typeSelect || !confirmBtn) return;

  const printerType = typeSelect.value;
  const isBambu = printerType === 'bambu';

  // Validate Bambu credentials
  if (isBambu) {
    const serial = serialInput?.value.trim() || '';
    const apiKey = apiKeyInput?.value.trim() || '';

    if (!serial || !apiKey) {
      if (saveResult) {
        saveResult.style.display = 'block';
        saveResult.className = 'test-result test-result-error';
        saveResult.textContent = 'Für Bambu Lab Drucker sind Seriennummer und Access Code erforderlich';
      }
      return;
    }
  }

  // Disable button during save
  confirmBtn.disabled = true;
  confirmBtn.textContent = 'Speichere...';

  try {
    // WICHTIG: Bambu-Drucker benötigen Port 8883 für MQTT (TLS)
    // Scanner testet Port 6000, aber für die Verbindung brauchen wir 8883
    const finalPort = isBambu ? 8883 : port;

    const payload = {
      name: `${printerType}-${ip}`,
      printer_type: printerType,
      ip_address: ip,
      port: finalPort,
      model: "Lite",
      mqtt_version: "311",
      active: true
    };

    // Add Bambu credentials if needed
    if (isBambu) {
      payload.cloud_serial = serialInput?.value.trim() || '';
      payload.api_key = apiKeyInput?.value.trim() || '';
    }

    const res = await fetch('/api/printers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    const data = await res.json().catch(() => ({}));

    if (data?.status === 'exists') {
      if (saveResult) {
        saveResult.style.display = 'block';
        saveResult.className = 'test-result test-result-warning';
        saveResult.textContent = 'Drucker bereits im System vorhanden';
      }

      // Update UI
      if (btn) {
        btn.classList.add('btn-add-disabled', 'disabled');
        btn.classList.remove('btn-add-active');
        btn.disabled = true;
        btn.textContent = 'Im System';
      }
      if (card) {
        const saveInfo = card.querySelector('[data-role="saveInfo"]');
        if (saveInfo) saveInfo.textContent = 'Bereits vorhanden';
        setScannerStatus(card, 'ok', 'OK', 'info');
      }

      setTimeout(() => closeScannerPrinterDialog(), 1500);
      return;
    }

    if (res.ok) {
      if (saveResult) {
        saveResult.style.display = 'block';
        saveResult.className = 'test-result test-result-success';
        saveResult.textContent = 'Drucker erfolgreich hinzugefügt!';
      }

      // Update UI
      if (btn) {
        btn.classList.remove('btn-add-disabled', 'disabled');
        btn.classList.add('btn-add-active');
        btn.disabled = false;
        btn.textContent = 'Gespeichert';
        btn.title = '';
      }
      if (card) {
        const saveInfo = card.querySelector('[data-role="saveInfo"]');
        if (saveInfo) saveInfo.textContent = 'Gespeichert';
        setScannerStatus(card, 'ok', 'OK', `Port ${port}: OK`);
      }

      setTimeout(() => closeScannerPrinterDialog(), 1500);
    } else {
      if (saveResult) {
        saveResult.style.display = 'block';
        saveResult.className = 'test-result test-result-error';
        saveResult.textContent = `Fehler beim Speichern: ${data?.detail || 'Unbekannter Fehler'}`;
      }
      confirmBtn.disabled = false;
      confirmBtn.textContent = 'Zum System hinzufügen';
    }
  } catch (err) {
    if (saveResult) {
      saveResult.style.display = 'block';
      saveResult.className = 'test-result test-result-error';
      saveResult.textContent = `Fehler: ${err.message}`;
    }
    confirmBtn.disabled = false;
    confirmBtn.textContent = 'Zum System hinzufügen';
  }
}

async function handleManualTest() {
  const ipInput = $('manualIp');
  const portInput = $('manualPort');
  const typeSelect = $('manualType');
  const testBtn = $('manualTestBtn');
  const saveBtn = $('manualSaveBtn');
  const testResult = $('manualTestResult');

  if (!ipInput || !portInput || !typeSelect || !testBtn || !saveBtn || !testResult) return;

  const ip = ipInput.value.trim();
  const port = parseInt(portInput.value.trim(), 10);
  const printerType = typeSelect.value;

  // Validate IP
  const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
  if (!ip || !ipRegex.test(ip)) {
    testResult.style.display = 'block';
    testResult.className = 'test-result test-result-error';
    testResult.textContent = 'Ungültiges IP-Adressen-Format';
    saveBtn.disabled = true;
    return;
  }

  // Validate port
  if (!port || port < 1 || port > 65535) {
    testResult.style.display = 'block';
    testResult.className = 'test-result test-result-error';
    testResult.textContent = 'Port muss zwischen 1 und 65535 liegen';
    saveBtn.disabled = true;
    return;
  }

  // Disable button during test
  testBtn.disabled = true;
  testBtn.textContent = 'Teste...';
  testResult.style.display = 'block';
  testResult.className = 'test-result test-result-info';
  testResult.textContent = 'Verbindung wird getestet...';
  saveBtn.disabled = true;

  try {
    const res = await fetch('/api/debug/printer/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ip, port, timeout_ms: 2000 })
    });

    const data = await res.json();

    if (data.ok && data.reachable) {
      testResult.className = 'test-result test-result-success';
      testResult.textContent = `Verbindung erfolgreich! Latenz: ${data.latency_ms}ms`;
      saveBtn.disabled = false;
    } else {
      testResult.className = 'test-result test-result-error';
      testResult.textContent = data.message || 'Verbindung fehlgeschlagen - Drucker nicht erreichbar';
      saveBtn.disabled = true;
    }
  } catch (err) {
    testResult.className = 'test-result test-result-error';
    testResult.textContent = 'Test fehlgeschlagen: ' + err.message;
    saveBtn.disabled = true;
  } finally {
    testBtn.disabled = false;
    testBtn.textContent = 'Verbindung testen';
  }
}

async function handleManualSave() {
  const ipInput = $('manualIp');
  const portInput = $('manualPort');
  const typeSelect = $('manualType');
  const serialInput = $('manualSerial');
  const accessCodeInput = $('manualAccessCode');
  const saveBtn = $('manualSaveBtn');
  const testResult = $('manualTestResult');

  if (!ipInput || !portInput || !typeSelect || !saveBtn || !testResult) return;

  const ip = ipInput.value.trim();
  const port = parseInt(portInput.value.trim(), 10);
  const printerType = typeSelect.value;
  const serial = serialInput ? serialInput.value.trim() : '';
  const accessCode = accessCodeInput ? accessCodeInput.value.trim() : '';

  // Validate Bambu credentials if Bambu is selected
  if (printerType === 'bambu') {
    if (!serial || !accessCode) {
      testResult.style.display = 'block';
      testResult.className = 'test-result test-result-error';
      testResult.textContent = 'Seriennummer und Access Code sind für Bambu-Drucker erforderlich';
      saveBtn.disabled = false;
      saveBtn.textContent = 'Drucker speichern';
      return;
    }
  }

  saveBtn.disabled = true;
  saveBtn.textContent = 'Speichere...';

  const payload = {
    name: `${printerType}-${ip}`,
    printer_type: printerType,
    ip_address: ip,
    port: port,
    model: printerType === 'bambu' ? 'X1C' : printerType === 'klipper' ? 'Klipper' : 'Generic',
    mqtt_version: '311',
    active: true
  };

  // Add Bambu credentials if Bambu is selected
  if (printerType === 'bambu') {
    payload.cloud_serial = serial;
    payload.api_key = accessCode;
  }

  try {
    const res = await fetch('/api/printers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    if (data.status === 'exists') {
      testResult.className = 'test-result test-result-warning';
      testResult.textContent = 'Drucker existiert bereits im System';
    } else if (data.id) {
      testResult.className = 'test-result test-result-success';
      testResult.textContent = 'Drucker erfolgreich hinzugefügt!';
      setTimeout(() => {
        closeManualPrinterDialog();
      }, 1500);
    } else {
      testResult.className = 'test-result test-result-error';
      testResult.textContent = 'Fehler beim Hinzufügen des Druckers';
    }
  } catch (err) {
    testResult.className = 'test-result test-result-error';
    testResult.textContent = 'Speichern fehlgeschlagen: ' + err.message;
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = 'Drucker speichern';
  }
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
  // mqtt variable entfernt - wird nicht mehr benötigt, da mqtt-connect-handler.js zuständig ist

  const sysHealth = statusData?.systemHealth || {};
  let level = sysHealth.status || 'warning';
  const textMap = {
    ok: 'All core services operational',
    warning: 'Warning due to service status or response time.',
    critical: 'Critical system services',
  };
  let reasons = Array.isArray(sysHealth.reasons) ? sysHealth.reasons.filter(Boolean) : [];
  if (!statusData?.systemHealth) {
    const avgMs = Number(statusData?.runtimeAvgMs);
    const wsClients = Number(statusData?.wsClients);
    if (Number.isFinite(avgMs) && avgMs >= 600) {
      reasons.push(`High average response time (${Math.round(avgMs)} ms)`);
    }
    // MQTT-Status-Checks entfernt - mqtt-connect-handler.js ist zuständig
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
    t.textContent = textMap[level] || textMap.warning;
    applyClass(t, level);
  });

  // Mirror to pro detail placeholders
  setText('proApiStatus', statusData?.api || '-');
  setText('proDbStatus', statusData?.db || '-');
  setText('proWsStatus', statusData?.ws || '-');
  // proMqttStatus wird NICHT mehr hier gesetzt - mqtt-connect-handler.js ist zuständig

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
    reasonsEl.style.display = document.body.classList.contains('pro-mode') ? '' : 'none';
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

  // DEPRECATED: initDebugModeUI wurde durch bindDebugModeToggle im HTML ersetzt
  // if (typeof initDebugModeUI === 'function') {
  //   initDebugModeUI();
  // } else {
  //   console.warn('[debug.js] initDebugModeUI fehlt – übersprungen');
  // }

  if (typeof initTabs === 'function') {
    initTabs();
  } else {
    console.warn('[debug.js] initTabs fehlt – übersprungen');
  }

  if (typeof startPolling === 'function') {
    startPolling();
  } else {
    console.warn('[debug.js] startPolling fehlt – übersprungen');
  }

  const probeBtn = document.getElementById('proProbeStart');
  if (probeBtn && typeof handleProbe === 'function') {
    probeBtn.addEventListener('click', () => handleProbe(probeBtn));
    if (typeof updateProbeButtonState === 'function') {
      updateProbeButtonState();
    }
  }

  const fpBtn = document.getElementById('proFingerprintStart');
  if (fpBtn && typeof handleFingerprint === 'function') {
    fpBtn.addEventListener('click', () => handleFingerprint(fpBtn));
    if (typeof updateProbeButtonState === 'function') {
      updateProbeButtonState();
    }
  }

  if (typeof activeTab !== 'undefined') {
    if (activeTab === 'performance' && typeof startPerformancePolling === 'function') {
      startPerformancePolling();
    }
    if (activeTab === 'scanner' && typeof initScannerTab === 'function') {
      initScannerTab();
    }
  }

  if (typeof initJsonInspector === 'function') {
    initJsonInspector();
  }

    // JSON start button
    const jsonStartBtn = document.getElementById('json-start-btn');
    if (jsonStartBtn) {
      jsonStartBtn.addEventListener('click', () => {
        if (liveStatePaused) {
          toggleLiveStatePause();
        } else if (window.showToast) {
          window.showToast('Live-Ansicht bereits aktiv', 'info');
        }
      });
    }

    // JSON copy button
    const jsonCopyBtn = document.getElementById('json-copy-btn');
    if (jsonCopyBtn) {
      jsonCopyBtn.addEventListener('click', () => copyJsonInspector());
    }

  // JSON pause button
  const jsonPauseBtn = document.getElementById('json-pause-btn');
  if (jsonPauseBtn) {
    jsonPauseBtn.addEventListener('click', () => toggleLiveStatePause());
  }

  if (typeof initServicesButtons === 'function') {
    initServicesButtons();
  }
});

// ============================================
// MQTT TOPICS MANAGEMENT FUNCTIONS
// ============================================

async function refreshMQTTTopics() {
    console.log('refreshMQTTTopics called');
    try {
        const r = await fetch('/api/mqtt/runtime/topics', { method: 'GET' });
        const data = await r.json();
        console.log('Topics API response:', data);
        if (r.ok && data && data.connected) {
            _renderTopics(data.items || []);
            return;
        }
        _renderTopics([]);
    } catch (e) {
        console.error('refreshMQTTTopics error:', e);
        const hint = document.getElementById('mqttTopicsHint');
        if (hint) hint.textContent = 'Keine Daten';
        _renderTopics([]);
    }
}

function _renderTopics(items) {
    console.log('_renderTopics called with', items);
    const list = document.getElementById('topicsList');
    const empty = document.getElementById('topicsEmpty');
    const hint = document.getElementById('mqttTopicsHint');
    const countEl = document.getElementById('mqttSubscriptionsCount');
    if (!list) return;

    const safeItems = Array.isArray(items) ? items : [];
    if (countEl) countEl.textContent = String(safeItems.length);

    if (safeItems.length === 0) {
        if (hint) hint.textContent = 'Keine Topics';
        if (empty) empty.style.display = 'block';
        list.style.display = 'none';
        return;
    }

    if (empty) empty.style.display = 'none';
    list.style.display = 'block';
    list.innerHTML = '';

    safeItems.forEach((topic) => {
        const row = document.createElement('div');
        row.className = 'kv';

        const k = document.createElement('div');
        k.className = 'k';
        k.style.fontFamily = 'Consolas,monospace';
        k.style.whiteSpace = 'nowrap';
        k.style.overflow = 'hidden';
        k.style.textOverflow = 'ellipsis';
        k.title = String(topic || '');
        k.textContent = String(topic || '');

        const v = document.createElement('div');
        v.className = 'v';
        v.textContent = 'abonniert';

        row.appendChild(k);
        row.appendChild(v);
        list.appendChild(row);
    });
}

let _mqttTopicsPollTimer = null;

function _syncTopicsPolling() {
    console.log('_syncTopicsPolling called, _mqttLastConnected:', window._mqttLastConnected);
    const shouldRun = Boolean(window._mqttLastConnected);
    if (!shouldRun) {
        if (_mqttTopicsPollTimer) {
            clearInterval(_mqttTopicsPollTimer);
            _mqttTopicsPollTimer = null;
        }
        const hint = document.getElementById('mqttTopicsHint');
        if (hint) hint.textContent = 'Nicht verbunden';
        const empty = document.getElementById('topicsEmpty');
        const list = document.getElementById('topicsList');
        if (empty) empty.style.display = 'block';
        if (list) list.style.display = 'none';
        return;
    }

    if (_mqttTopicsPollTimer) return;
    console.log('Starting topics polling...');
    refreshMQTTTopics().catch(() => {});
    _mqttTopicsPollTimer = setInterval(() => {
        refreshMQTTTopics().catch(() => {});
    }, 4000);
}

let _mqttMessagesPollTimer = null;

async function refreshMQTTMessages() {
    console.log('refreshMQTTMessages called');
    try {
        const r = await fetch('/api/mqtt/runtime/messages?limit=50', { method: 'GET' });
        const data = await r.json();
        console.log('Messages API response:', data);
        if (r.ok && data) {
            _renderMessages(data.messages || []);
            return;
        }
        _renderMessages([]);
    } catch (e) {
        console.error('refreshMQTTMessages error:', e);
        _renderMessages([]);
    }
}

function _renderMessages(messages) {
    console.log('_renderMessages called with', messages.length, 'messages');
    const container = document.getElementById('mqttLiveMessages');
    if (!container) {
        console.warn('Live messages container not found');
        return;
    }

    const safeMessages = Array.isArray(messages) ? messages : [];

    if (safeMessages.length === 0) {
        container.innerHTML = '<div style="padding: 20px; text-align: center; color: #888;">Keine Live-Nachrichten</div>';
        return;
    }

    // Clear and rebuild
    container.innerHTML = '';

    safeMessages.forEach((msg, idx) => {
        if (!msg || typeof msg !== 'object') return;

        const msgDiv = document.createElement('div');
        msgDiv.style.cssText = 'padding: 12px 10px; border-bottom: 1px solid var(--border); display: flex; justify-content: space-between; align-items: flex-start; gap: 10px;';

        // Left: Topic and Payload
        const leftDiv = document.createElement('div');
        leftDiv.style.cssText = 'flex: 1; min-width: 0;';

        const topicSpan = document.createElement('div');
        topicSpan.style.cssText = 'font-family: Consolas, monospace; color: #3498db; font-weight: 500; word-break: break-all;';
        topicSpan.textContent = msg.topic || '';

        const payloadSpan = document.createElement('div');
        payloadSpan.style.cssText = 'font-family: Consolas, monospace; color: #666; font-size: 12px; margin-top: 4px; word-break: break-all; max-height: 60px; overflow: hidden;';
        const payload = String(msg.payload || '').substring(0, 150);
        payloadSpan.textContent = payload || '(empty)';

        leftDiv.appendChild(topicSpan);
        leftDiv.appendChild(payloadSpan);

        // Right: Timestamp
        const timeSpan = document.createElement('div');
        timeSpan.style.cssText = 'font-size: 12px; color: var(--text-dim); white-space: nowrap;';
        try {
            const ts = new Date(msg.timestamp);
            const hours = String(ts.getHours()).padStart(2, '0');
            const mins = String(ts.getMinutes()).padStart(2, '0');
            const secs = String(ts.getSeconds()).padStart(2, '0');
            timeSpan.textContent = `${hours}:${mins}:${secs}`;
        } catch (e) {
            timeSpan.textContent = '00:00:00';
        }

        msgDiv.appendChild(leftDiv);
        msgDiv.appendChild(timeSpan);
        container.appendChild(msgDiv);
    });

    const treeContainer = document.getElementById('mqtt-json-tree');
    if (treeContainer) {
        updateMqttJsonTreeFromMessage(safeMessages[0]);
    }
}

function updateMqttJsonTreeFromMessage(message) {
    const container = document.getElementById('mqtt-json-tree');
    if (!container) return;
    if (!message) {
        container.innerHTML = '<div class="json-placeholder">Warte auf JSON-Daten...</div>';
        return;
    }

    let payload = message.payload;
    if (typeof payload === 'string') {
        try {
            payload = JSON.parse(payload);
        } catch (error) {
            payload = { raw: payload };
        }
    }

    renderMqttMessageJsonTree(payload, container);
}

function renderMqttMessageJsonTree(data, container) {
    if (!container) return;
    container.innerHTML = '';

    function renderNode(key, value, parentElement, level) {
        const row = document.createElement('div');
        row.className = 'json-row';
        row.dataset.level = String(level);

        const isCollection = value && typeof value === 'object';
        const entries = Array.isArray(value) ? Array.from(value.entries()) : Object.entries(value || {});
        const hasChildren = isCollection && entries.length > 0;

        const toggle = document.createElement('span');
        toggle.className = 'json-toggle';
        toggle.textContent = hasChildren ? '▼' : ' ';
        toggle.style.visibility = hasChildren ? 'visible' : 'hidden';

        const keySpan = document.createElement('span');
        keySpan.className = 'json-key';
        keySpan.textContent = key;

        const valueSpan = document.createElement('span');
        const type = determineType(value);
        valueSpan.className = `json-value json-${type}`;
        if (type === 'object') {
            valueSpan.textContent = '{}';
        } else if (type === 'array') {
            valueSpan.textContent = '[]';
        } else {
            valueSpan.textContent = formatPrimitive(value, type);
        }

        const copyBtn = document.createElement('button');
        copyBtn.className = 'copy-btn';
        copyBtn.textContent = 'Copy';
        const copyValue = type === 'object' || type === 'array' ? JSON.stringify(value) : String(value ?? 'null');
        copyBtn.addEventListener('click', () => copyToClipboard(copyValue));

        row.append(toggle, keySpan, valueSpan, copyBtn);
        parentElement.appendChild(row);

        if (hasChildren) {
            const childrenWrapper = document.createElement('div');
            childrenWrapper.className = 'json-children';
            row.after(childrenWrapper);

            toggle.addEventListener('click', () => {
                const expanded = toggle.textContent === '▼';
                toggle.textContent = expanded ? '▶' : '▼';
                childrenWrapper.classList.toggle('collapsed', expanded);
            });

            for (const [childKey, childValue] of entries) {
                renderNode(String(childKey), childValue, childrenWrapper, level + 1);
            }
        }
    }

    renderNode('(root)', data, container, 0);
}

function determineType(value) {
    if (Array.isArray(value)) return 'array';
    if (value === null) return 'null';
    if (typeof value === 'number') return 'number';
    if (typeof value === 'boolean') return 'boolean';
    if (typeof value === 'string') return 'value';
    if (typeof value === 'object') return 'object';
    return 'value';
}

function formatPrimitive(value, type) {
    if (type === 'null') return 'null';
    if (value === undefined) return 'undefined';
    return String(value);
}

function copyToClipboard(text) {
    if (!text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).catch(() => {});
        return;
    }
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
}

function _syncMessagesPolling() {
    console.log('_syncMessagesPolling called, _mqttLastConnected:', window._mqttLastConnected);
    const shouldRun = Boolean(window._mqttLastConnected);
    
    if (!shouldRun) {
        if (_mqttMessagesPollTimer) {
            clearInterval(_mqttMessagesPollTimer);
            _mqttMessagesPollTimer = null;
        }
        return;
    }

    if (_mqttMessagesPollTimer) return;
    console.log('Starting messages polling...');
    refreshMQTTMessages().catch(() => {});
    _mqttMessagesPollTimer = setInterval(() => {
        refreshMQTTMessages().catch(() => {});
    }, 2000);  // Update every 2 seconds for live feel
}

// MQTT Detail & Health Functions
async function refreshMQTTDetails() {
    console.log('refreshMQTTDetails called');
    try {
        const r = await fetch('/api/mqtt/runtime/status', { method: 'GET' });
        const data = await r.json();
        console.log('MQTT Details response:', data);
        
        if (r.ok && data) {
            _updateMQTTDetails(data);
            return;
        }
        _clearMQTTDetails();
    } catch (e) {
        console.error('refreshMQTTDetails error:', e);
        _clearMQTTDetails();
    }
}

function _updateMQTTDetails(status) {
    // MQTT Detail Panel - Lite Version
    const statusEl_lite = document.getElementById('mqttStatus_lite');
    const brokerEl_lite = document.getElementById('mqttBroker_lite');
    const clientsEl_lite = document.getElementById('mqttClients_lite');
    
    if (statusEl_lite) {
        statusEl_lite.textContent = status.connected ? 'Verbunden' : 'Nicht verbunden';
        statusEl_lite.style.color = status.connected ? '#2ecc71' : '#e74c3c';
    }
    
    if (brokerEl_lite) {
        brokerEl_lite.textContent = status.broker || '-';
    }
    
    if (clientsEl_lite) {
        clientsEl_lite.textContent = '1';  // Wir haben immer 1 client (runtime)
    }
    
    // MQTT Detail Panel - Pro Version
    const statusEl_pro = document.getElementById('mqttStatus_pro');
    const brokerEl_pro = document.getElementById('mqttBroker_pro');
    const clientsEl_pro = document.getElementById('mqttClients_pro');
    
    if (statusEl_pro) {
        statusEl_pro.textContent = status.connected ? 'Verbunden' : 'Nicht verbunden';
        statusEl_pro.style.color = status.connected ? '#2ecc71' : '#e74c3c';
    }
    
    if (brokerEl_pro) {
        brokerEl_pro.textContent = status.broker || '-';
    }
    
    if (clientsEl_pro) {
        clientsEl_pro.textContent = '1';  // Wir haben immer 1 client (runtime)
    }
    
    // Health & Statistik Panel - Lite Version
    const msgSecEl_lite = document.getElementById('mqttMsgSec_lite');
    const errorsEl_lite = document.getElementById('mqttErrors_lite');
    const qosAvgEl_lite = document.getElementById('mqttQosAvg_lite');
    
    if (msgSecEl_lite) {
        // Calculate messages per second from uptime and message_count
        const msgCount = parseInt(status.message_count || 0);
        const uptime = status.uptime || '00:00:00';
        let msgPerSec = 0;
        
        try {
            const parts = uptime.split(':');
            if (parts.length === 3) {
                const hours = parseInt(parts[0]) || 0;
                const mins = parseInt(parts[1]) || 0;
                const secs = parseInt(parts[2]) || 0;
                const totalSecs = hours * 3600 + mins * 60 + secs;
                msgPerSec = totalSecs > 0 ? (msgCount / totalSecs).toFixed(2) : 0;
            }
        } catch (e) {
            msgPerSec = 0;
        }
        msgSecEl_lite.textContent = msgPerSec + ' msg/s';
    }
    
    if (errorsEl_lite) {
        errorsEl_lite.textContent = '0';  // No error tracking yet
    }
    
    if (qosAvgEl_lite) {
        qosAvgEl_lite.textContent = status.qos || '1';
    }
    
    // Health & Statistik Panel - Pro Version
    const msgSecEl_pro = document.getElementById('mqttMsgSec_pro');
    const errorsEl_pro = document.getElementById('mqttErrors_pro');
    const qosAvgEl_pro = document.getElementById('mqttQosAvg_pro');
    
    if (msgSecEl_pro) {
        // Calculate messages per second from uptime and message_count
        const msgCount = parseInt(status.message_count || 0);
        const uptime = status.uptime || '00:00:00';
        let msgPerSec = 0;
        
        try {
            const parts = uptime.split(':');
            if (parts.length === 3) {
                const hours = parseInt(parts[0]) || 0;
                const mins = parseInt(parts[1]) || 0;
                const secs = parseInt(parts[2]) || 0;
                const totalSecs = hours * 3600 + mins * 60 + secs;
                msgPerSec = totalSecs > 0 ? (msgCount / totalSecs).toFixed(2) : 0;
            }
        } catch (e) {
            msgPerSec = 0;
        }
        msgSecEl_pro.textContent = msgPerSec + ' msg/s';
    }
    
    if (errorsEl_pro) {
        errorsEl_pro.textContent = '0';  // No error tracking yet
    }
    
    if (qosAvgEl_pro) {
        qosAvgEl_pro.textContent = status.qos || '1';
    }
}

function _clearMQTTDetails() {
    const elements = [
        'mqttStatus_lite', 'mqttBroker_lite', 'mqttClients_lite',
        'mqttMsgSec_lite', 'mqttErrors_lite', 'mqttQosAvg_lite',
        'mqttStatus_pro', 'mqttBroker_pro', 'mqttClients_pro',
        'mqttMsgSec_pro', 'mqttErrors_pro', 'mqttQosAvg_pro'
    ];
    
    elements.forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '-';
    });
}

let _mqttDetailsPollTimer = null;

function _syncDetailsPoll() {
    console.log('_syncDetailsPoll called, _mqttLastConnected:', window._mqttLastConnected);
    const shouldRun = Boolean(window._mqttLastConnected);
    
    if (!shouldRun) {
        if (_mqttDetailsPollTimer) {
            clearInterval(_mqttDetailsPollTimer);
            _mqttDetailsPollTimer = null;
        }
        _clearMQTTDetails();
        return;
    }

    if (_mqttDetailsPollTimer) return;
    console.log('Starting details polling...');
    refreshMQTTDetails().catch(() => {});
    _mqttDetailsPollTimer = setInterval(() => {
        refreshMQTTDetails().catch(() => {});
    }, 5000);  // Update every 5 seconds
}

// Export globally
window.refreshMQTTTopics = refreshMQTTTopics;
window._renderTopics = _renderTopics;
window._syncTopicsPolling = _syncTopicsPolling;
window.refreshMQTTMessages = refreshMQTTMessages;
window._renderMessages = _renderMessages;
window._syncMessagesPolling = _syncMessagesPolling;
window.refreshMQTTDetails = refreshMQTTDetails;
window._updateMQTTDetails = _updateMQTTDetails;
window._syncDetailsPoll = _syncDetailsPoll;

console.log('✓ MQTT Topics & Messages functions exported from debug.js');

// ============================================
// JSON INSPECTOR FUNCTIONS
// ============================================

let jsonInspectorLimits = {
    max_size_mb: 5,
    max_depth: 50,
    allow_override: false
};

async function loadJsonInspectorLimits() {
    try {
        const res = await fetch('/api/config/current');
        if (!res.ok) return;
        const data = await res.json();
        const limits = data?.json_inspector;
        if (limits && typeof limits === 'object') {
            jsonInspectorLimits = {
                max_size_mb: limits.max_size_mb || 5,
                max_depth: limits.max_depth || 50,
                allow_override: limits.allow_override || false
            };
            updateJsonInspectorLimitDisplay();
        }
    } catch (err) {
        console.warn('[json-inspector] Failed to load limits', err);
    }
}

function updateJsonInspectorLimitDisplay() {
    const sizeEl = document.getElementById('json-limit-size');
    const depthEl = document.getElementById('json-limit-depth');
    const overrideEl = document.getElementById('json-limit-override');

    if (sizeEl) sizeEl.textContent = `${jsonInspectorLimits.max_size_mb} MB`;
    if (depthEl) depthEl.textContent = jsonInspectorLimits.max_depth.toString();
    if (overrideEl) overrideEl.textContent = jsonInspectorLimits.allow_override ? 'Yes' : 'No';
}

function calculateJsonDepth(obj, currentDepth = 0) {
    if (typeof obj !== 'object' || obj === null) return currentDepth;
    let maxDepth = currentDepth;
    for (const key in obj) {
        if (obj.hasOwnProperty(key)) {
            const depth = calculateJsonDepth(obj[key], currentDepth + 1);
            maxDepth = Math.max(maxDepth, depth);
        }
    }
    return maxDepth;
}

function validateJsonData(jsonData, jsonString) {
    const statusBadge = document.getElementById('json-inspector-status');
    const warningEl = document.getElementById('json-inspector-warning');

    if (!statusBadge || !warningEl) return { allowed: true, reason: null };

    const sizeMB = (new Blob([jsonString]).size) / (1024 * 1024);
    const depth = calculateJsonDepth(jsonData);

    let sizeExceeded = false;
    let depthExceeded = false;

    if (sizeMB > jsonInspectorLimits.max_size_mb) {
        sizeExceeded = true;
    }

    if (depth > jsonInspectorLimits.max_depth) {
        depthExceeded = true;
    }

    if (!sizeExceeded && !depthExceeded) {
        statusBadge.className = 'status-badge status-ok';
        statusBadge.textContent = 'Ready';
        warningEl.style.display = 'none';
        warningEl.textContent = '';
        return { allowed: true, reason: null };
    }

    const reasons = [];
    if (sizeExceeded) {
        reasons.push(`JSON size (${sizeMB.toFixed(2)} MB) exceeds configured limit (${jsonInspectorLimits.max_size_mb} MB)`);
    }
    if (depthExceeded) {
        reasons.push(`JSON depth (${depth}) exceeds configured limit (${jsonInspectorLimits.max_depth})`);
    }

    const reasonText = reasons.join('. ');

    if (jsonInspectorLimits.allow_override) {
        statusBadge.className = 'status-badge status-warn';
        statusBadge.textContent = 'Limit exceeded';
        warningEl.textContent = reasonText + '. Rendering continued.';
        warningEl.style.display = '';
        return { allowed: true, reason: reasonText };
    } else {
        statusBadge.className = 'status-badge status-error';
        statusBadge.textContent = 'Rendering blocked';
        warningEl.textContent = reasonText + '. Rendering blocked. Enable override in Config Manager to proceed.';
        warningEl.style.display = '';
        return { allowed: false, reason: reasonText };
    }
}

// ============================================
// DEPRECATED - JSON Inspector moved to json_inspector_new.js
// ============================================
// This section is kept for reference but no longer used
// The new JSON Inspector is in json_inspector_new.js

// State-Management für geöffnete JSON-Knoten (DEPRECATED)
let jsonTreeOpenPaths = new Set();

// DEPRECATED - Use json_inspector_new.js instead
// This function is no longer called
function renderJsonTree_DEPRECATED(jsonData) {
  const treeEl = document.getElementById('json-inspector-tree');
  if (!treeEl) {
    return;
  }

  // Function body removed - replaced by json_inspector_new.js
  console.warn('renderJsonTree_DEPRECATED called - use json_inspector_new.js instead');
  return;
}

// Helper: Extract JSON from text that may contain prefixes (timestamps, topics, etc.)
function parsePossiblyWrappedJSON(text) {
    try {
        return JSON.parse(text);
    } catch (e) {
        const start = text.indexOf('{');
        const end = text.lastIndexOf('}');
        if (start === -1 || end === -1 || end <= start) {
            throw e;
        }
        const extracted = text.slice(start, end + 1);
        const parsed = JSON.parse(extracted);

        // If the parsed object has a 'payload' field that's a JSON string, parse it
        if (parsed.payload && typeof parsed.payload === 'string') {
            // Check if payload is truncated
            if (parsed.payload.includes('...[truncated]')) {
                // Try to extract valid JSON from truncated payload
                const payloadStart = parsed.payload.indexOf('{');
                const truncPos = parsed.payload.indexOf('...[truncated]');
                if (payloadStart !== -1 && truncPos > payloadStart) {
                    // Find the last complete closing brace before truncation
                    const beforeTrunc = parsed.payload.slice(payloadStart, truncPos);
                    // Count braces to find matching close
                    let depth = 0;
                    let lastValidPos = -1;
                    for (let i = 0; i < beforeTrunc.length; i++) {
                        if (beforeTrunc[i] === '{') depth++;
                        if (beforeTrunc[i] === '}') {
                            depth--;
                            if (depth === 0) lastValidPos = i;
                        }
                    }
                    if (lastValidPos !== -1) {
                        const truncatedJson = beforeTrunc.slice(0, lastValidPos + 1);
                        try {
                            parsed.payload = JSON.parse(truncatedJson);
                            parsed._truncated = true;
                            return parsed;
                        } catch (e2) {
                            // Keep as string
                        }
                    }
                }
                parsed._truncated = true;
            } else {
                // Not truncated, try to parse normally
                try {
                    parsed.payload = JSON.parse(parsed.payload);
                } catch (payloadErr) {
                    // Keep as string if it's not valid JSON
                }
            }
        }

        return parsed;
    }
}

function initJsonInspector() {
    const uploadEl = document.getElementById('json-upload');
    if (!uploadEl) return;

    uploadEl.addEventListener('change', async (e) => {
        const file = e.target.files?.[0];
        if (!file) return;

        try {
            const text = await file.text();
            let jsonData;
            
            // Try to parse as regular JSON first
            try {
                jsonData = JSON.parse(text);
            } catch (firstErr) {
                // If that fails, try JSONL format (one JSON object per line)
                const lines = text.split('\n').filter(line => line.trim());
                const parsed = [];
                let hasAnyJson = false;

                for (const line of lines) {
                    // Skip lines that don't contain JSON (check for opening brace)
                    if (!line.includes('{')) {
                        continue;
                    }

                    try {
                        // Use robust parser that can extract JSON from log lines
                        const obj = parsePossiblyWrappedJSON(line);
                        parsed.push(obj);
                        hasAnyJson = true;
                    } catch (lineErr) {
                        // Skip lines that fail to parse (e.g., plain text log lines)
                        console.debug('[json-inspector] Skipping non-JSON line:', line.substring(0, 100));
                        continue;
                    }
                }

                if (hasAnyJson && parsed.length > 0) {
                    jsonData = parsed;
                } else {
                    // Last fallback: try to extract JSON from the whole text
                    jsonData = parsePossiblyWrappedJSON(text);
                }
            }

            const validation = validateJsonData(jsonData, JSON.stringify(jsonData));

            if (validation.allowed) {
                // JSON Inspector rendering is now handled by json_inspector_new.js
                // Clear warning if present
                const warningEl = document.getElementById('json-inspector-warning');
                if (warningEl) warningEl.style.display = 'none';

                // Auto-pause live updates when file is loaded
                if (!liveStatePaused) {
                    liveStatePaused = true;
                    liveStatePausedManually = true; // Treat file load as manual pause
                    const pauseBtn = document.getElementById('json-pause-btn');
                    if (pauseBtn) {
                        pauseBtn.textContent = '▶ Resume';
                        pauseBtn.title = 'Setze Live-Aktualisierung fort';
                    }
                    if (window.showToast) window.showToast('Live-Aktualisierung automatisch pausiert', 'info');
                }
            } else {
                const treeEl = document.getElementById('json-inspector-tree');
                if (treeEl) {
                    treeEl.innerHTML = '<div class="info-label">Rendering blocked due to limit violation.</div>';
                }
            }
        } catch (err) {
            console.error('[json-inspector] Parse error:', err);
            const statusBadge = document.getElementById('json-inspector-status');
            const warningEl = document.getElementById('json-inspector-warning');
            const treeEl = document.getElementById('json-inspector-tree');

            if (statusBadge) {
                statusBadge.className = 'status-badge status-error';
                statusBadge.textContent = 'Parse error';
            }
            if (warningEl) {
                warningEl.textContent = 'Fehler beim Parsen: ' + err.message;
                warningEl.style.display = '';
            }
            if (treeEl) {
                treeEl.innerHTML = '<div class="info-label" style="padding:20px; color:var(--error,#ff9a8a);">Fehler beim Parsen der Datei<br><br>' +
                    '<small style="opacity:0.7;">' + err.message + '</small></div>';
            }
        }
    });
}

window.loadJsonInspectorLimits = loadJsonInspectorLimits;
window.initJsonInspector = initJsonInspector;

// ============================================
// Live Payload - Frontend polling + rendering
// ============================================

let liveStatePollInterval = null;
let lastLiveState = null;
let lastLiveDeviceKeysCount = 0;
let lastLiveSelectedDevice = null;
let liveStatePaused = false;
let liveStatePausedManually = false; // Track if user manually paused
let lastMqttConnected = false; // Track MQTT connection state

function updateLivePayloadUI(state) {
  // Skip update if paused
  if (liveStatePaused) {
    console.log('[JSON Inspector] updateLivePayloadUI skipped - paused');
    return;
  }

  console.log('[JSON Inspector] updateLivePayloadUI called', { hasState: !!state, device: state?.device });

  if (!state) {
    setText('liveDeviceName', '-');
    setText('liveStatus', 'Status: -');
    setText('liveLastUpdate', 'Letztes Update: -');
    setText('liveJobName', 'Job: -');
    const pb = document.getElementById('liveProgressBar'); if (pb) pb.value = 0;
    setText('liveAmsInfo', 'AMS: -');
    return;
  }
  const device = state.device || '-';
  const ts = state.ts || null;
  const payload = state.payload || {};
  setText('liveDeviceName', device);
  // determine status
  const lastTs = ts ? Date.parse(ts) : null;
  const now = Date.now();
  let status = 'offline';
  if (lastTs && (now - lastTs) < 30000) {
    // within 30s, consider active
    const gstate = (payload?.print?.gcode_state || payload?.gcode_state || '').toString().toLowerCase();
    if (gstate && (gstate === 'running' || gstate === 'printing' || gstate === 'start')) status = 'printing';
    else status = 'idle';
  }
  const statusText = `Status: ${status}`;
  setText('liveStatus', statusText);
  // show relative time (Deutsch) with full timestamp as title
  if (ts) {
    const rel = relativeTime(ts);
    const full = new Date(ts).toLocaleString();
    const el = document.getElementById('liveLastUpdate');
    if (el) {
      el.textContent = `Letztes Update: ${rel}`;
      el.title = full;
    }
  } else {
    setText('liveLastUpdate', 'Letztes Update: -');
  }
  const jobname = (payload?.job?.name) || (payload?.print?.file?.name) || payload?.subtask_name || '-';
  setText('liveJobName', `Job: ${jobname}`);
  const progress = Number(payload?.print?.progress || payload?.progress || 0);
  const pb = document.getElementById('liveProgressBar');
  const pct = Number.isFinite(progress) ? Math.max(0, Math.min(100, Math.round(progress))) : 0;
  if (pb) pb.value = pct;
  // show percent text next to progress bar (insert if missing)
  let pctEl = document.getElementById('liveProgressPercent');
  if (!pctEl) {
    const container = document.getElementById('liveProgress');
    if (container) {
      pctEl = document.createElement('span');
      pctEl.id = 'liveProgressPercent';
      pctEl.style.cssText = 'margin-left:8px; font-weight:600; color:var(--text-dim);';
      container.appendChild(pctEl);
    }
  }
  if (pctEl) pctEl.textContent = `${pct}%`;
  // AMS short info
  const ams = payload?.ams || null;
  if (ams && Array.isArray(ams) && ams.length) {
    const first = ams[0];
    const slot = first?.trays?.[0]?.tray_id || first?.slot || '-';
    const material = first?.trays?.[0]?.material || first?.trays?.[0]?.tray_type || '-';
    const color = first?.trays?.[0]?.tray_color || first?.trays?.[0]?.color || '-';
    setText('liveAmsInfo', `AMS: slot=${slot}, material=${material}, color=${color}`);
  } else {
    setText('liveAmsInfo', 'AMS: -');
  }
  // JSON Inspector rendering is now handled by json_inspector_new.js
}

function relativeTime(ts) {
  try {
    const t = Date.parse(ts);
    if (!t) return new Date(ts).toLocaleString();
    const diff = Date.now() - t;
    const sec = Math.floor(diff / 1000);
    if (sec < 5) return 'gerade eben';
    if (sec < 60) return `vor ${sec} s`;
    const min = Math.floor(sec / 60);
    if (min < 60) return `vor ${min} min`;
    const h = Math.floor(min / 60);
    if (h < 24) return `vor ${h} h`;
    const d = Math.floor(h / 24);
    return `vor ${d} d`;
  } catch (e) {
    return new Date(ts).toLocaleString();
  }
}

async function copyJsonInspector() {
  try {
    const tree = document.getElementById('json-inspector-tree');
    if (!tree) return;
    // Prefer preformatted text content
    const txt = tree.innerText || tree.textContent || '';
    if (!txt) {
      if (window.showToast) window.showToast('Kein JSON zum Kopieren vorhanden', 'warning');
      return;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(txt);
      if (window.showToast) window.showToast('JSON kopiert', 'success');
    } else {
      // Fallback
      const ta = document.createElement('textarea');
      ta.value = txt;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      if (window.showToast) window.showToast('JSON kopiert', 'success');
    }
  } catch (e) {
    console.warn('copyJsonInspector failed', e);
    if (window.showToast) window.showToast('Kopieren fehlgeschlagen', 'error');
  }
}

function toggleLiveStatePause() {
  liveStatePaused = !liveStatePaused;
  liveStatePausedManually = liveStatePaused; // Track manual pause
  const btn = document.getElementById('json-pause-btn');
  const statusBadge = document.getElementById('json-inspector-status');

  if (liveStatePaused) {
    // Paused
    if (btn) {
      btn.textContent = '▶ Resume';
      btn.title = 'Setze Live-Aktualisierung fort';
    }
    if (statusBadge && statusBadge.textContent === 'Live') {
      statusBadge.className = 'status-badge status-warn';
      statusBadge.textContent = 'Paused';
    }
    if (window.showToast) window.showToast('Live-Aktualisierung pausiert', 'info');

    // Stop polling
    if (liveStatePollInterval) {
      clearInterval(liveStatePollInterval);
      liveStatePollInterval = null;
    }
  } else {
    // Resumed/Started
    if (btn) {
      btn.textContent = '⏸ Pause';
      btn.title = 'Pausiere Live-Aktualisierung';
    }
    if (statusBadge && (statusBadge.textContent === 'Paused' || statusBadge.textContent === 'Ready')) {
      statusBadge.className = 'status-badge status-ok';
      statusBadge.textContent = 'Live';
    }
    if (window.showToast) window.showToast('Live-Aktualisierung gestartet', 'success');

    // Start polling with selector
    startLiveStatePollingWithSelector();
  }
}

async function checkMqttConnectionStatus() {
  try {
    const res = await fetch('/api/mqtt/runtime/status');
    if (!res.ok) return false;
    const data = await res.json();
    const isConnected = data && data.connected === true;
    console.log('[JSON Inspector] MQTT status check:', { connected: isConnected, data });
    return isConnected;
  } catch (err) {
    console.warn('[JSON Inspector] MQTT status check failed:', err);
    return false;
  }
}

async function refreshLiveStateAll() {
  try {
    console.log('[JSON Inspector] refreshLiveStateAll - liveStatePaused:', liveStatePaused);

    // Check MQTT connection status
    const mqttConnected = await checkMqttConnectionStatus();

    // Auto-pause if MQTT disconnected (but don't override manual pause/file load)
    if (!mqttConnected && !liveStatePaused) {
      liveStatePaused = true;
      const btn = document.getElementById('json-pause-btn');
      const statusBadge = document.getElementById('json-inspector-status');
      if (btn) {
        btn.textContent = '▶ Resume';
        btn.title = 'Setze Live-Aktualisierung fort';
      }
      if (statusBadge && statusBadge.textContent === 'Live') {
        statusBadge.className = 'status-badge status-idle';
        statusBadge.textContent = 'No MQTT';
      }
      lastMqttConnected = false;
      console.log('[JSON Inspector] Auto-paused: MQTT disconnected');
      return;
    }

    // Auto-resume if MQTT connected AND not manually paused AND not showing file data
    if (mqttConnected && !lastMqttConnected && liveStatePaused && !liveStatePausedManually) {
      liveStatePaused = false;
      const btn = document.getElementById('json-pause-btn');
      const statusBadge = document.getElementById('json-inspector-status');
      if (btn) {
        btn.textContent = '⏸ Pause';
        btn.title = 'Pausiere Live-Aktualisierung';
      }
      if (statusBadge && statusBadge.textContent === 'No MQTT') {
        statusBadge.className = 'status-badge status-ok';
        statusBadge.textContent = 'Live';
      }
      console.log('[JSON Inspector] Auto-resumed: MQTT connected');
    }

    lastMqttConnected = mqttConnected;

    const res = await fetch('/api/live-state/');
    if (!res.ok) {
      console.warn('[JSON Inspector] API call failed:', res.status);
      return;
    }
    const data = await res.json();
    const keys = Object.keys(data || {});
    console.log('[JSON Inspector] Live-state data received:', { deviceCount: keys.length, keys });

    if (!keys.length) {
      console.log('[JSON Inspector] No devices found');
      updateLivePayloadUI(null);
      return;
    }
    // pick first device for now
    const first = data[keys[0]];
    if (!first) {
      console.warn('[JSON Inspector] First device has no data');
      return;
    }
    console.log('[JSON Inspector] Calling updateLivePayloadUI with device:', first.device);
    lastLiveState = first;
    updateLivePayloadUI(first);
  } catch (err) {
    console.error('[JSON Inspector] refresh failed', err);
  }
}

function startLiveStatePolling() {
  if (liveStatePollInterval) clearInterval(liveStatePollInterval);
  refreshLiveStateAll();
  liveStatePollInterval = setInterval(refreshLiveStateAll, 2500);
}

// start polling when JSON inspector initialized so user sees live data
const _origInitJsonInspector = typeof initJsonInspector === 'function' ? initJsonInspector : null;
function _wrappedInitJsonInspector() {
  if (_origInitJsonInspector) _origInitJsonInspector();
  // Auto-start polling if MQTT is connected
  initEmptyJsonInspector();
}
window.initJsonInspector = _wrappedInitJsonInspector;

async function initEmptyJsonInspector() {
  const treeEl = document.getElementById('json-inspector-tree');
  const statusBadge = document.getElementById('json-inspector-status');
  const pauseBtn = document.getElementById('json-pause-btn');

  // Check if MQTT is already connected
  try {
    const mqttConnected = await checkMqttConnectionStatus();

    if (mqttConnected) {
      // MQTT verbunden - Auto-start live updates
      console.log('[JSON Inspector] MQTT connected - auto-starting live updates');

      if (statusBadge) {
        statusBadge.className = 'status-badge status-ok';
        statusBadge.textContent = 'Live';
      }

      if (pauseBtn) {
        pauseBtn.textContent = '⏸ Pause';
        pauseBtn.title = 'Live-Aktualisierung pausieren';
      }

      // Start polling automatically (this will populate the tree)
      liveStatePaused = false;
      liveStatePausedManually = false;
      console.log('[JSON Inspector] Starting polling...');
      startLiveStatePollingWithSelector();

    } else {
      // MQTT nicht verbunden - zeige Platzhalter
      console.log('[JSON Inspector] MQTT not connected - showing placeholder');

      if (treeEl) {
        treeEl.innerHTML = '<div class="info-label" style="text-align:center; padding:40px 20px; opacity:0.5;">Keine Daten vorhanden<br><br>MQTT nicht verbunden. Lade eine Datei oder klicke auf <strong>▶ Start</strong></div>';
      }

      if (statusBadge) {
        statusBadge.className = 'status-badge status-idle';
        statusBadge.textContent = 'Ready';
      }

      if (pauseBtn) {
        pauseBtn.textContent = '▶ Start';
        pauseBtn.title = 'Starte Live-Aktualisierung';
      }

      // Set initial paused state
      liveStatePaused = true;
      liveStatePausedManually = false;
    }
  } catch (e) {
    // Error checking MQTT status - default to paused state
    console.warn('[JSON Inspector] Error checking MQTT status:', e);

    if (treeEl) {
      treeEl.innerHTML = '<div class="info-label" style="text-align:center; padding:40px 20px; opacity:0.5;">Keine Daten vorhanden<br><br>Lade eine Datei oder klicke auf <strong>▶ Start</strong></div>';
    }

    if (statusBadge) {
      statusBadge.className = 'status-badge status-idle';
      statusBadge.textContent = 'Ready';
    }

    if (pauseBtn) {
      pauseBtn.textContent = '▶ Start';
      pauseBtn.title = 'Starte Live-Aktualisierung';
    }

    liveStatePaused = true;
    liveStatePausedManually = false;
  }
}

async function populateLiveDeviceSelector() {
  try {
    const res = await fetch('/api/live-state');
    if (!res.ok) return;
    const data = await res.json();
    const sel = document.getElementById('liveDeviceSelect');
    if (!sel) return;
    // preserve selection if possible
    const prevSelected = sel.value || lastLiveSelectedDevice || null;
    const prevCount = lastLiveDeviceKeysCount || 0;
    sel.innerHTML = '';
    const keys = Object.keys(data || {});
    keys.forEach(k => {
      const opt = document.createElement('option');
      opt.value = k;
      opt.textContent = k;
      sel.appendChild(opt);
    });
    // ensure only one change listener: replace node then operate on the new element
    const cloned = sel.cloneNode(true);
    sel.replaceWith(cloned);
    const newSel = document.getElementById('liveDeviceSelect');
    if (newSel) {
      newSel.addEventListener('change', () => {
        const v = newSel.value;
        lastLiveSelectedDevice = v;
        if (v && data[v]) updateLivePayloadUI(data[v]);
      });
      // restore selection if still present
      if (prevSelected && keys.includes(prevSelected)) {
        newSel.value = prevSelected;
        lastLiveSelectedDevice = prevSelected;
      } else if (keys.length && keys.length > prevCount) {
        // new device(s) added -> auto-select the last one
        const last = keys[keys.length - 1];
        newSel.value = last;
        lastLiveSelectedDevice = last;
      } else if (keys.length) {
        newSel.value = keys[0];
        lastLiveSelectedDevice = keys[0];
      }
      if (lastLiveSelectedDevice && data[lastLiveSelectedDevice]) updateLivePayloadUI(data[lastLiveSelectedDevice]);
    }
    lastLiveDeviceKeysCount = keys.length;
  } catch (e) {
    // ignore
  }
}

// enhance polling to refresh selector list
function startLiveStatePollingWithSelector() {
  startLiveStatePolling();
  if (liveStatePollInterval) clearInterval(liveStatePollInterval);
  refreshLiveStateAll();
  populateLiveDeviceSelector();
  liveStatePollInterval = setInterval(async () => {
    await refreshLiveStateAll();
    await populateLiveDeviceSelector();
  }, 2500);
}

console.log('✓ JSON Inspector functions registered');

// ============================================
// SERVICES TAB FUNCTIONS
// ============================================

async function loadServicesData() {
    try {
        const [perfRes, sysRes] = await Promise.all([
            fetch('/api/debug/performance'),
            fetch('/api/debug/system_status')
        ]);

        if (!perfRes.ok || !sysRes.ok) {
            console.warn('[services] Failed to load data');
            return;
        }

        const perfData = await perfRes.json();
        const sysData = await sysRes.json();

        updateServicesDisplay(perfData, sysData);
    } catch (err) {
        console.error('[services] Error loading data', err);
    }
}

function updateServicesDisplay(perf, sys) {
    // Runtime & Process
    const pidEl = document.getElementById('service-pid');
    const cpuEl = document.getElementById('service-cpu');
    const memoryEl = document.getElementById('service-memory');
    const threadsEl = document.getElementById('service-threads');
    const runtimeStatusEl = document.getElementById('service-runtime-status');

    if (pidEl) pidEl.textContent = 'N/A';
    if (cpuEl && perf?.cpu_percent) cpuEl.textContent = `${perf.cpu_percent}%`;
    if (memoryEl && perf?.ram_used_mb && perf?.ram_total_mb) {
        const percent = ((perf.ram_used_mb / perf.ram_total_mb) * 100).toFixed(1);
        memoryEl.textContent = `${percent}% (${perf.ram_used_mb} MB / ${perf.ram_total_mb} MB)`;
    }
    if (threadsEl) threadsEl.textContent = 'N/A';

    if (runtimeStatusEl) {
        runtimeStatusEl.className = 'status-badge status-ok';
        runtimeStatusEl.textContent = 'Running';
    }

    // Server & Environment
    const startedEl = document.getElementById('service-started');
    const uptimeEl = document.getElementById('service-uptime');
    const platformEl = document.getElementById('service-platform');
    const hostnameEl = document.getElementById('service-hostname');
    const pythonEl = document.getElementById('service-python');
    const portEl = document.getElementById('service-port');
    const environment = sys?.environment || {};
    const serverInfo = environment.server || {};
    const uptimeSeconds = Number(perf?.backend_uptime_s);

    if (startedEl) {
        if (Number.isFinite(uptimeSeconds)) {
            const startedAtMs = Date.now() - uptimeSeconds * 1000;
            startedEl.textContent = new Date(startedAtMs).toLocaleString();
        } else {
            startedEl.textContent = '-';
        }
    }
    if (uptimeEl && Number.isFinite(uptimeSeconds)) {
        const hours = Math.floor(uptimeSeconds / 3600);
        const minutes = Math.floor((uptimeSeconds % 3600) / 60);
        const seconds = Math.floor(uptimeSeconds % 60);
        uptimeEl.textContent = `${hours}h ${minutes}m ${seconds}s`;
    }
    if (platformEl) {
        const platformLabel = environment.platform
            ? environment.platform_release && environment.platform_release !== environment.platform
                ? `${environment.platform} ${environment.platform_release}`
                : environment.platform
            : environment.platform_details || '-';
        platformEl.textContent = platformLabel;
    }
    if (hostnameEl) hostnameEl.textContent = environment.hostname || '-';
    if (pythonEl) {
        const pythonLine = environment.python_version ? environment.python_version.split('\n')[0] : '-';
        pythonEl.textContent = pythonLine;
    }
    if (portEl) {
        portEl.textContent =
            serverInfo.port !== undefined && serverInfo.port !== null ? String(serverInfo.port) : '-';
    }
}

function initServicesButtons() {
    const restartBtn = document.getElementById('service-restart-btn');
    if (restartBtn) {
        restartBtn.addEventListener('click', () => {
            alert('Backend restart functionality not implemented yet.');
        });
    }

    const dockerUpBtn = document.getElementById('service-docker-up-btn');
    if (dockerUpBtn) {
        dockerUpBtn.addEventListener('click', async () => {
            alert('Docker up functionality not implemented yet.');
        });
    }

    const dockerDownBtn = document.getElementById('service-docker-down-btn');
    if (dockerDownBtn) {
        dockerDownBtn.addEventListener('click', async () => {
            alert('Docker down functionality not implemented yet.');
        });
    }

    const dockerStatusBtn = document.getElementById('service-docker-status-btn');
    if (dockerStatusBtn) {
        dockerStatusBtn.addEventListener('click', async () => {
            alert('Docker status functionality not implemented yet.');
        });
    }

    // Test buttons with locked state management
    const testButtons = [
        { id: 'service-test-smoke-btn', name: 'Smoke CRUD', endpoint: '/api/services/tests/smoke' },
        { id: 'service-test-db-btn', name: 'DB CRUD', endpoint: '/api/services/tests/db' },
        { id: 'service-test-all-btn', name: 'All Tests', endpoint: '/api/services/tests/all' },
        { id: 'service-test-coverage-btn', name: 'Coverage', endpoint: '/api/services/tests/coverage' }
    ];
    
    testButtons.forEach(config => {
        const btn = document.getElementById(config.id);
        if (btn) {
            // Store original label
            btn.setAttribute('data-original-label', btn.textContent);
            btn.setAttribute('data-test-name', config.name);
            
            btn.addEventListener('click', async () => {
                // Only allow click if button is not disabled
                if (btn.disabled) return;
                
                // Set to running state
                btn.disabled = true;
                btn.textContent = 'Running…';
                btn.className = 'btn btn-secondary';
                
                try {
                    const response = await fetch(config.endpoint, { method: 'POST' });
                    const data = await response.json();
                    
                    // Evaluate result and lock button in final state
                    if (data.status === 'ok') {
                        btn.className = 'btn btn-success';
                        btn.textContent = 'Success';
                        if (window.showToast) {
                            window.showToast(`${config.name} erfolgreich`, 'success');
                        }
                    } else if (data.status === 'fail') {
                        btn.className = 'btn btn-error';
                        btn.textContent = 'Failed';
                        if (window.showToast) {
                            window.showToast(`${config.name} fehlgeschlagen`, 'error');
                        }
                    } else if (data.status === 'blocked') {
                        btn.className = 'btn btn-warning';
                        btn.textContent = 'Blocked';
                        if (window.showToast) {
                            window.showToast('Test konnte nicht ausgeführt werden', 'warning');
                        }
                    } else {
                        // Unknown status, treat as fail
                        btn.className = 'btn btn-error';
                        btn.textContent = 'Failed';
                        if (window.showToast) {
                            window.showToast(`${config.name} fehlgeschlagen`, 'error');
                        }
                    }
                    
                    // Button stays disabled (locked)
                } catch (error) {
                    // Network or other error - lock as blocked
                    btn.className = 'btn btn-warning';
                    btn.textContent = 'Blocked';
                    if (window.showToast) {
                        window.showToast('Test konnte nicht ausgeführt werden', 'warning');
                    }
                    // Button stays disabled (locked)
                    console.error('Test execution error:', error);
                }
            });
        }
    });

    // Dependency buttons
    const depsButtons = [
        'service-deps-install-btn',
        'service-deps-update-btn',
        'service-deps-list-btn',
        'service-deps-outdated-btn'
    ];
    depsButtons.forEach(id => {
        const btn = document.getElementById(id);
        if (btn) {
            btn.addEventListener('click', () => {
                alert('Dependency functionality not implemented yet.');
            });
        }
    });
}

window.loadServicesData = loadServicesData;
window.initServicesButtons = initServicesButtons;

console.log('✓ Services tab functions registered');
