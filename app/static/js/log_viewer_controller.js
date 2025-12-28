// Controller: loads logs from API and renders via LogViewerRenderer
(function(){
  // Lokaler State (ohne window.LogViewerState)
  let allLogs = [];
  let filteredLogs = [];

  async function loadLogs(){
    const root = document.getElementById('log-entries');
    if (root) root.textContent = 'Lade Logs...';

    // Lese aktuelles Modul aus Dropdown
    const moduleSelect = document.getElementById('logModuleSelect');
    const limitSelect = document.getElementById('logLimitSelect');
    const module = moduleSelect ? moduleSelect.value : 'app';
    const limit = limitSelect ? limitSelect.value : '500';

    try{
      const res = await fetch(`/api/debug/logs?module=${module}&limit=${limit}`);
      const data = await res.json();
      let items = [];

      // API gibt { logs: [...], count: X, module: "..." } zurück
      if (Array.isArray(data.logs)) {
        items = data.logs;
      } else if (Array.isArray(data.items)) {
        items = data.items;
      } else if (typeof data.lines === 'string') {
        items = data.lines.split('\n').map(m=>({level:'INFO', module:module, message:m}));
      } else if (Array.isArray(data.lines)) {
        items = data.lines.map(m=>({level:'INFO', module:module, message:m}));
      }

      // Store und Render via lokale Filter
      allLogs = items;
      populateModuleOptions(allLogs);
      applyFilters();

      // Update Last Update Zeit
      const lastUpdateEl = document.getElementById('logLastUpdate');
      if (lastUpdateEl) {
        const now = new Date();
        lastUpdateEl.textContent = now.toLocaleTimeString('de-DE');
      }
    } catch (err) {
      console.error('Fehler beim Laden der Logs:', err);
      const rootEl = document.getElementById('log-entries');
      if (rootEl) rootEl.textContent = `Fehler beim Laden der Logs für Modul "${module}": ${err.message}`;
    }
  }

  function populateModuleOptions(items){
    const modSel = document.getElementById('logModuleFilter');
    if (!modSel) return;
    const mods = new Set();
    (items||[]).forEach(it => {
      const msg = (it.message ?? it.text ?? '').toString();
      const inferred = (msg.match(/\[(.*?)\]/)?.[1] || 'app');
      const mod = (it.module ?? inferred).toString();
      if (mod) mods.add(mod);
    });
    const prev = modSel.value;
    const options = ['','...'].slice(0,1); // ensure empty 'Alle'
    modSel.innerHTML = '';
    const allOpt = document.createElement('option');
    allOpt.value = '';
    allOpt.textContent = 'Modul: Alle';
    modSel.appendChild(allOpt);
    Array.from(mods).sort((a,b)=>a.localeCompare(b)).forEach(m => {
      const o = document.createElement('option');
      o.value = m;
      o.textContent = m;
      modSel.appendChild(o);
    });
    // restore previous selection if still present
    if (prev && Array.from(mods).includes(prev)) {
      modSel.value = prev;
    } else {
      modSel.value = '';
    }
  }

  function applyFilters(){
    const level = document.getElementById('logLevelFilter')?.value || '';
    const moduleSel = document.getElementById('logModuleFilter')?.value || '';
    const search = (document.getElementById('logSearchInput')?.value || '').toLowerCase();

    filteredLogs = (allLogs || []).filter(log => {
      // Heuristik: Level und Modul aus Text ableiten, falls Felder fehlen
      const rawText = (log.message || log.text || '').toString();
      const lvl = (log.level ? String(log.level) : ( /\b(ERROR|CRITICAL)\b/i.test(rawText) ? 'ERROR' : /\bWARNING|WARN\b/i.test(rawText) ? 'WARNING' : /\bDEBUG\b/i.test(rawText) ? 'DEBUG' : 'INFO'));
      const mod = (log.module ? String(log.module) : (rawText.match(/\[(.*?)\]/)?.[1] || 'app'));
      if (level && lvl !== level) return false;
      if (moduleSel && mod !== moduleSel) return false;
      if (search) {
        const text = rawText.toLowerCase();
        if (!text.includes(search)) return false;
      }
      return true;
    });

    window.LogViewerRenderer?.renderLogs(filteredLogs);
  }

  function setupToolbar(){
    const reload = document.getElementById('logReloadBtn');
    const pause = document.getElementById('logPauseBtn');
    const lvl = document.getElementById('logLevelFilter');
    const mod = document.getElementById('logModuleFilter');
    const q = document.getElementById('logSearchInput');

    // Modul-Selector (lädt neue Logs bei Änderung)
    const moduleSelect = document.getElementById('logModuleSelect');
    const limitSelect = document.getElementById('logLimitSelect');

    if (reload) reload.onclick = loadLogs;

    // Modul-Wechsel → Logs neu laden
    if (moduleSelect) moduleSelect.onchange = loadLogs;
    if (limitSelect) limitSelect.onchange = loadLogs;

    // Pause-Button: toggelt nur Label (reine UI, da Autoscroll lokal nicht verwaltet wird)
    if (pause) pause.onclick = () => {
      pause.textContent = (pause.textContent === 'Pause') ? 'Fortsetzen' : 'Pause';
    };
    if (lvl) lvl.onchange = applyFilters;
    if (mod) mod.onchange = applyFilters;
    if (q) q.oninput = applyFilters;
  }

  function observePanel(){
    const panel = document.getElementById('panel-logs');
    if (!panel) return;
    const obs = new MutationObserver(() => {
      if (panel.style.display !== 'none') loadLogs();
    });
    obs.observe(panel, { attributes: true, attributeFilter: ['style'] });
  }

  function setupClickPause(){
    const container = document.getElementById('log-entries');
    if (!container) return;
    container.addEventListener('click', (e) => {
      if (e.target.classList.contains('log-toggle') || e.target.classList.contains('log-line')) {
        const pause = document.getElementById('logPauseBtn');
        if (pause) pause.textContent = 'Fortsetzen';
      }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    setupToolbar();
    observePanel();
    setupClickPause();
    loadLogs();
  });

  window.LogViewerController = { loadLogs };
})();