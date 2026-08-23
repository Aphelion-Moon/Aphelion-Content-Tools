(() => {
  'use strict';

const state = {
  repositories: {tool: null, game: null},
  selectedPaths: {tool: new Set(), game: new Set()},
  exportStages: [],
};

async function requestJson(path, options = {}) {
  const response = await fetch(path, options);
  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json') ? await response.json() : {};
  if (!response.ok) throw new Error(payload.error || ('Request failed (' + response.status + ')'));
  return payload;
}

function setText(selector, value) {
  document.querySelector(selector).textContent = value;
}

// Parsec (webapp/web/parsec.js) is this app's standard feedback-reporting surface -- every meaningful
// success/error here also announces through her, additively alongside the inline status text above,
// which stays exactly as it was (see references/maintainer-guide.md for the standing convention).
function announceError(message) {
  window.AphelionParsec?.announce(message, {kind: 'error', tool: 'file-management'});
}

function announceSuccess(message) {
  window.AphelionParsec?.announce(message, {kind: 'success', tool: 'file-management'});
}

function repositoryLabel(repository) {
  return repository === 'game' ? 'Meridian-Rift' : 'Aphelion Content Tools';
}

function renderChangedFileRow(repository, filePath) {
  const row = document.createElement('details');
  row.className = 'changed-file';
  const summary = document.createElement('summary');
  const label = document.createElement('span');
  label.textContent = filePath;
  const pinButton = document.createElement('button');
  pinButton.type = 'button';
  pinButton.className = 'text-button changed-file-pin';
  pinButton.textContent = 'Add to references';
  pinButton.addEventListener('click', (event) => {
    event.preventDefault();
    event.stopPropagation();
    window.AphelionReferences.add({
      tool: 'file-management',
      kind: 'file',
      key: filePath,
      label: filePath,
      path: filePath,
      note: repository,
    }).catch((error) => console.error(error));
  });
  summary.append(label, pinButton);
  row.append(summary);
  const diffOutput = document.createElement('pre');
  diffOutput.className = 'tool-output diff-output';
  diffOutput.textContent = 'Loading diff…';
  row.append(diffOutput);
  let loaded = false;
  row.addEventListener('toggle', () => {
    if (!row.open || loaded) return;
    loaded = true;
    requestJson('/api/git/diff?repository=' + encodeURIComponent(repository) + '&path=' + encodeURIComponent(filePath))
      .then((payload) => { diffOutput.textContent = payload.diff || '(no textual diff for this change)'; })
      .catch((error) => { diffOutput.textContent = error.message; loaded = false; announceError(error.message); });
  });
  return row;
}

function renderRepositoryStatus(repository) {
  const status = state.repositories[repository];
  const container = document.querySelector('#' + repository + '-status');
  container.replaceChildren();

  const summary = document.createElement('p');
  summary.className = status?.dirty ? 'repository-dirty' : 'repository-clean';
  summary.textContent = status
    ? (status.dirty ? 'Changes pending' : 'Clean') + ' · ' + status.branch
    : 'Status unavailable';
  container.append(summary);

  const metaLine = document.createElement('p');
  metaLine.className = 'metadata';
  if (status) {
    const aheadBehind = (status.ahead ? ' · ahead ' + status.ahead : '') + (status.behind ? ' · behind ' + status.behind : '');
    metaLine.textContent = (status.changed_files?.length ? status.changed_files.length + ' changed file(s)' : 'No changed files') + aheadBehind;
    if (status.conflicted) metaLine.textContent += ' · conflicts need attention';
    container.append(metaLine);
  }

  if (status?.owned_changes?.length) {
    const fileList = document.createElement('div');
    fileList.className = 'changed-file-list';
    for (const change of status.owned_changes) {
      const wrapper = document.createElement('div');
      const selectLabel = document.createElement('label');
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = state.selectedPaths[repository].has(change.path);
      checkbox.addEventListener('change', () => {
        if (checkbox.checked) state.selectedPaths[repository].add(change.path);
        else state.selectedPaths[repository].delete(change.path);
      });
      selectLabel.append(checkbox, ' Select ' + change.kind.replaceAll('_', ' ') + ': ' + change.summary);
      wrapper.append(selectLabel, renderChangedFileRow(repository, change.path));
      fileList.append(wrapper);
    }
    container.append(fileList);
  }
  if (status?.unowned_changes?.length) {
    const note = document.createElement('p');
    note.className = 'metadata';
    note.textContent = 'Unrelated changes are shown for awareness and cannot be committed by the app.';
    container.append(note);
    const fileList = document.createElement('div');
    fileList.className = 'changed-file-list';
    for (const filePath of status.unowned_changes) fileList.append(renderChangedFileRow(repository, filePath));
    container.append(fileList);
  }
}

async function loadRepositoryStatus() {
  const statuses = await Promise.all(['tool', 'game'].map(async (repository) => [
    repository,
    await requestJson('/api/git/status?repository=' + repository),
  ]));
  for (const [repository, status] of statuses) {
    state.repositories[repository] = status;
    const ownedPaths = new Set((status.owned_changes || []).map((change) => change.path));
    state.selectedPaths[repository] = new Set(
      Array.from(state.selectedPaths[repository]).filter((path) => ownedPaths.has(path))
    );
  }
  renderRepositoryStatus('tool');
  renderRepositoryStatus('game');
}

async function loadBranches(repository) {
  const payload = await requestJson('/api/git/branches?repository=' + repository);
  const branches = payload.branches || [];
  const select = document.querySelector('#' + repository + '-branch-select');
  select.replaceChildren();
  for (const branch of branches) {
    const option = document.createElement('option');
    option.value = branch;
    option.textContent = branch;
    select.append(option);
  }
  const current = state.repositories[repository]?.branch;
  if (current && branches.includes(current)) select.value = current;
}

async function createRepositoryBranch(repository) {
  const name = document.querySelector('#' + repository + '-branch-name').value.trim();
  if (!name) throw new Error('Enter a branch name first.');
  await requestJson('/api/git/branch', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({repository, name}),
  });
  setText('#' + repository + '-message', 'Created and switched to ' + name + '.');
  announceSuccess('Created and switched to ' + name + '.');
  document.querySelector('#' + repository + '-branch-name').value = '';
  await Promise.all([loadRepositoryStatus(), loadBranches(repository)]);
}

async function switchRepositoryBranch(repository) {
  const branch = document.querySelector('#' + repository + '-branch-select').value;
  if (!branch) throw new Error('Choose a branch to switch to first.');
  await requestJson('/api/git/switch-branch', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({repository, name: branch}),
  });
  setText('#' + repository + '-message', 'Switched to ' + branch + '.');
  announceSuccess('Switched to ' + branch + '.');
  await Promise.all([loadRepositoryStatus(), loadBranches(repository)]);
}

