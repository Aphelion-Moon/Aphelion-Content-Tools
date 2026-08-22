(() => {
  'use strict';

  // Shared "Database and Git" status widget -- shown below the page title on every tool page (see the
  // `<div id="store-status-widget">` inserted right after `<header class="hero">`, above #reference-panel,
  // in each page's HTML). A compact always-visible summary (row count, disk size, whether a background
  // job is running) with the fuller per-table breakdown and job detail available on hover via
  // info-tooltip.js -- the full console, Stop control, and job buttons stay on File Management's
  // "Database and Git" panel; this is a glanceable status indicator, not a second copy of that panel.

  const POLL_INTERVAL_MS = 5000;

  const containers = new Set();
  let cachedHealth = null;
  let cachedActiveRuns = [];
  let pollTimer = null;

  async function requestJson(path) {
    const response = await fetch(path);
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : {};
    if (!response.ok) throw new Error(payload.error || ('Request failed (' + response.status + ')'));
    return payload;
  }

  function formatBytes(bytes) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    let value = bytes;
    let unitIndex = 0;
    while (value >= 1024 && unitIndex < units.length - 1) {
      value /= 1024;
      unitIndex += 1;
    }
    return (unitIndex === 0 ? value : value.toFixed(1)) + ' ' + units[unitIndex];
  }

  function formatElapsed(queuedAt) {
    const seconds = Math.max(0, Math.round(Date.now() / 1000 - queuedAt));
    if (seconds < 60) return seconds + 's';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return minutes + 'm ' + (seconds % 60) + 's';
    const hours = Math.floor(minutes / 60);
    return hours + 'h ' + (minutes % 60) + 'm';
  }

  function buildHealthTooltipContent() {
    const wrapper = document.createElement('div');
    if (!cachedHealth) {
      wrapper.textContent = 'Database health unavailable.';
      return wrapper;
    }
    const lastWrite = cachedHealth.last_write_time
      ? new Date(cachedHealth.last_write_time * 1000).toLocaleString()
      : 'never';
    const summary = document.createElement('p');
    summary.textContent = 'Last write: ' + lastWrite;
    wrapper.append(summary);
    const table = document.createElement('div');
    table.className = 'info-tooltip-table';
    for (const [name, count] of Object.entries(cachedHealth.tables || {})) {
      const row = document.createElement('span');
      row.textContent = name + ': ' + count.toLocaleString();
      table.append(row);
    }
    wrapper.append(table);
    return wrapper;
  }

  function buildActiveTooltipContent() {
    const wrapper = document.createElement('div');
    if (!cachedActiveRuns.length) {
      wrapper.textContent = 'No job is running.';
      return wrapper;
    }
    for (const run of cachedActiveRuns) {
      const line = document.createElement('p');
      line.textContent = (run.tool_label || run.tool_id) + ' -- running for ' + formatElapsed(run.queued_at);
      wrapper.append(line);
    }
    return wrapper;
  }

  function navigateToFileManagement(event) {
    event.stopPropagation();
    window.dispatchEvent(new CustomEvent('aphelion:navigate', {detail: {tool: 'file-management', href: '/file-management'}}));
  }

  function navigateToParsecSettings(event) {
    event.stopPropagation();
    window.dispatchEvent(new CustomEvent('aphelion:navigate', {detail: {tool: 'parsec', href: '/parsec'}}));
  }

  const PAT_LINES = [
    'Rows: counted. Naps: pending.',
    'All quiet on the database front!',
    '*wags tail*',
    'Good data. Good day.',
    'Sniffing for stale fragments...',
  ];

  // Hidden easter egg: enough rapid pats in a row (see ParsecInstance.registerPat) switches her reaction
  // from a normal happy wag to "twerking" -- a repurposed leftover animation that was originally (and
  // mistakenly) used as her idle loop, before turning out to look like a sit-down/stand-up transition.
  const TWERK_LINES = [
    "okay THAT'S enough patting",
    "you found the secret. weird flex but ok",
    '*aggressive tail action*',
    "we don't talk about this one",
  ];

  function patParsec(event) {
    event.stopPropagation();
    const instance = event.currentTarget.parsec;
    const reaction = instance?.registerPat ? instance.registerPat() : (instance?.react('happy'), 'happy');
    const lines = reaction === 'twerking' ? TWERK_LINES : PAT_LINES;
    window.AphelionParsec?.announce(lines[Math.floor(Math.random() * lines.length)], {kind: 'info', tool: 'parsec'});
  }

  // Builds the widget's elements exactly once per mounted container, then only ever updates their
  // text/class/state on later polls -- rebuilding them every poll (every 5s) would tear down and
  // recreate the very elements info-tooltip.js has attached hover/focus listeners to (and may currently
  // be showing a tooltip anchored on), and would restart Parsec's animation/position from scratch.
  function ensureElements(container) {
    let summaryButton = container.querySelector('.store-status-summary');
    let statusPill = container.querySelector('.store-status-pill');
    let petBox = container.querySelector('.store-status-pet-box');
    if (summaryButton && statusPill && petBox) return {summaryButton, statusPill, petBox};

    summaryButton = document.createElement('button');
    summaryButton.type = 'button';
    summaryButton.className = 'store-status-summary';
    summaryButton.addEventListener('click', navigateToFileManagement);
    window.AphelionTooltip?.attach(summaryButton, {getContent: buildHealthTooltipContent, placement: 'bottom-start'});

    statusPill = document.createElement('button');
    statusPill.type = 'button';
    statusPill.addEventListener('click', navigateToFileManagement);
    window.AphelionTooltip?.attach(statusPill, {getContent: buildActiveTooltipContent, placement: 'bottom-start'});

    petBox = document.createElement('div');
    petBox.className = 'store-status-pet-box';
    petBox.addEventListener('click', patParsec);

    const settingsGear = document.createElement('button');
    settingsGear.type = 'button';
    settingsGear.className = 'store-status-pet-settings';
    settingsGear.setAttribute('aria-label', "Parsec's settings");
    settingsGear.title = "Parsec's settings";
    settingsGear.textContent = '⚙';
    settingsGear.addEventListener('click', navigateToParsecSettings);
    petBox.append(settingsGear);

    // mount() looks up which tool this box belongs to via `.closest('[data-tool]')`, which needs petBox
    // to already be attached under the tool's `data-tool`-bearing root element -- it has to be appended
    // to `container` (already inside that tree) *before* mount() runs, not after, or the lookup finds
    // nothing and Parsec never gets registered as "the instance for this tool".
    container.append(summaryButton, statusPill, petBox);
    petBox.parsec = window.AphelionParsec?.mount(petBox) || null;

    return {summaryButton, statusPill, petBox};
  }

  function renderInto(container) {
    const {summaryButton, statusPill, petBox} = ensureElements(container);

    const totalRows = cachedHealth ? cachedHealth.total_rows.toLocaleString() : '…';
    const diskSize = cachedHealth ? formatBytes(cachedHealth.disk_bytes) : '';
    summaryButton.textContent = cachedHealth ? totalRows + ' rows · ' + diskSize : 'Loading database status…';

    const isRunning = cachedActiveRuns.length > 0;
    statusPill.className = 'store-status-pill' + (isRunning ? ' is-running' : ' is-idle');
    statusPill.textContent = isRunning
      ? '● Running: ' + (cachedActiveRuns[0].tool_label || cachedActiveRuns[0].tool_id)
      : 'Idle';

    petBox.parsec?.setState(isRunning ? 'working' : 'idle');
  }

  function renderAll() {
    for (const container of containers) {
      if (container.isConnected) renderInto(container);
    }
  }

  async function poll() {
    try {
      const [health, active] = await Promise.all([
        requestJson('/api/store/health'),
        requestJson('/api/tools/active'),
      ]);
      cachedHealth = health;
      cachedActiveRuns = active.active_runs || [];
    } catch (error) {
      console.error(error);
    }
    renderAll();
  }

  function ensurePolling() {
    if (pollTimer !== null) return;
    poll();
    pollTimer = window.setInterval(poll, POLL_INTERVAL_MS);
  }

  function mount(container) {
    if (!container || containers.has(container)) return;
    containers.add(container);
    renderInto(container);
    ensurePolling();
  }

  if (typeof window !== 'undefined') {
    window.AphelionStoreStatus = {mount};
  }

  // On a hard page load, shell.js's own init() runs (and would try to mount this widget) before this
  // script's tag executes -- since it always loads after shell.js -- so `window.AphelionStoreStatus`
  // doesn't exist yet at that point and shell.js's call is a no-op. Pick up any `#store-status-widget`
  // already in the DOM here instead, matching references-panel.js's documented workaround for the same
  // load-order gotcha; the SPA nav-click path (shell.js's loadView/registerView) still mounts new views
  // directly since this script is already loaded by the time later tools activate.
  if (typeof document !== 'undefined') {
    document.querySelectorAll('#store-status-widget').forEach(mount);
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {formatBytes, formatElapsed};
  }
})();
