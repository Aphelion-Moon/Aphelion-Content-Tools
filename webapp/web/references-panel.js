(() => {
  'use strict';

  // Shared "References" sidebar panel -- shown below the page title on every tool page (see the
  // `<div id="reference-panel">` inserted right after `<header class="hero">` in each page's HTML).
  // A writer can pin a catalog entry, a content-graph node, or a changed file from wherever that item is
  // already selectable, and it shows up here on every page since the backing store
  // (`webapp/references.py`, `/api/references`) is shared, not per-tool.

  const containers = new Set();
  let cachedReferences = null;
  let loadPromise = null;

  async function requestJson(path, options = {}) {
    const response = await fetch(path, options);
    const contentType = response.headers.get('content-type') || '';
    const payload = contentType.includes('application/json') ? await response.json() : {};
    if (!response.ok) throw new Error(payload.error || ('Request failed (' + response.status + ')'));
    return payload;
  }

  function renderInto(container, references) {
    container.replaceChildren();
    if (!references.length) {
      const empty = document.createElement('p');
      empty.className = 'metadata reference-panel-empty';
      empty.textContent = 'No pinned references yet.';
      container.append(empty);
      return;
    }
    const list = document.createElement('ul');
    list.className = 'reference-panel-list';
    for (const reference of references) {
      const item = document.createElement('li');
      item.className = 'reference-panel-item';
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'reference-panel-select';
      button.textContent = reference.label;
      button.title = reference.key;
      button.addEventListener('click', () => {
        window.dispatchEvent(new CustomEvent('aphelion:reference-select', {
          detail: {tool: reference.tool, kind: reference.kind, key: reference.key},
        }));
      });
      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'reference-panel-remove';
      remove.setAttribute('aria-label', 'Remove reference');
      remove.textContent = '×';
      remove.addEventListener('click', (event) => {
        event.stopPropagation();
        requestJson('/api/references/' + encodeURIComponent(reference.id), {method: 'DELETE'})
          .then(() => refresh())
          .catch((error) => console.error(error));
      });
      item.append(button, remove);
      list.append(item);
    }
    container.append(list);
  }

  function renderAll() {
    for (const container of containers) {
      if (container.isConnected) renderInto(container, cachedReferences || []);
    }
  }

  async function refresh() {
    if (!loadPromise) {
      loadPromise = requestJson('/api/references')
        .then((payload) => {
          cachedReferences = payload.references || [];
          renderAll();
        })
        .catch((error) => console.error(error))
        .finally(() => {
          loadPromise = null;
        });
    }
    return loadPromise;
  }

  function mount(container) {
    if (!container || containers.has(container)) return;
    containers.add(container);
    if (cachedReferences) {
      renderInto(container, cachedReferences);
    } else {
      refresh();
    }
  }

  async function add({tool, kind, key, label, path, note}) {
    await requestJson('/api/references', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({tool, kind, key, label, path, note}),
    });
    cachedReferences = null;
    await refresh();
  }

  window.AphelionReferences = {mount, add, refresh};

  // On a hard page load, shell.js's own init() runs (and calls mountReferencePanel) before this script's
  // tag executes -- since it always loads after shell.js -- so `window.AphelionReferences` doesn't exist
  // yet at that point and shell.js's call is a no-op. Pick up any `#reference-panel` already in the DOM
  // here instead; the SPA nav-click path (shell.js's loadView/registerView) still mounts new views
  // directly since this script is already loaded by the time later tools activate.
  if (typeof document !== 'undefined') {
    document.querySelectorAll('#reference-panel').forEach(mount);
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {renderInto};
  }
})();
