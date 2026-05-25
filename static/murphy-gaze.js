/**
 * murphy-gaze.js v4 — Murphy live gaze tracker + random blinks
 *
 * Tracks cursor (desktop) / touch (mobile). Adds random blinks at natural
 * human cadence (mean ~4.5s between blinks, gaussian-ish jitter). 15% chance
 * of a double-blink. Blink itself is ~150ms close + ~150ms open. Saccades
 * occasionally trigger a blink (humans often blink when their gaze jumps).
 *
 * © Inoni LLC — Murphy brand asset, locked 2026-05-25.
 */
(function () {
  'use strict';

  const SVG_URL              = '/static/logo-live.svg';
  const MAX_IRIS_DX_VBU      = 22;
  const MAX_IRIS_DY_VBU      = 12;
  const PUPIL_MULT           = 1.55;
  const SACCADE_INTERVAL_MS  = 4500;
  const CURSOR_IDLE_MS       = 1800;
  // ── Blink config ────────────────────────────────────────────────────────
  const BLINK_INTERVAL_MEAN_MS = 4500;   // average gap between blinks
  const BLINK_INTERVAL_STD_MS  = 1800;   // std deviation
  const BLINK_INTERVAL_MIN_MS  = 1800;   // never blink faster than this
  const BLINK_CLOSE_MS         = 110;    // time to close
  const BLINK_HOLD_MS          = 40;     // time held closed
  const BLINK_OPEN_MS          = 130;    // time to open
  const DOUBLE_BLINK_PROB      = 0.15;   // 15% chance of double-blink
  const SACCADE_BLINK_PROB     = 0.30;   // 30% of saccades also trigger blink

  let svgTemplate = null;
  let lastInput   = Date.now();
  const eyes      = [];  // each: {wrapper, iris, pupil, lidTop, lidBot}

  async function fetchTemplate() {
    if (svgTemplate) return svgTemplate;
    const r = await fetch(SVG_URL);
    let t = await r.text();
    t = t.replace(/^\s*<\?xml[^?]*\?>\s*/, '');
    svgTemplate = t;
    return t;
  }

  async function registerEye(wrapper) {
    if (wrapper.dataset.mlGazeReady === '1') return;
    wrapper.dataset.mlGazeReady = '1';
    const tpl = await fetchTemplate();
    const uid = 'e' + Math.random().toString(36).slice(2, 8);
    const svgText = tpl
      .replace(/"ml-iris"/g,        `"ml-iris-${uid}"`)
      .replace(/"ml-pupil"/g,       `"ml-pupil-${uid}"`)
      .replace(/"ml-eyelids"/g,     `"ml-eyelids-${uid}"`)
      .replace(/"ml-lid-top"/g,     `"ml-lid-top-${uid}"`)
      .replace(/"ml-lid-bot"/g,     `"ml-lid-bot-${uid}"`)
      .replace(/"ml-eye-clip"/g,    `"ml-eye-clip-${uid}"`)
      .replace(/url\(#ml-eye-clip\)/g, `url(#ml-eye-clip-${uid})`)
      .replace(/"ml-gear-mask"/g,   `"ml-gear-mask-${uid}"`)
      .replace(/url\(#ml-gear-mask\)/g, `url(#ml-gear-mask-${uid})`);
    wrapper.innerHTML = svgText;

    const svg = wrapper.querySelector('svg');
    if (svg) {
      svg.setAttribute('width', '100%');
      svg.setAttribute('height', '100%');
      svg.style.display = 'block';
    }

    const iris   = wrapper.querySelector('#ml-iris-'   + uid);
    const pupil  = wrapper.querySelector('#ml-pupil-'  + uid);
    const lidTop = wrapper.querySelector('#ml-lid-top-' + uid);
    const lidBot = wrapper.querySelector('#ml-lid-bot-' + uid);
    if (!iris || !pupil) return;

    // Eyelids start OPEN (out of the eye area)
    if (lidTop) lidTop.setAttribute('transform', 'translate(0 -60)');  // shifted up out of view
    if (lidBot) lidBot.setAttribute('transform', 'translate(0  60)');  // shifted down out of view

    const cs = getComputedStyle(wrapper);
    if (cs.position === 'static') wrapper.style.position = 'relative';

    const eye = {wrapper, iris, pupil, lidTop, lidBot, isBlinking: false};
    eyes.push(eye);
    // Kick off a personalized blink loop for this eye
    scheduleNextBlink(eye);
  }

  // ── Gaze ────────────────────────────────────────────────────────────────
  function look(clientX, clientY) {
    for (const e of eyes) {
      const r = e.wrapper.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top  + r.height / 2;
      const dx = clientX - cx;
      const dy = clientY - cy;
      const dist = Math.hypot(dx, dy);
      if (dist === 0) {
        e.iris.setAttribute('transform',  'translate(0 0)');
        e.pupil.setAttribute('transform', 'translate(0 0)');
        continue;
      }
      const SAT = 400;
      const norm = Math.tanh(dist / SAT);
      const nx = (dx / dist) * norm;
      const ny = (dy / dist) * norm;
      const irisDx  = nx * MAX_IRIS_DX_VBU;
      const irisDy  = ny * MAX_IRIS_DY_VBU;
      const pupilDx = irisDx * (PUPIL_MULT - 1);
      const pupilDy = irisDy * (PUPIL_MULT - 1);
      e.iris.setAttribute('transform',  `translate(${irisDx.toFixed(2)} ${irisDy.toFixed(2)})`);
      e.pupil.setAttribute('transform', `translate(${pupilDx.toFixed(2)} ${pupilDy.toFixed(2)})`);
    }
  }

  // ── Blinks ──────────────────────────────────────────────────────────────
  function gaussian() {
    // Box-Muller approximation
    let u = 0, v = 0;
    while (u === 0) u = Math.random();
    while (v === 0) v = Math.random();
    return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }

  function nextBlinkDelay() {
    let d = BLINK_INTERVAL_MEAN_MS + gaussian() * BLINK_INTERVAL_STD_MS;
    if (d < BLINK_INTERVAL_MIN_MS) d = BLINK_INTERVAL_MIN_MS;
    if (d > 11000) d = 11000;
    return d;
  }

  function blink(eye, onDone) {
    if (eye.isBlinking) { if (onDone) onDone(); return; }
    if (!eye.lidTop || !eye.lidBot) { if (onDone) onDone(); return; }
    eye.isBlinking = true;

    // Set close transition
    eye.lidTop.style.transition = `transform ${BLINK_CLOSE_MS}ms ease-in`;
    eye.lidBot.style.transition = `transform ${BLINK_CLOSE_MS}ms ease-in`;
    // Close — slide lids to meet at y=120 (center of eye)
    eye.lidTop.setAttribute('transform', 'translate(0 60)');   // lid rect was at y=60, shifts down 60 → covers eye top half
    eye.lidBot.setAttribute('transform', 'translate(0 -60)');  // lid rect was at y=120, shifts up 60 → covers eye bottom half

    setTimeout(() => {
      // Open — slide lids back out
      eye.lidTop.style.transition = `transform ${BLINK_OPEN_MS}ms ease-out`;
      eye.lidBot.style.transition = `transform ${BLINK_OPEN_MS}ms ease-out`;
      eye.lidTop.setAttribute('transform', 'translate(0 -60)');
      eye.lidBot.setAttribute('transform', 'translate(0  60)');
      setTimeout(() => {
        eye.isBlinking = false;
        if (onDone) onDone();
      }, BLINK_OPEN_MS);
    }, BLINK_CLOSE_MS + BLINK_HOLD_MS);
  }

  function scheduleNextBlink(eye) {
    setTimeout(() => {
      blink(eye, () => {
        // Double-blink chance
        if (Math.random() < DOUBLE_BLINK_PROB) {
          setTimeout(() => blink(eye, () => scheduleNextBlink(eye)), 140);
        } else {
          scheduleNextBlink(eye);
        }
      });
    }, nextBlinkDelay());
  }

  // ── Input handlers ──────────────────────────────────────────────────────
  document.addEventListener('mousemove', e => {
    lastInput = Date.now();
    look(e.clientX, e.clientY);
  }, {passive: true});

  document.addEventListener('touchmove', e => {
    if (!e.touches[0]) return;
    lastInput = Date.now();
    look(e.touches[0].clientX, e.touches[0].clientY);
  }, {passive: true});

  document.addEventListener('touchstart', e => {
    if (!e.touches[0]) return;
    lastInput = Date.now();
    look(e.touches[0].clientX, e.touches[0].clientY);
  }, {passive: true});

  // ── Saccades ───────────────────────────────────────────────────────────
  setInterval(() => {
    if (Date.now() - lastInput < CURSOR_IDLE_MS) return;
    if (!eyes.length) return;
    const angle = Math.random() * Math.PI * 2;
    const r = eyes[0].wrapper.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    const cy = r.top  + r.height / 2;
    const mag = 80 + Math.random() * 200;
    look(cx + Math.cos(angle) * mag, cy + Math.sin(angle) * mag);
    // 30% of saccades trigger a small blink (real eyes do this)
    if (Math.random() < SACCADE_BLINK_PROB) {
      eyes.forEach(eye => blink(eye));
    }
  }, SACCADE_INTERVAL_MS);

  // ── Init ────────────────────────────────────────────────────────────────
  function init() {
    document.querySelectorAll('.murphy-logo-live').forEach(registerEye);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  new MutationObserver(muts => {
    for (const m of muts) for (const n of m.addedNodes) {
      if (n.nodeType === 1) {
        if (n.classList && n.classList.contains('murphy-logo-live')) registerEye(n);
        n.querySelectorAll && n.querySelectorAll('.murphy-logo-live').forEach(registerEye);
      }
    }
  }).observe(document.body, {childList: true, subtree: true});

  window.MurphyGaze = { registerEye, look, blink: (i) => blink(eyes[i || 0]) };
})();
