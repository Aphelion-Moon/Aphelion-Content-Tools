(() => {
  'use strict';

  // Parsec -- the app's mascot/pixel-pet engine, and its standard feedback-reporting surface. Any script
  // can call `window.AphelionParsec.announce(message, {kind, tool})` to have her deliver a speech-bubble
  // toast alongside her current animation, in addition to whatever inline status text a page already
  // shows (see references/maintainer-guide.md for the standing convention this establishes).
  //
  // Structurally inspired by oneko.js (github.com/adryd325/oneko.js, MIT) -- a requestAnimationFrame loop
  // throttled to a low, economical frame rate, stepping through a named state's list of sprite-sheet
  // frame coordinates -- but rewritten for this use case: she is confined to a small container (not
  // position:fixed chasing the cursor across the whole page), and her state is driven by job status and
  // app events, not cursor proximity. oneko's 8-directional movement and wall-scratching don't apply here
  // and aren't reproduced.
  //
  // Artwork: cropped and repacked from "Husky Sprites" (opengameart.org/content/husky-sprites),
  // CC0 / public domain -- no attribution required, kept here only as a provenance note.

  const SPRITE_URL = '/parsec.png';
  const CELL_WIDTH = 72;
  const CELL_HEIGHT = 51;
  const FRAME_INTERVAL_MS = 150; // ~6-7fps -- plenty for blocky pixel art, matches oneko's own economical throttling
  const PATROL_SPEED_PX_PER_TICK = 2;
  const REACTION_DURATION_MS = 900;
  const TWERK_REACTION_DURATION_MS = 1800; // longer than a normal reaction -- let the joke land
  const TWERK_CLICK_THRESHOLD = 6; // rapid pats within the window below trigger the easter egg
  const TWERK_WINDOW_MS = 3000;
  const BUBBLE_DURATION_MS = 5000;
  const ANNOUNCEMENT_LOG_LIMIT = 20;
  const REDUCED_MOTION_OVERRIDE_KEY = 'aphelion-parsec-reduced-motion-override';

  // Column/row offsets into parsec.png. Row 0: a sitting-idle loop -- a consistent seated posture where
  // only the tail moves, a genuinely loopable idle (an earlier standing+tail-curl row looked like a
  // sit-down/stand-up transition when cycled, not a loop, hence the switch). Row 1: a running/trotting
  // cycle for the "working" state. Row 2: a two-frame hop used for the "happy" one-shot reaction. Row 3:
  // that original mis-picked idle row (standing, tail curling up dramatically) -- kept on purpose as a
  // hidden "twerking" easter-egg reaction rather than discarded, since cycled on repeat it reads as exactly
  // the joke its name suggests. More states can be added here later without changing the engine below.
  const FRAME_SETS = {
    idle: [0, 1, 2, 3].map((col) => ({x: col * CELL_WIDTH, y: 0})),
    working: [0, 1, 2, 3, 4, 5].map((col) => ({x: col * CELL_WIDTH, y: CELL_HEIGHT})),
    happy: [0, 1].map((col) => ({x: col * CELL_WIDTH, y: CELL_HEIGHT * 2})),
    twerking: [0, 1, 2].map((col) => ({x: col * CELL_WIDTH, y: CELL_HEIGHT * 3})),
  };

  function resolveState(state) {
    return FRAME_SETS[state] ? state : 'idle';
  }

  // Pure helpers factored out of the tick loop so they're testable without a real requestAnimationFrame
  // driving them (a sandboxed/headless browser pane may never actually fire rAF at all if it isn't being
  // composited/displayed -- confirmed directly against this project's own automated browser tooling --
  // so the frame-stepping and patrol-bounds math needs to be verifiable independent of that).
  function nextFrameIndex(frameIndex, frameCount) {
    return (frameIndex + 1) % frameCount;
  }

  function advancePatrol({x, direction, maxX, speed}) {
    if (maxX <= 0) return {x: 0, direction};
    let nextX = x + direction * speed;
    let nextDirection = direction;
    if (nextX >= maxX) {
      nextX = maxX;
      nextDirection = -1;
    } else if (nextX <= 0) {
      nextX = 0;
      nextDirection = 1;
    }
    return {x: nextX, direction: nextDirection};
  }

  function readReducedMotionOverride() {
    try {
      return window.localStorage.getItem(REDUCED_MOTION_OVERRIDE_KEY);
    } catch (error) {
      return null; // storage disabled/unavailable -- fall through to the OS setting
    }
  }

  function setReducedMotionOverride(value) {
    try {
      if (value === null) {
        window.localStorage.removeItem(REDUCED_MOTION_OVERRIDE_KEY);
      } else {
        window.localStorage.setItem(REDUCED_MOTION_OVERRIDE_KEY, value);
      }
    } catch (error) {
      // Storage disabled/unavailable -- the override just won't persist, not worth surfacing an error for.
    }
  }

  function prefersReducedMotion() {
    const override = readReducedMotionOverride();
    if (override === 'reduce') return true;
    if (override === 'follow-system') {
      return typeof window !== 'undefined'
        && typeof window.matchMedia === 'function'
        && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }
    // Default (no override saved, or the older 'no-preference' value from before "follow system" was a
    // distinct choice): animate regardless of the OS-wide setting. This sprite is small and fully
    // confined to its own box -- not the large-scale/parallax motion prefers-reduced-motion exists to
    // guard against -- and that OS setting is commonly on for reasons unrelated to a deliberate
    // vestibular accommodation (a Windows power-saving profile, for instance), which was leaving her
    // looking frozen/inert for most people by default. Anyone who does want her to actually stop can
    // still choose "Always reduce motion" explicitly on her settings page.
    return false;
  }

  class ParsecInstance {
    constructor(container) {
      this.container = container;
      this.state = 'idle';
      this.reactionState = null;
      this.reactionEndsAt = 0;
      this.frameIndex = 0;
      this.lastFrameTime = 0;
      this.x = 0;
      this.direction = 1; // 1 = moving/facing right, -1 = moving/facing left
      this.rafId = null;
      this.patTimestamps = [];

      this.el = document.createElement('div');
      this.el.className = 'parsec-sprite';
      this.el.style.backgroundImage = `url(${SPRITE_URL})`;
      container.appendChild(this.el);

      this._tick = this._tick.bind(this);
      this.rafId = window.requestAnimationFrame(this._tick);
    }

    setState(nextState) {
      const resolved = resolveState(nextState);
      if (resolved === this.state) return;
      this.state = resolved;
      if (!this.reactionState) this.frameIndex = 0;
    }

    react(name) {
      if (!FRAME_SETS[name]) return;
      this.reactionState = name;
      const duration = name === 'twerking' ? TWERK_REACTION_DURATION_MS : REACTION_DURATION_MS;
      this.reactionEndsAt = performance.now() + duration;
      this.frameIndex = 0;
    }

    // Called on every pat click. Normally just plays the happy reaction, but enough rapid pats in a row
    // (see TWERK_CLICK_THRESHOLD/TWERK_WINDOW_MS) trigger the hidden "twerking" reaction instead. Returns
    // which reaction actually played, so the caller can pick a matching announcement line.
    registerPat() {
      const now = performance.now();
      this.patTimestamps = this.patTimestamps.filter((t) => now - t < TWERK_WINDOW_MS);
      this.patTimestamps.push(now);
      if (this.patTimestamps.length >= TWERK_CLICK_THRESHOLD) {
        this.patTimestamps = [];
        this.react('twerking');
        return 'twerking';
      }
      this.react('happy');
      return 'happy';
    }

    _maxX() {
      return Math.max(0, this.container.clientWidth - CELL_WIDTH);
    }

    // Moves her existing sprite element into a different box, keeping every bit of state (position,
    // facing, current frame, animation state) intact -- used when the visible page changes, so she reads
    // as one continuous character following you around rather than a fresh copy resetting to x=0 in each
    // page's own box.
    reparent(newContainer) {
      if (!newContainer || this.container === newContainer) return;
      this.container = newContainer;
      newContainer.appendChild(this.el);
    }

    _tick(timestamp) {
      this.rafId = window.requestAnimationFrame(this._tick);
      if (timestamp - this.lastFrameTime < FRAME_INTERVAL_MS) return;
      this.lastFrameTime = timestamp;

      if (this.reactionState && timestamp >= this.reactionEndsAt) {
        this.reactionState = null;
        this.frameIndex = 0;
      }

      const reduced = prefersReducedMotion();
      const activeState = this.reactionState || this.state;
      const frames = FRAME_SETS[activeState];

      if (!reduced) {
        this.frameIndex = nextFrameIndex(this.frameIndex, frames.length);
        if (activeState === 'working') {
          const next = advancePatrol({x: this.x, direction: this.direction, maxX: this._maxX(), speed: PATROL_SPEED_PX_PER_TICK});
          this.x = next.x;
          this.direction = next.direction;
        }
      }

      const frame = frames[reduced ? 0 : this.frameIndex];
      this.el.style.backgroundPosition = `-${frame.x}px -${frame.y}px`;
      // The sprite art faces left natively; flip it to face the direction it's actually walking.
      const facingScale = this.direction === 1 ? -1 : 1;
      this.el.style.transform = `translateX(${this.x}px) scaleX(${facingScale})`;
    }

    destroy() {
      if (this.rafId !== null) window.cancelAnimationFrame(this.rafId);
      this.el.remove();
    }
  }

  // ---- App-wide singleton bookkeeping: there is exactly one Parsec, reparented as you navigate ----

  // parsec.js is loaded fresh on every SPA navigation to a not-yet-visited tool (it's in every tool's
  // script list, the same way info-tooltip.js/store-status-widget.js are -- see shell.js's
  // STATUS_WIDGET_SCRIPTS) -- each `<script>` load re-runs this whole IIFE in a brand-new closure. Every
  // page also builds its own `.store-status-pet-box` the first time it's visited. Naively calling `mount`
  // per box would create a separate ParsecInstance (and rAF loop) per page, each with its own position --
  // she'd visibly reset to x=0 every time you switched pages, since you'd really be looking at a
  // different copy each time. Instead, exactly one ParsecInstance ever exists for the whole app session;
  // navigating between pages moves her existing element into whichever page's box just became visible
  // (see reparent() above) rather than creating a new one. This bookkeeping (the one instance, and which
  // container belongs to which tool) is kept on a persistent object hung off the global scope rather than
  // as closure-local variables, since a fresh closure from a script reload would otherwise lose track of
  // an instance that's very much still alive and animating.
  const globalScope = typeof window !== 'undefined' ? window : globalThis;
  const shared = globalScope.__aphelionParsecShared || (globalScope.__aphelionParsecShared = {
    instance: null, // the one and only ParsecInstance
    containersByTool: new Map(), // tool name -> that tool's own .store-status-pet-box element
    announcementLog: [],
    bubbleActive: false,
    bubbleQueue: [],
  });

  function mount(container) {
    if (!container) return null;
    const tool = container.closest('[data-tool]')?.dataset.tool;
    if (tool) shared.containersByTool.set(tool, container);

    if (!shared.instance) {
      // First mount for the whole app session -- create the one true instance here. On a hard page load
      // this is also the only container that exists yet, so it's already the right one; no reparent needed.
      shared.instance = new ParsecInstance(container);
    }
    // If `container` belongs to a tool that isn't the one currently on screen, deliberately leave her
    // where she is rather than reparenting immediately -- that happens below, exactly when this tool's
    // view actually becomes visible, not merely when its (still-hidden) box is first built.
    return shared.instance;
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('aphelion:tool-visibility', (event) => {
      const detail = event.detail || {};
      if (!detail.visible) return;
      const container = shared.containersByTool.get(detail.tool);
      if (container) shared.instance?.reparent(container);
    });
  }

  // ---- Announcements: a speech-bubble toast + an in-memory log, the reporting API other scripts use ----

  function recordAnnouncement(message, kind, tool) {
    shared.announcementLog.push({message, kind, tool: tool || null, at: Date.now() / 1000});
    if (shared.announcementLog.length > ANNOUNCEMENT_LOG_LIMIT) shared.announcementLog.shift();
  }

  function getRecentAnnouncements() {
    return shared.announcementLog.slice().reverse();
  }

  function processBubbleQueue() {
    if (shared.bubbleActive || shared.bubbleQueue.length === 0) return;
    const {message, kind} = shared.bubbleQueue.shift();
    const instance = shared.instance;
    if (!instance || typeof window.FloatingUIDOM === 'undefined') return processBubbleQueue();
    shared.bubbleActive = true;

    const bubble = document.createElement('div');
    bubble.className = 'parsec-bubble parsec-bubble-' + kind;
    bubble.textContent = message;
    document.body.appendChild(bubble);

    const {computePosition, autoUpdate, offset, flip, shift} = window.FloatingUIDOM;
    function updatePosition() {
      computePosition(instance.el, bubble, {
        strategy: 'fixed',
        placement: 'top',
        middleware: [offset(8), flip(), shift({padding: 8})],
      }).then(({x, y}) => {
        bubble.style.left = x + 'px';
        bubble.style.top = y + 'px';
      });
    }
    const cleanupAutoUpdate = autoUpdate(instance.el, bubble, updatePosition);
    window.setTimeout(() => {
      cleanupAutoUpdate();
      bubble.remove();
      shared.bubbleActive = false;
      processBubbleQueue();
    }, BUBBLE_DURATION_MS);
  }

  function announce(message, {kind = 'info', tool} = {}) {
    if (!message) return;
    recordAnnouncement(message, kind, tool);
    if (kind === 'success' && shared.instance) shared.instance.react('happy');
    // At most one bubble ever waits behind the one currently showing -- a burst of rapid calls (repeated
    // pats, in particular) replaces whatever was pending instead of appending to it, so the queue can't
    // back up into a long run of stale toasts that keeps talking well after the clicking stopped.
    shared.bubbleQueue = [{message, kind}];
    processBubbleQueue();
  }

  const api = {
    mount,
    announce,
    getRecentAnnouncements,
    setReducedMotionOverride,
    getReducedMotionOverride: readReducedMotionOverride,
  };
  if (typeof window !== 'undefined') {
    window.AphelionParsec = api;
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
      FRAME_SETS, CELL_WIDTH, CELL_HEIGHT, resolveState, prefersReducedMotion,
      nextFrameIndex, advancePatrol, setReducedMotionOverride, getReducedMotionOverride: readReducedMotionOverride,
      recordAnnouncement, getRecentAnnouncements, ANNOUNCEMENT_LOG_LIMIT,
    };
  }
})();
