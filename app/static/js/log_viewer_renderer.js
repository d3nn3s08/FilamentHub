// Renderer for new Log Viewer (DOM only, no state)
// Minimal window-based renderer (no modules)
(function(){
  function formatTimestamp(ts){
    if (!ts) return '';
    try {
      const d = new Date(ts);
      if (isNaN(d.getTime())) return '';
      const hh = String(d.getHours()).padStart(2,'0');
      const mm = String(d.getMinutes()).padStart(2,'0');
      const ss = String(d.getSeconds()).padStart(2,'0');
      return `${hh}:${mm}:${ss}`;
    } catch { return ''; }
  }
  function splitMessage(message){
    const text = (message ?? '').toString();
    const parts = text.split(/\r?\n/);
    return { first: parts[0] ?? '', rest: parts.slice(1).join('\n') };
  }
  function normalizeLevel(level){
    const lv = (level ?? 'INFO').toString().toUpperCase();
    return lv === 'WARN' ? 'WARNING' : lv;
  }
  function levelClass(level){
    const lv = normalizeLevel(level);
    if (lv === 'ERROR' || lv === 'CRITICAL') return 'log-error';
    if (lv === 'WARNING') return 'log-warning';
    if (lv === 'DEBUG') return 'log-debug';
    return 'log-info';
  }
  function renderLogs(items){
    const root = document.getElementById('log-entries');
    if (!root) return;
    root.innerHTML = '';
    (items || []).forEach(it => {
      const lv = normalizeLevel(it.level);
      const mod = (it.module ?? 'app').toString();
      const ts = it.timestamp || it.time || it.created_at || null;
      const msg = (it.message ?? it.text ?? '').toString();
      const { first, rest } = splitMessage(msg);

      const line = document.createElement('div');
      line.className = `log-line ${levelClass(lv)}`;
      line.dataset.level = lv;
      line.dataset.module = mod;

      const summary = document.createElement('div');
      summary.className = 'log-summary';

      const lvlEl = document.createElement('span');
      lvlEl.className = 'log-level';
      lvlEl.textContent = lv;

      const tsText = formatTimestamp(ts);
      let tsEl = null;
      if (tsText) {
        tsEl = document.createElement('span');
        tsEl.className = 'log-timestamp';
        tsEl.textContent = tsText;
      }

      const msgEl = document.createElement('span');
      msgEl.className = 'log-message';
      msgEl.textContent = first;

      summary.appendChild(lvlEl);
      if (tsEl) summary.appendChild(tsEl);
      summary.appendChild(msgEl);

      let toggleBtn = null;
      let toggleIcon = null;
      let stackEl = null;
      if (rest.trim().length > 0){
        toggleBtn = document.createElement('button');
        toggleBtn.className = 'log-toggle';
        toggleBtn.type = 'button';
        toggleBtn.textContent = 'Details';
        stackEl = document.createElement('pre');
        stackEl.className = 'log-stacktrace';
        stackEl.textContent = rest;
        toggleBtn.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          const isOpen = line.classList.toggle('expanded');
          toggleBtn.textContent = isOpen ? 'Schließen' : 'Details';
          if (toggleIcon) toggleIcon.textContent = isOpen ? '▾' : '▸';
        });
        // Klick auf gesamte Zeile/summary toggelt ebenfalls
        line.addEventListener('click', () => {
          const isOpen = line.classList.toggle('expanded');
          if (toggleBtn) toggleBtn.textContent = isOpen ? 'Schließen' : 'Details';
          if (toggleIcon) toggleIcon.textContent = isOpen ? '▾' : '▸';
        });
        summary.addEventListener('click', (e) => {
          // Falls Button geklickt, ist bereits behandelt
          if (e.target === toggleBtn) return;
          const isOpen = line.classList.toggle('expanded');
          if (toggleBtn) toggleBtn.textContent = isOpen ? 'Schließen' : 'Details';
          if (toggleIcon) toggleIcon.textContent = isOpen ? '▾' : '▸';
        });
        // dezentes Icon rechts zur visuellen Andeutung
        toggleIcon = document.createElement('span');
        toggleIcon.className = 'log-toggle-icon';
        toggleIcon.textContent = '▸';
        summary.appendChild(toggleBtn);
        summary.appendChild(toggleIcon);
      } else {
        // Einstzeilige Logs: Zeilenklick toggelt und zeigt eine dezente Detailfläche
        stackEl = document.createElement('pre');
        stackEl.className = 'log-stacktrace';
        stackEl.textContent = 'Keine weiteren Details';
        // dezentes Icon rechts
        toggleIcon = document.createElement('span');
        toggleIcon.className = 'log-toggle-icon';
        toggleIcon.textContent = '▸';
        line.addEventListener('click', () => {
          line.classList.toggle('expanded');
          if (toggleIcon) toggleIcon.textContent = line.classList.contains('expanded') ? '▾' : '▸';
        });
        summary.addEventListener('click', () => {
          line.classList.toggle('expanded');
          if (toggleIcon) toggleIcon.textContent = line.classList.contains('expanded') ? '▾' : '▸';
        });
      }
      line.appendChild(summary);
      if (stackEl) line.appendChild(stackEl);
      root.appendChild(line);
    });
  }
  window.LogViewerRenderer = { renderLogs };
})();