async function commitRepositoryChanges(repository) {
  const status = state.repositories[repository];
  const message = document.querySelector('#' + repository + '-commit-message').value.trim();
  const selectedPaths = Array.from(state.selectedPaths[repository]);
  if (!status?.owned_changes?.length || !selectedPaths.length) throw new Error('Select at least one owned change to commit.');
  if (!message) throw new Error('Enter a commit message first.');
  await requestJson('/api/git/commit', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({repository, paths: selectedPaths, message}),
  });
  setText('#' + repository + '-message', 'Committed ' + selectedPaths.length + ' file(s).');
  announceSuccess('Committed ' + selectedPaths.length + ' file(s).');
  state.selectedPaths[repository].clear();
  document.querySelector('#' + repository + '-commit-message').value = '';
  await loadRepositoryStatus();
}

async function openRepositoryInDesktop(repository) {
  await requestJson('/api/git/open', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({repository}),
  });
  setText('#' + repository + '-message', 'Opened in GitHub Desktop.');
  announceSuccess('Opened in GitHub Desktop.');
}

function attachRepositoryControls(repository) {
  document.querySelector('#' + repository + '-refresh-button').addEventListener('click', () =>
    Promise.all([loadRepositoryStatus(), loadBranches(repository)]).catch((error) => { setText('#' + repository + '-message', error.message); announceError(error.message); }));
  document.querySelector('#' + repository + '-switch-branch-button').addEventListener('click', () =>
    switchRepositoryBranch(repository).catch((error) => { setText('#' + repository + '-message', error.message); announceError(error.message); }));
  document.querySelector('#' + repository + '-create-branch-button').addEventListener('click', () =>
    createRepositoryBranch(repository).catch((error) => { setText('#' + repository + '-message', error.message); announceError(error.message); }));
  document.querySelector('#' + repository + '-commit-button').addEventListener('click', () =>
    commitRepositoryChanges(repository).catch((error) => { setText('#' + repository + '-message', error.message); announceError(error.message); }));
  document.querySelector('#' + repository + '-open-desktop-button').addEventListener('click', () =>
    openRepositoryInDesktop(repository).catch((error) => { setText('#' + repository + '-message', error.message); announceError(error.message); }));
}

