'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const parsec = require(path.join(__dirname, '..', 'parsec.js'));

test('FRAME_SETS defines idle, working, and happy frame lists, each a distinct sprite-sheet row', () => {
  for (const name of ['idle', 'working', 'happy']) {
    assert.ok(Array.isArray(parsec.FRAME_SETS[name]), name + ' should be an array');
    assert.ok(parsec.FRAME_SETS[name].length > 0, name + ' should have at least one frame');
  }
  const rows = new Set(['idle', 'working', 'happy'].map((name) => parsec.FRAME_SETS[name][0].y));
  assert.equal(rows.size, 3, 'idle/working/happy should each occupy their own sprite-sheet row');
});

test('FRAME_SETS.idle columns are evenly spaced by CELL_WIDTH starting at 0', () => {
  parsec.FRAME_SETS.idle.forEach((frame, index) => {
    assert.equal(frame.x, index * parsec.CELL_WIDTH);
  });
});

test('resolveState passes through known states, including the happy reaction', () => {
  assert.equal(parsec.resolveState('idle'), 'idle');
  assert.equal(parsec.resolveState('working'), 'working');
  assert.equal(parsec.resolveState('happy'), 'happy');
});

test('resolveState falls back to idle for anything unrecognized', () => {
  assert.equal(parsec.resolveState('dancing'), 'idle');
  assert.equal(parsec.resolveState(undefined), 'idle');
  assert.equal(parsec.resolveState(null), 'idle');
});

test('FRAME_SETS.twerking is the hidden easter-egg reaction, on its own sprite-sheet row distinct from idle/working/happy', () => {
  assert.ok(Array.isArray(parsec.FRAME_SETS.twerking) && parsec.FRAME_SETS.twerking.length > 0);
  assert.equal(parsec.resolveState('twerking'), 'twerking');
  const rows = new Set(['idle', 'working', 'happy', 'twerking'].map((name) => parsec.FRAME_SETS[name][0].y));
  assert.equal(rows.size, 4, 'twerking should occupy its own row, not reuse idle/working/happy');
});

test('prefersReducedMotion is false when window/matchMedia is unavailable (Node has no window)', () => {
  assert.equal(parsec.prefersReducedMotion(), false);
});

test('nextFrameIndex cycles through a frame set and wraps back to 0', () => {
  assert.equal(parsec.nextFrameIndex(0, 4), 1);
  assert.equal(parsec.nextFrameIndex(1, 4), 2);
  assert.equal(parsec.nextFrameIndex(3, 4), 0);
});

test('advancePatrol walks right, then reverses direction exactly at the right edge', () => {
  let state = {x: 0, direction: 1, maxX: 10, speed: 4};
  state = {...state, ...parsec.advancePatrol(state)};
  assert.equal(state.x, 4);
  assert.equal(state.direction, 1);

  state = {...state, ...parsec.advancePatrol(state)};
  assert.equal(state.x, 8);
  assert.equal(state.direction, 1);

  // 8 + 4 = 12, past maxX=10 -- clamps to the edge and reverses
  state = {...state, ...parsec.advancePatrol(state)};
  assert.equal(state.x, 10);
  assert.equal(state.direction, -1);
});

test('advancePatrol walks left, then reverses direction exactly at the left edge', () => {
  let state = {x: 10, direction: -1, maxX: 10, speed: 4};
  state = {...state, ...parsec.advancePatrol(state)};
  assert.equal(state.x, 6);
  assert.equal(state.direction, -1);

  state = {...state, ...parsec.advancePatrol(state)};
  assert.equal(state.x, 2);
  assert.equal(state.direction, -1);

  // 2 - 4 = -2, past the left edge -- clamps to 0 and reverses
  state = {...state, ...parsec.advancePatrol(state)};
  assert.equal(state.x, 0);
  assert.equal(state.direction, 1);
});

test('advancePatrol is a no-op (stays at 0) when the box has no room to patrol', () => {
  const result = parsec.advancePatrol({x: 0, direction: 1, maxX: 0, speed: 4});
  assert.equal(result.x, 0);
});

test('with no override saved, Parsec animates by default even when the OS wants reduced motion', () => {
  const store = {};
  global.window = {
    localStorage: {
      getItem: (key) => (key in store ? store[key] : null),
      setItem: (key, value) => { store[key] = value; },
      removeItem: (key) => { delete store[key]; },
    },
    matchMedia: () => ({matches: true}), // OS says "reduce motion" -- should be ignored by default
  };
  try {
    assert.equal(parsec.getReducedMotionOverride(), null);
    assert.equal(parsec.prefersReducedMotion(), false, 'small confined sprite should animate by default regardless of the OS setting');
  } finally {
    delete global.window;
  }
});

test('reduced-motion override round-trips through a mocked localStorage: reduce, follow-system, and clearing back to the default', () => {
  const store = {};
  global.window = {
    localStorage: {
      getItem: (key) => (key in store ? store[key] : null),
      setItem: (key, value) => { store[key] = value; },
      removeItem: (key) => { delete store[key]; },
    },
    matchMedia: () => ({matches: true}), // OS says "reduce motion"
  };
  try {
    parsec.setReducedMotionOverride('reduce');
    assert.equal(parsec.getReducedMotionOverride(), 'reduce');
    assert.equal(parsec.prefersReducedMotion(), true);

    parsec.setReducedMotionOverride('follow-system');
    assert.equal(parsec.prefersReducedMotion(), true, '"follow system" should defer to matchMedia, which says reduce here');

    parsec.setReducedMotionOverride(null);
    assert.equal(parsec.getReducedMotionOverride(), null);
    assert.equal(parsec.prefersReducedMotion(), false, 'clearing the override goes back to the animate-by-default behavior, not matchMedia');
  } finally {
    delete global.window;
  }
});

test('getRecentAnnouncements stays capped and returns most-recent-first', () => {
  const total = parsec.ANNOUNCEMENT_LOG_LIMIT + 5;
  for (let i = 0; i < total; i += 1) {
    parsec.recordAnnouncement('message ' + i, 'info', 'test');
  }
  const recent = parsec.getRecentAnnouncements();
  assert.equal(recent.length, parsec.ANNOUNCEMENT_LOG_LIMIT);
  assert.equal(recent[0].message, 'message ' + (total - 1), 'most recent entry should come first');
  assert.equal(recent[recent.length - 1].message, 'message ' + (total - parsec.ANNOUNCEMENT_LOG_LIMIT));
});
