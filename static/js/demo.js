/* KEYSTROKE QUEST - demo.js
 * 45-second automatic map cinematic. No Enter. SKIP or Escape only.
 */
(function () {
  'use strict';

  var WORLD_MS = 5000;
  var FINALE_AT = WORLD_MS * 5;
  var EXPLODE_AT = FINALE_AT + 6000;
  var TOTAL = EXPLODE_AT + 1800;
  var SCENES = [
    { at: 0, until: WORLD_MS, scene: 'world', focus: 'dojo', caption: 'World 1: The Home Row Dojo. Boss: Sensei Semicolon.' },
    { at: WORLD_MS, until: WORLD_MS * 2, scene: 'world', focus: 'tower', caption: 'World 2: Skyreach Tower. Boss: The Q-Bit.' },
    { at: WORLD_MS * 2, until: WORLD_MS * 3, scene: 'world', focus: 'undergrid', caption: 'World 3: The Undergrid. Boss: Z-Wraith.' },
    { at: WORLD_MS * 3, until: WORLD_MS * 4, scene: 'world', focus: 'citadel', caption: 'World 4: Shift Citadel. Boss: Lord Shift.' },
    { at: WORLD_MS * 4, until: FINALE_AT, scene: 'world', focus: 'harbor', caption: 'World 5: Glyph Harbor. Boss: The Null Pointer.' },
    { at: FINALE_AT, until: TOTAL, scene: 'finale', caption: 'Every boss. One last stand. Then it is your turn.' }
  ];

  var running = false;
  var startedAt = 0;
  var raf = 0;
  var sceneKey = '';
  var captionTimer = null;
  var skipBound = false;
  var exploded = false;

  function $(id) {
    try {
      return document.getElementById(id);
    } catch (e) {
      return null;
    }
  }

  function audio(name) {
    try {
      if (window.KQAudio && typeof window.KQAudio[name] === 'function') {
        return window.KQAudio[name].apply(
          window.KQAudio,
          Array.prototype.slice.call(arguments, 1)
        );
      }
    } catch (e) {}
  }

  function show(el) {
    if (!el) return;
    try { el.removeAttribute('hidden'); } catch (e) {}
  }

  function hide(el) {
    if (!el) return;
    try { el.setAttribute('hidden', ''); } catch (e) {}
  }

  function setCaption(text) {
    var el = $('kq-demo-caption');
    if (!el) return;
    if (captionTimer) {
      clearInterval(captionTimer);
      captionTimer = null;
    }
    var full = String(text || '');
    var i = 0;
    el.textContent = '';
    captionTimer = setInterval(function () {
      i += 1;
      el.textContent = full.slice(0, i);
      if (i % 3 === 0) audio('blip');
      if (i >= full.length) {
        clearInterval(captionTimer);
        captionTimer = null;
      }
    }, 28);
  }

  function setScene(spec) {
    var root = $('kq-demo');
    if (!root) return;
    root.setAttribute('data-scene', spec.scene);
    if (spec.focus) root.setAttribute('data-focus', spec.focus);
    else root.removeAttribute('data-focus');

    var finale = $('kq-demo-finale');
    if (finale) {
      if (spec.scene === 'finale') show(finale);
      else hide(finale);
    }

    setCaption(spec.caption);

    if (spec.scene === 'world') {
      audio('hit');
      clearLit();
      lightWorld(spec.focus, 0);
      try {
        var band = document.querySelector('#kq-demo-map .kq-demo-world[data-theme="' + spec.focus + '"]');
        if (band && band.scrollIntoView) band.scrollIntoView({ block: 'center', behavior: 'smooth' });
      } catch (e) {}
    }
    if (spec.scene === 'finale') {
      exploded = false;
      audio('levelUp');
    }
  }

  function sceneId(spec) {
    return spec.scene + ':' + (spec.focus || '');
  }

  function clearLit() {
    var lit = document.querySelectorAll('#kq-demo-map .kq-node--lit');
    for (var i = 0; i < lit.length; i++) lit[i].classList.remove('kq-node--lit');
  }

  function lightWorld(theme, count) {
    var band = document.querySelector('#kq-demo-map .kq-demo-world[data-theme="' + theme + '"]');
    if (!band) return;
    var nodes = band.querySelectorAll('.kq-node');
    for (var i = 0; i < nodes.length; i++) {
      if (i < count) nodes[i].classList.add('kq-node--lit');
      else nodes[i].classList.remove('kq-node--lit');
    }
  }

  function explodeBosses() {
    if (exploded) return;
    exploded = true;
    var bosses = document.querySelectorAll('#kq-demo-finale .kq-demo-villain');
    var screen = $('kq-screen');
    for (var i = 0; i < bosses.length; i++) {
      bosses[i].classList.add('kq-demo-boss--boom');
    }
    if (screen) {
      screen.classList.add('kq-shake');
      window.setTimeout(function () {
        try { screen.classList.remove('kq-shake'); } catch (e) {}
      }, 800);
    }
    audio('hit');
    audio('combo', 80);
  }

  function currentScene(elapsed) {
    var found = SCENES[0];
    for (var i = 0; i < SCENES.length; i++) {
      if (elapsed >= SCENES[i].at) found = SCENES[i];
    }
    return found;
  }

  function tick() {
    if (!running) return;
    var elapsed = Date.now() - startedAt;
    if (elapsed >= TOTAL) {
      explodeBosses();
      window.setTimeout(stop, 900);
      return;
    }

    var spec = currentScene(elapsed);
    var id = sceneId(spec);
    if (id !== sceneKey) {
      sceneKey = id;
      setScene(spec);
    }

    if (spec.scene === 'world') {
      var local = (elapsed - spec.at) / Math.max(1, spec.until - spec.at);
      lightWorld(spec.focus, Math.min(6, 1 + Math.floor(local * 6)));
    }
    if (spec.scene === 'finale' && elapsed >= EXPLODE_AT) explodeBosses();

    var all = $('kq-demo-progress-all');
    var sceneBar = $('kq-demo-progress-scene');
    if (all) all.style.width = Math.min(100, (elapsed / TOTAL) * 100) + '%';
    if (sceneBar) {
      var span = spec.until - spec.at;
      sceneBar.style.width = Math.min(100, ((elapsed - spec.at) / span) * 100) + '%';
    }

    raf = window.requestAnimationFrame(tick);
  }

  function bindSkip() {
    if (skipBound) return;
    skipBound = true;
    var btn = $('kq-demo-skip');
    if (btn) btn.addEventListener('click', function (ev) {
      try { ev.preventDefault(); } catch (e) {}
      stop();
    });
    document.addEventListener('keydown', function (ev) {
      if (!running) return;
      if (ev.key === 'Escape') {
        try { ev.preventDefault(); } catch (e) {}
        stop();
        return;
      }
      if (ev.key === 'Enter' || ev.key === ' ' || ev.code === 'Space') {
        try { ev.preventDefault(); ev.stopPropagation(); } catch (e) {}
      }
    }, true);
  }

  function stop() {
    running = false;
    if (raf) {
      try { window.cancelAnimationFrame(raf); } catch (e) {}
      raf = 0;
    }
    if (captionTimer) {
      clearInterval(captionTimer);
      captionTimer = null;
    }
    hide($('kq-demo'));
    var root = $('kq-demo');
    if (root) {
      root.setAttribute('data-scene', 'world');
      root.setAttribute('data-focus', 'dojo');
    }
    clearLit();
    var bosses = document.querySelectorAll('.kq-demo-boss--boom');
    for (var i = 0; i < bosses.length; i++) bosses[i].classList.remove('kq-demo-boss--boom');
    audio('restoreUserTheme');
    audio('bgmStart');
    var start = $('kq-start-btn');
    if (start) {
      try { start.focus(); } catch (e) {}
    }
  }

  function play() {
    if (running) return;
    running = true;
    exploded = false;
    sceneKey = '';
    startedAt = Date.now();
    bindSkip();
    audio('setTheme', 'battle', false);
    audio('setEnabled', true);
    audio('bgmStart');
    show($('kq-demo'));
    var all = $('kq-demo-progress-all');
    var sceneBar = $('kq-demo-progress-scene');
    if (all) all.style.width = '0';
    if (sceneBar) sceneBar.style.width = '0';
    raf = window.requestAnimationFrame(tick);
  }

  window.KQDemo = { play: play, stop: stop };
})();