function renderExportStages() {
  // Stage names are UTC timestamps ("YYYYMMDDThhmmssZ-<hash>"), and /api/export/stages returns them
  // sorted ascending by name, so the last entry is always the most recently prepared stage — the
  // picker defaults to it every time the list is (re)rendered, never to whatever was selected before.
  const select = document.querySelector('#export-stage-select');
  select.replaceChildren();
  if (!state.exportStages.length) {
    const empty = document.createElement('option');
    empty.value = '';
    empty.textContent = 'No prepared stages — prepare one first';
    select.append(empty);
    return;
  }
  for (const stage of state.exportStages) {
    const option = document.createElement('option');
    option.value = stage.stage;
    const manifest = stage.manifest || {};
    option.textContent = stage.stage + ' · ' + (manifest.entry_ids?.length || 0) + ' override(s)';
    select.append(option);
  }
  select.value = state.exportStages[state.exportStages.length - 1].stage;
}

async function loadExportStages() {
  const payload = await requestJson('/api/export/stages');
  state.exportStages = payload.stages || [];
  renderExportStages();
}

async function prepareExport() {
  const payload = await requestJson('/api/export/prepare', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: '{}',
  });
  document.querySelector('#export-output').textContent =
    'Prepared stage ' + payload.stage + '. Review the manifest below, then click Apply to write it into Meridian-Rift.\n\n' +
    JSON.stringify(payload.manifest || payload, null, 2);
  announceSuccess('Prepared export stage ' + payload.stage + '.');
  await Promise.all([loadExportStages(), loadRepositoryStatus()]);
}

async function applySelectedExport() {
  const stage = document.querySelector('#export-stage-select').value;
  if (!stage) throw new Error('Prepare an export before applying one.');
  const payload = await requestJson('/api/export/apply', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({stage}),
  });
  const desktopNote = payload.opened_in_github_desktop
    ? 'GitHub Desktop opened automatically for the game checkout.'
    : 'Could not open GitHub Desktop automatically' + (payload.github_desktop_error ? (': ' + payload.github_desktop_error) : '.') + ' Open it manually to review, commit, and open a pull request.';
  document.querySelector('#export-output').textContent =
    'Applied ' + payload.artifact + '.\n' +
    'Review the game diff above under Meridian-Rift, then commit it locally.\n' + desktopNote;
  announceSuccess('Applied ' + payload.artifact + '.');
  await loadRepositoryStatus();
}

// Which panel group each tool's button renders into. "refresh-validate" is the one pipeline step most
// users want; its individual halves (catalog-refresh/validate/generate) move into the "advanced"
// disclosure instead of sitting at the same top-level priority as a visibly duplicate action.
const TOOL_GROUPS = {
  'refresh-validate': 'tool-list-catalog',
  'catalog-refresh': 'tool-list-catalog-advanced',
  'validate': 'tool-list-catalog-advanced',
  'generate': 'tool-list-catalog-advanced',
  'scan-content': 'tool-list-graph',
  'rebuild-search-embeddings': 'tool-list-maintenance',
  'optimize-store': 'tool-list-maintenance',
};

