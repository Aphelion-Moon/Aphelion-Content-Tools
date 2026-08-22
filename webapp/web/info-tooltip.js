(() => {
  'use strict';

  // Shared, general-purpose hover tooltip -- reveals "advanced" detail for a compact piece of UI without
  // it having to be shown all the time. First consumer: the sidebar's store-status-widget.js.
  //
  // Positioned with the same vendored Floating UI used by open-in-menu.js (this project's only other
  // floating/portaled element), since the plain @floating-ui/dom core it vendors is positioning math
  // only -- there's no @floating-ui/react-style useHover/useFocus/useDismiss here, so the show/hide
  // interaction logic below is hand-rolled the same way open-in-menu.js hand-rolls its own.
  //
  // Follows the WAI-ARIA tooltip pattern: opens on hover *and* keyboard focus (not hover-only, so it
  // works for keyboard/screen-reader users), closes on mouse-out, blur, or Escape -- never on a timer --
  // and per WCAG 1.4.13 ("hoverable"), the pointer can move from the trigger onto the tooltip's own
  // content without it closing: "still open" means "over the trigger OR over the tooltip", not just the
  // trigger. Tooltip content should stay short and non-interactive (no buttons/links inside it).

  let nextId = 0;
  let openState = null; // {trigger, tooltip, cleanupAutoUpdate} for whichever tooltip is open, or null

  function closeOpen() {
    if (!openState) return;
    openState.cleanupAutoUpdate();
    openState.tooltip.remove();
    openState.trigger.removeAttribute('aria-describedby');
    openState = null;
  }

  function isOpenFor(trigger) {
    return !!openState && openState.trigger === trigger;
  }

  function open(trigger, getContent, placement) {
    if (isOpenFor(trigger)) return;
    closeOpen();

    const tooltip = document.createElement('div');
    tooltip.className = 'info-tooltip';
    tooltip.setAttribute('role', 'tooltip');
    tooltip.id = 'info-tooltip-' + (nextId += 1);
    const content = getContent();
    if (typeof content === 'string') {
      tooltip.textContent = content;
    } else if (content) {
      tooltip.replaceChildren(content);
    }
    document.body.appendChild(tooltip);
    trigger.setAttribute('aria-describedby', tooltip.id);

    const {computePosition, autoUpdate, offset, flip, shift} = window.FloatingUIDOM;
    function updatePosition() {
      computePosition(trigger, tooltip, {
        strategy: 'fixed',
        placement: placement || 'bottom-start',
        middleware: [offset(8), flip(), shift({padding: 8})],
      }).then(({x, y}) => {
        tooltip.style.left = x + 'px';
        tooltip.style.top = y + 'px';
      });
    }
    const cleanupAutoUpdate = autoUpdate(trigger, tooltip, updatePosition);
    openState = {trigger, tooltip, cleanupAutoUpdate};

    // Hoverable per WCAG 1.4.13: entering the tooltip itself must not let a pending close proceed.
    tooltip.addEventListener('mouseenter', () => cancelPendingClose());
    tooltip.addEventListener('mouseleave', () => scheduleCloseUnless(trigger, tooltip));
  }

  // A short grace period (not a display timer -- the tooltip itself never auto-hides while hovered/
  // focused) so moving the pointer from the trigger onto the tooltip's own content doesn't flicker-close
  // it in the gap between the two elements.
  const CLOSE_GRACE_MS = 100;
  let pendingCloseTimer = null;

  function cancelPendingClose() {
    if (pendingCloseTimer !== null) {
      window.clearTimeout(pendingCloseTimer);
      pendingCloseTimer = null;
    }
  }

  function scheduleCloseUnless(trigger, tooltip) {
    cancelPendingClose();
    pendingCloseTimer = window.setTimeout(() => {
      pendingCloseTimer = null;
      if (!trigger.matches(':hover') && !tooltip.matches(':hover') && document.activeElement !== trigger) {
        closeOpen();
      }
    }, CLOSE_GRACE_MS);
  }

  function attach(trigger, {getContent, placement} = {}) {
    if (!trigger || typeof getContent !== 'function') return;
    trigger.addEventListener('mouseenter', () => { cancelPendingClose(); open(trigger, getContent, placement); });
    trigger.addEventListener('mouseleave', () => scheduleCloseUnless(trigger, openState ? openState.tooltip : trigger));
    trigger.addEventListener('focus', () => open(trigger, getContent, placement));
    trigger.addEventListener('blur', () => { if (isOpenFor(trigger)) closeOpen(); });
  }

  if (typeof document !== 'undefined') {
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeOpen();
    });
  }

  const api = {attach};
  if (typeof window !== 'undefined') {
    window.AphelionTooltip = api;
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
})();
