(() => {
  'use strict';

  const LOG_REFRESH_MS = 5000;

  function getPetInstance() {
    const box = document.querySelector('#tool-view-parsec .store-status-pet-box')
      || document.querySelector('.store-status-pet-box');
    return box ? box.parsec : null;
  }

  function initMotionControl() {
    const select = document.querySelector('#parsec-motion-select');
    if (!select || !window.AphelionParsec) return;
    select.value = window.AphelionParsec.getReducedMotionOverride() || '';
    select.addEventListener('change', () => {
      window.AphelionParsec.setReducedMotionOverride(select.value || null);
    });
  }

  function initPreviewButtons() {
    document.querySelector('#parsec-preview-idle')?.addEventListener('click', () => {
      getPetInstance()?.setState('idle');
    });
    document.querySelector('#parsec-preview-working')?.addEventListener('click', () => {
      getPetInstance()?.setState('working');
    });
    document.querySelector('#parsec-preview-happy')?.addEventListener('click', () => {
      getPetInstance()?.react('happy');
    });
    document.querySelector('#parsec-preview-success')?.addEventListener('click', () => {
      window.AphelionParsec?.announce('Preview: everything worked!', {kind: 'success', tool: 'parsec'});
    });
    document.querySelector('#parsec-preview-error')?.addEventListener('click', () => {
      window.AphelionParsec?.announce('Preview: something went wrong.', {kind: 'error', tool: 'parsec'});
    });
  }

  function renderAnnouncementLog() {
    const container = document.querySelector('#parsec-announcement-log');
    if (!container || !window.AphelionParsec) return;
    const entries = window.AphelionParsec.getRecentAnnouncements();
    if (!entries.length) {
      container.innerHTML = '<p class="metadata">Nothing announced yet this session.</p>';
      return;
    }
    container.replaceChildren();
    for (const entry of entries) {
      const row = document.createElement('div');
      row.className = 'changed-file';
      const when = new Date(entry.at * 1000).toLocaleTimeString();
      const tool = entry.tool ? ' · ' + entry.tool : '';
      row.textContent = '[' + entry.kind + ' · ' + when + tool + '] ' + entry.message;
      container.append(row);
    }
  }

  let logTimer = null;

  function ensureLogPolling() {
    if (logTimer !== null) return;
    renderAnnouncementLog();
    logTimer = window.setInterval(renderAnnouncementLog, LOG_REFRESH_MS);
  }

  function initialize() {
    initMotionControl();
    initPreviewButtons();
    ensureLogPolling();
  }

  if (typeof document !== 'undefined') {
    initialize();
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('aphelion:tool-visibility', (event) => {
      if (event.detail && event.detail.tool === 'parsec' && event.detail.visible) {
        renderAnnouncementLog();
      }
    });
  }
})();
