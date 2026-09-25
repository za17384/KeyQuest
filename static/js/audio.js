/* KEYSTROKE QUEST - audio.js
 * window.KQAudio : runtime-synthesised chiptune SFX (no audio files).
 * Defensive by design: nothing in here may ever throw into the typing loop.
 */
(function () {
  'use strict';

  var Ctx = window.AudioContext || window.webkitAudioContext || null;
  var STORE_KEY = 'kq.sound';

  var ctx = null;
  var master = null;
  var enabled = false;
  var gestureBound = false;
  var bgmGain = null;
  var bgmPlaying = false;
  var bgmTimer = null;
  var bgmStep = 0;
  var bgmNextTime = 0;

  /* ---------------------------------------------------------------- utils */

  function storedPreference() {
    try {
      var v = window.localStorage.getItem(STORE_KEY);
      if (v === 'true') return true;
      if (v === 'false') return false;
    } catch (e) {
      /* private mode / disabled storage */
    }
    var s = window.KQ_SETTINGS;
    if (s && typeof s.sound === 'boolean') return s.sound;
    return false; // default MUTED
  }

  function persist(value) {
    try {
      window.localStorage.setItem(STORE_KEY, value ? 'true' : 'false');
    } catch (e) {}
    try {
      if (!window.KQ_SETTINGS || typeof window.KQ_SETTINGS !== 'object') {
        window.KQ_SETTINGS = {};
      }
      window.KQ_SETTINGS.sound = value;
      var body = {
        sound: value,
        scanlines: window.KQ_SETTINGS.scanlines !== false,
        reduced_motion: !!window.KQ_SETTINGS.reduced_motion
      };
      if (window.fetch) {
        window.fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body)
        })['catch'](function () {});
      }
    } catch (e) {}
  }

  function ensureCtx() {
    if (!Ctx) return null;
    try {
      if (!ctx) {
        ctx = new Ctx();
        master = ctx.createGain();
        master.gain.value = 0.5;
        master.connect(ctx.destination);
        bgmGain = ctx.createGain();
        bgmGain.gain.value = 0.16;
        bgmGain.connect(master);
      }
      if (ctx && !bgmGain) {
        try {
          bgmGain = ctx.createGain();
          bgmGain.gain.value = 0.16;
          bgmGain.connect(master);
        } catch (e) {}
      }
      if (ctx.state === 'suspended' && ctx.resume) {
        var p = ctx.resume();
        if (p && typeof p['catch'] === 'function') p['catch'](function () {});
      }
    } catch (e) {
      ctx = null;
      master = null;
    }
    return ctx;
  }

  function bindGesture() {
    if (gestureBound || !document) return;
    gestureBound = true;
    var wake = function () {
      ensureCtx();
      if (enabled) startBgm();
    };
    try {
      document.addEventListener('pointerdown', wake, { passive: true });
      document.addEventListener('mousedown', wake, { passive: true });
      document.addEventListener('touchstart', wake, { passive: true });
      document.addEventListener('keydown', wake);
    } catch (e) {}
  }

  /* --------------------------------------------------------------- engine */

  // One oscillator + gain envelope. Everything else is built from this.
  function tone(opts) {
    var c = ensureCtx();
    if (!c || !master) return;
    try {
      var now = c.currentTime;
      var t0 = now + (opts.delay || 0);
      var dur = Math.max(0.01, opts.dur || 0.08);
      var vol = Math.max(0.0005, opts.vol == null ? 0.12 : opts.vol);
      var from = Math.max(20, opts.freq || 440);
      var to = Math.max(20, opts.to || from);

      var osc = c.createOscillator();
      var gain = c.createGain();
      osc.type = opts.type || 'square';
      osc.frequency.setValueAtTime(from, t0);
      if (to !== from) osc.frequency.exponentialRampToValueAtTime(to, t0 + dur);

      var attack = Math.min(opts.attack == null ? 0.006 : opts.attack, dur * 0.5);
      gain.gain.setValueAtTime(0.0005, t0);
      gain.gain.exponentialRampToValueAtTime(vol, t0 + attack);
      gain.gain.exponentialRampToValueAtTime(0.0005, t0 + dur);

      osc.connect(gain);
      gain.connect(master);
      osc.start(t0);
      osc.stop(t0 + dur + 0.03);
      osc.onended = function () {
        try {
          gain.disconnect();
          osc.disconnect();
        } catch (e) {}
      };
    } catch (e) {}
  }

  // Wrap every public voice so a WebAudio hiccup can never reach the caller.
  function voice(fn) {
    return function () {
      if (!enabled) return;
      try {
        fn.apply(null, arguments);
      } catch (e) {}
    };
  }

  /* --------------------------------------------------------------- voices */

  var key = voice(function () {
    // slight pitch jitter so a held burst of typing does not sound robotic
    var f = 1180 + Math.random() * 420;
    tone({ type: 'square', freq: f, to: f * 0.72, dur: 0.035, vol: 0.085, attack: 0.002 });
  });

  var error = voice(function () {
    tone({ type: 'square', freq: 150, to: 74, dur: 0.2, vol: 0.16, attack: 0.004 });
    tone({ type: 'triangle', freq: 96, to: 60, dur: 0.22, vol: 0.12, delay: 0.01 });
  });

  var combo = voice(function (n) {
    var tier = Math.max(1, Math.min(8, Math.floor((Number(n) || 10) / 10)));
    var base = 480 + tier * 70;
    tone({ type: 'square', freq: base, to: base * 1.6, dur: 0.11, vol: 0.13 });
    tone({ type: 'triangle', freq: base * 1.5, to: base * 2.2, dur: 0.09, vol: 0.07, delay: 0.05 });
  });

  var hit = voice(function () {
    tone({ type: 'triangle', freq: 220, to: 52, dur: 0.17, vol: 0.2, attack: 0.003 });
    tone({ type: 'square', freq: 110, to: 44, dur: 0.12, vol: 0.09 });
  });

  var levelUp = voice(function () {
    var notes = [523.25, 659.25, 783.99, 1046.5];
    for (var i = 0; i < notes.length; i++) {
      tone({
        type: 'square',
        freq: notes[i],
        dur: i === notes.length - 1 ? 0.22 : 0.1,
        vol: 0.12,
        delay: i * 0.095
      });
      tone({ type: 'triangle', freq: notes[i] / 2, dur: 0.12, vol: 0.06, delay: i * 0.095 });
    }
  });

  var blip = voice(function () {
    tone({ type: 'square', freq: 900 + Math.random() * 120, dur: 0.022, vol: 0.05, attack: 0.002 });
  });

  var start = voice(function () {
    var notes = [392, 523.25, 659.25, 783.99, 1046.5];
    for (var i = 0; i < notes.length; i++) {
      tone({
        type: 'square',
        freq: notes[i],
        dur: i === notes.length - 1 ? 0.3 : 0.08,
        vol: 0.13,
        delay: i * 0.075
      });
    }
    tone({ type: 'triangle', freq: 196, to: 392, dur: 0.4, vol: 0.09, delay: 0.3 });
  });

  /* --------------------------------------------------------------- bgm */

  // 16 eighth-notes: a looping 8-bit overworld in C
  var BGM_MELODY = [
    523.25, 659.25, 783.99, 659.25,
    880.0, 783.99, 659.25, 523.25,
    698.46, 880.0, 783.99, 659.25,
    587.33, 659.25, 523.25, 392.0
  ];
  var BGM_BASS = [
    130.81, 130.81, 196.0, 196.0,
    220.0, 220.0, 164.81, 164.81,
    174.61, 174.61, 130.81, 130.81,
    196.0, 196.0, 98.0, 130.81
  ];
  var BGM_STEP = 0.22;

  function bgmTone(type, freq, t0, dur, vol) {
    var c = ctx;
    if (!c || !bgmGain || !freq) return;
    try {
      var osc = c.createOscillator();
      var gain = c.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(freq, t0);
      gain.gain.setValueAtTime(0.0005, t0);
      gain.gain.exponentialRampToValueAtTime(vol, t0 + 0.012);
      gain.gain.exponentialRampToValueAtTime(0.0005, t0 + dur);
      osc.connect(gain);
      gain.connect(bgmGain);
      osc.start(t0);
      osc.stop(t0 + dur + 0.02);
      osc.onended = function () {
        try {
          gain.disconnect();
          osc.disconnect();
        } catch (e) {}
      };
    } catch (e) {}
  }

  function scheduleBgm() {
    var c = ensureCtx();
    if (!c || !enabled || !bgmPlaying) return;
    try {
      if (bgmNextTime < c.currentTime + 0.05) bgmNextTime = c.currentTime + 0.05;
      while (bgmNextTime < c.currentTime + 1.1) {
        var i = bgmStep % BGM_MELODY.length;
        var t0 = bgmNextTime;
        var dur = BGM_STEP * 0.86;
        bgmTone('square', BGM_MELODY[i], t0, dur, 0.09);
        bgmTone('triangle', BGM_BASS[i], t0, BGM_STEP * 0.96, 0.14);
        if (i % 2 === 0) {
          bgmTone('square', 1600, t0, 0.03, 0.025);
        }
        bgmStep += 1;
        bgmNextTime += BGM_STEP;
      }
    } catch (e) {}
  }

  function startBgm() {
    if (!enabled || bgmPlaying) return;
    var c = ensureCtx();
    if (!c) return;
    bgmPlaying = true;
    bgmStep = 0;
    bgmNextTime = c.currentTime + 0.08;
    scheduleBgm();
    try {
      if (bgmTimer) clearInterval(bgmTimer);
      bgmTimer = setInterval(scheduleBgm, 180);
    } catch (e) {}
  }

  function stopBgm() {
    bgmPlaying = false;
    try {
      if (bgmTimer) clearInterval(bgmTimer);
    } catch (e) {}
    bgmTimer = null;
  }

  /* --------------------------------------------------------------- toggle */

  function toggleEl() {
    try {
      return document.getElementById('kq-sound-toggle');
    } catch (e) {
      return null;
    }
  }

  function paintToggle() {
    var el = toggleEl();
    if (!el) return;
    try {
      el.setAttribute('data-on', enabled ? 'true' : 'false');
      el.textContent = enabled ? 'SOUND: ON' : 'SOUND: OFF';
      el.setAttribute('aria-pressed', enabled ? 'true' : 'false');
    } catch (e) {}
  }

  function setEnabled(value) {
    enabled = !!value;
    persist(enabled);
    paintToggle();
    if (enabled) {
      ensureCtx();
      blip();
      startBgm();
    } else {
      stopBgm();
    }
    return enabled;
  }

  function bindToggle() {
    var el = toggleEl();
    if (!el || el.getAttribute('data-kq-bound') === 'true') {
      paintToggle();
      return;
    }
    el.setAttribute('data-kq-bound', 'true');
    el.addEventListener('click', function (ev) {
      try {
        ev.preventDefault();
      } catch (e) {}
      setEnabled(!enabled);
    });
    paintToggle();
  }

  function init() {
    try {
      enabled = storedPreference();
      bindGesture();
      bindToggle();
      try {
        document.addEventListener('visibilitychange', function () {
          if (document.hidden) stopBgm();
          else if (enabled) startBgm();
        });
      } catch (e) {}
      if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bindToggle);
      }
    } catch (e) {}
    return enabled;
  }

  window.KQAudio = {
    init: init,
    setEnabled: setEnabled,
    isEnabled: function () {
      return enabled;
    },
    key: key,
    error: error,
    combo: combo,
    hit: hit,
    levelUp: levelUp,
    blip: blip,
    start: start,
    bgmStart: startBgm,
    bgmStop: stopBgm
  };

  init();
})();
