'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const widget = require(path.join(__dirname, '..', 'store-status-widget.js'));

test('formatBytes renders human-readable sizes at the appropriate unit', () => {
  assert.equal(widget.formatBytes(0), '0 B');
  assert.equal(widget.formatBytes(512), '512 B');
  assert.equal(widget.formatBytes(2048), '2.0 KB');
  assert.equal(widget.formatBytes(5 * 1024 * 1024), '5.0 MB');
});

test('formatElapsed renders seconds for anything under a minute', () => {
  const now = Date.now() / 1000;
  assert.equal(widget.formatElapsed(now - 5), '5s');
  assert.equal(widget.formatElapsed(now), '0s');
});

test('formatElapsed renders minutes and seconds once past a minute', () => {
  const now = Date.now() / 1000;
  assert.equal(widget.formatElapsed(now - 90), '1m 30s');
});

test('formatElapsed renders hours and minutes once past an hour', () => {
  const now = Date.now() / 1000;
  assert.equal(widget.formatElapsed(now - 3700), '1h 1m');
});