function renderTools(tools) {
  const lists = new Map();
  for (const containerId of new Set(Object.values(TOOL_GROUPS))) {
    const container = document.querySelector('#' + containerId);
    if (container) {
      container.replaceChildren();
      lists.set(containerId, container);
    }
  }
  for (const tool of tools) {
    const containerId = TOOL_GROUPS[tool.id] || 'tool-list-catalog';
    const list = lists.get(containerId) || document.querySelector('#tool-list-catalog');
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.toolId = tool.id;
    button.textContent = tool.label;
    button.title = tool.description || '';
    button.addEventListener('click', () => runTool(tool.id));
    list.append(button);
  }
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

async function loadStoreHealth() {
  const container = document.querySelector('#store-health');
  if (!container) return;
  try {
    const health = await requestJson('/api/store/health');
    const lastWrite = health.last_write_time
      ? new Date(health.last_write_time * 1000).toLocaleString()
      : 'never (this session)';
    const tableRows = Object.entries(health.tables || {})
      .map(([name, count]) => `<span>${name}: ${count.toLocaleString()}</span>`)
      .join('');
    container.innerHTML =
      `<strong>${health.total_rows.toLocaleString()}</strong> total rows across ${Object.keys(health.tables || {}).length} tables · ` +
      `${formatBytes(health.disk_bytes)} on disk · last write ${lastWrite}` +
      `<div class="store-health-tables">${tableRows}</div>`;
  } catch (error) {
    container.textContent = 'Database health unavailable: ' + error.message;
  }
}

async function pollTool(runId) {
  const payload = await requestJson('/api/tools/runs/' + encodeURIComponent(runId));
  document.querySelector('#tool-output').textContent = payload.output || '';
  setText('#tool-log-path', payload.log_path ? 'Log file: ' + payload.log_path : '');
  if (payload.status === 'queued' || payload.status === 'running') {
    window.setTimeout(() => pollTool(runId).catch((error) => {
      document.querySelector('#tool-output').textContent = error.message;
    }), 750);
    return;
  }
  document.querySelectorAll('[data-tool-id]').forEach((button) => { button.disabled = false; });
  const stopButton = document.querySelector('#stop-tool-button');
  stopButton.hidden = true;
  stopButton.onclick = null;
  if (payload.status === 'succeeded') {
    announceSuccess(payload.tool_id + ' completed successfully.');
    await loadRepositoryStatus();
    if (payload.tool_id === 'catalog-refresh') await loadExportStages();
    await loadStoreHealth();
  } else if (payload.status === 'failed') {
    announceError(payload.tool_id + ' failed.');
  }
}

async function runTool(toolId) {
  document.querySelectorAll('[data-tool-id]').forEach((button) => { button.disabled = true; });
  document.querySelector('#tool-output').textContent = 'Starting ' + toolId + '…';
  try {
    const payload = await requestJson('/api/tools/' + encodeURIComponent(toolId), {method: 'POST'});
    const stopButton = document.querySelector('#stop-tool-button');
    stopButton.hidden = false;
    stopButton.disabled = false;
    stopButton.onclick = () => {
      stopButton.disabled = true;
      requestJson('/api/tools/runs/' + encodeURIComponent(payload.run_id) + '/stop', {method: 'POST'})
        .catch((error) => { document.querySelector('#tool-output').textContent = error.message; announceError(error.message); });
    };
    await pollTool(payload.run_id);
  } catch (error) {
    document.querySelector('#tool-output').textContent = error.message;
    announceError(error.message);
    document.querySelectorAll('[data-tool-id]').forEach((button) => { button.disabled = false; });
  }
}

function attachEvents() {
  attachRepositoryControls('tool');
  attachRepositoryControls('game');
  document.querySelector('#prepare-export-button').addEventListener('click', () => {
    document.querySelector('#export-output').textContent = 'Preparing export…';
    prepareExport().catch((error) => { document.querySelector('#export-output').textContent = error.message; announceError(error.message); });
  });
  document.querySelector('#apply-export-button').addEventListener('click', () => {
    document.querySelector('#export-output').textContent = 'Applying export…';
    applySelectedExport().catch((error) => { document.querySelector('#export-output').textContent = error.message; announceError(error.message); });
  });
}

async function loadPageData() {
  const tools = await requestJson('/api/tools');
  renderTools(tools.tools || []);
  await loadRepositoryStatus();
  await Promise.all([loadExportStages(), loadBranches('tool'), loadBranches('game'), loadStoreHealth()]);
}

function initialize() {
  attachEvents();
  loadPageData().catch((error) => {
    setText('#tool-message', error.message);
    setText('#game-message', error.message);
    announceError(error.message);
  });
}

if (typeof document !== 'undefined') {
  initialize();
}

if (typeof window !== 'undefined') {
  window.addEventListener('aphelion:tool-visibility', (event) => {
    if (!event.detail || event.detail.tool !== 'file-management' || !event.detail.visible) return;
    loadRepositoryStatus().then(() => Promise.all([loadBranches('tool'), loadBranches('game')])).catch(() => {});
  });
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {repositoryLabel, formatBytes};
}

})();
