/* KEYSTROKE QUEST - game.js
 * window.KQGame : stage orchestration. Loads the stage payload, runs the
 * dialogue, drives the TypingEngine and layers the RPG rules on top
 * (hearts, combo, floating damage, boss fights, results, XP).
 */
(function () {
  'use strict';

  var HP_NORMAL = 5;
  var HP_BOSS = 3;
  var FX_EVERY = 4;           // floating numbers: roughly 1 keystroke in 4
  var THUD_EVERY = 5;         // boss damage thud throttle
  var TAUNT_EVERY = 40;       // correct chars between boss taunts
  var TAUNT_MS = 4200;
  var SHAKE_MS = 200;
  var POPUP_MS = 900;

  var run = newRun();

  function newRun() {
    return {
      stageId: 0,
      data: null,
      isBoss: false,
      engine: null,
      hp: HP_NORMAL,
      hpMax: HP_NORMAL,
      combo: 0,
      comboMax: 0,
      correctTotal: 0,
      sinceTaunt: 0,
      fxTick: 0,
      thudTick: 0,
      bossMax: 100,
      bossHp: 100,
      dmgPerChar: 1,
      ended: false,
      booted: false,
      levelBefore: null,
      nextStageId: null,
      tabArmed: false,
      timers: { shake: null, popup: null, taunt: null, tab: null }
    };
  }

  /* ----------------------------------------------------------------- dom */

  function $(id) {
    try {
      return document.getElementById(id);
    } catch (e) {
      return null;
    }
  }

  function setText(id, value) {
    var el = $(id);
    if (el) el.textContent = String(value);
    return el;
  }

  function show(el) {
    if (!el) return;
    try {
      el.removeAttribute('hidden');
    } catch (e) {}
  }

  function hide(el) {
    if (!el) return;
    try {
      el.setAttribute('hidden', '');
    } catch (e) {}
  }

  function audio(name, arg) {
    try {
      if (window.KQAudio && typeof window.KQAudio[name] === 'function') {
        window.KQAudio[name](arg);
      }
    } catch (e) {}
  }

  function keys(fn, a, b) {
    try {
      if (window.KQKeyboard && typeof window.KQKeyboard[fn] === 'function') {
        window.KQKeyboard[fn](a, b);
      }
    } catch (e) {}
  }

  function dialogueOpen() {
    try {
      return !!(window.KQDialogue && window.KQDialogue.isOpen());
    } catch (e) {
      return false;
    }
  }

  function playDialogue(lines) {
    try {
      if (window.KQDialogue && window.KQDialogue.play) return window.KQDialogue.play(lines);
    } catch (e) {}
    return Promise.resolve();
  }

  function reduced() {
    try {
      if (window.KQ_SETTINGS && window.KQ_SETTINGS.reduced_motion) return true;
      return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
    } catch (e) {
      return false;
    }
  }

  function clearTimer(name) {
    if (run.timers[name]) {
      clearTimeout(run.timers[name]);
      run.timers[name] = null;
    }
  }

  /* ------------------------------------------------------- loading panel */

  function messageHost() {
    var panel = $('kq-loading');
    if (panel) return panel;
    // no loading panel in the template: build a minimal banner so errors are visible
    var host = document.getElementById('kq-fallback-msg');
    if (host) return host;
    try {
      host = document.createElement('div');
      host.id = 'kq-fallback-msg';
      host.className = 'kq-panel';
      var parent = $('kq-screen') || document.body;
      if (!parent) return null;
      parent.appendChild(host);
      return host;
    } catch (e) {
      return null;
    }
  }

  function panelText(host, message) {
    if (!host) return;
    try {
      var slot = host.querySelector('.kq-loading-msg');
      if (!slot) {
        slot = host.ownerDocument.createElement('p');
        slot.className = 'kq-loading-msg';
        host.appendChild(slot);
      }
      slot.textContent = String(message);
    } catch (e) {}
  }

  function showLoading(message) {
    var host = messageHost();
    show(host);
    if (message) panelText(host, message);
  }

  function hideLoading() {
    var panel = $('kq-loading');
    hide(panel);
    var fallback = document.getElementById('kq-fallback-msg');
    hide(fallback);
  }

  // Shows a readable failure inside the loading panel with a retry button.
  function askRetry(message) {
    return new Promise(function (resolve) {
      var host = messageHost();
      show(host);
      panelText(host, message);
      var button = null;
      try {
        button = host && host.querySelector('.kq-loading-retry');
        if (!button && host) {
          button = host.ownerDocument.createElement('button');
          button.type = 'button';
          button.className = 'kq-btn kq-btn--primary kq-loading-retry';
          button.textContent = 'RETRY';
          host.appendChild(button);
        }
      } catch (e) {
        button = null;
      }
      if (!button) {
        setTimeout(resolve, 4000); // last resort: retry on a timer
        return;
      }
      show(button);
      var onClick = function () {
        button.removeEventListener('click', onClick);
        hide(button);
        resolve();
      };
      button.addEventListener('click', onClick);
      try {
        button.focus();
      } catch (e) {}
    });
  }

  function fatal(err) {
    var message = err && err.message ? err.message : String(err || 'unknown error');
    var host = messageHost();
    show(host);
    panelText(host, 'SOMETHING BROKE: ' + message);
    try {
      console.error('[KQGame]', err);
    } catch (e) {}
  }

  /* ---------------------------------------------------------------- data */

  function fetchJSON(url, options) {
    if (!window.fetch) return Promise.reject(new Error('This browser has no fetch()'));
    return window.fetch(url, options).then(function (res) {
      if (!res.ok) throw new Error('server returned ' + res.status);
      return res.json();
    });
  }

  function fetchStage(stageId) {
    return fetchJSON('/api/stage/' + stageId, {
      headers: { Accept: 'application/json' },
      credentials: 'same-origin'
    }).then(function (data) {
      if (!data || !Array.isArray(data.lines) || data.lines.length === 0) {
        throw new Error('the stage came back with no practice text');
      }
      return data;
    });
  }

  async function loadStage(stageId) {
    for (var attempt = 0; attempt < 24; attempt++) {
      try {
        return await fetchStage(stageId);
      } catch (err) {
        var why = err && err.message ? err.message : 'unknown error';
        await askRetry('COULD NOT LOAD STAGE ' + stageId + ' (' + why + '). Press RETRY.');
        showLoading('GENERATING...');
      }
    }
    throw new Error('gave up loading stage ' + stageId);
  }

  function loadLevel() {
    return fetchJSON('/api/progress')
      .then(function (data) {
        var player = data && data.player;
        run.levelBefore = player && typeof player.level === 'number' ? player.level : null;
      })
      ['catch'](function () {
        run.levelBefore = null;
      });
  }

  /* ---------------------------------------------------------------- HUD */

  function renderHearts() {
    var host = $('kq-hp');
    if (!host) return;
    try {
      host.innerHTML = '';
      var doc = host.ownerDocument || document;
      for (var i = 0; i < run.hpMax; i++) {
        var heart = doc.createElement('span');
        heart.className = 'kq-heart';
        heart.setAttribute('data-full', i < run.hp ? 'true' : 'false');
        host.appendChild(heart);
      }
    } catch (e) {}
  }

  function setCombo(value) {
    setText('kq-combo', value);
  }

  function formatTime(ms) {
    var total = Math.max(0, Math.floor((ms || 0) / 1000));
    var mm = Math.floor(total / 60);
    var ss = total % 60;
    return (mm < 10 ? '0' : '') + mm + ':' + (ss < 10 ? '0' : '') + ss;
  }

  function shake() {
    if (reduced()) return;
    var screen = $('kq-screen');
    if (!screen) return;
    try {
      screen.classList.add('kq-shake');
    } catch (e) {}
    clearTimer('shake');
    run.timers.shake = setTimeout(function () {
      run.timers.shake = null;
      try {
        screen.classList.remove('kq-shake');
      } catch (e) {}
    }, SHAKE_MS);
  }

  function comboPopup(value) {
    var pop = $('kq-combo-popup');
    if (pop) {
      try {
        pop.textContent = 'x' + value + ' COMBO!';
        pop.removeAttribute('hidden');
        pop.classList.add('kq-combo-popup--show');
      } catch (e) {}
      clearTimer('popup');
      run.timers.popup = setTimeout(function () {
        run.timers.popup = null;
        try {
          pop.classList.remove('kq-combo-popup--show');
          pop.setAttribute('hidden', '');
        } catch (e) {}
      }, POPUP_MS);
    }
    audio('combo', value);
    shake();
  }

  function floatNumber(amount) {
    if (reduced()) return;
    var layer = $('kq-fx');
    if (!layer) return;
    try {
      var doc = layer.ownerDocument || document;
      var rect = layer.getBoundingClientRect();
      var pos = run.engine && run.engine.getCaretPos ? run.engine.getCaretPos() : null;
      var x = pos ? pos.clientX - rect.left : rect.width / 2;
      var y = pos ? pos.clientY - rect.top : rect.height / 2;

      var node = doc.createElement('span');
      node.className = 'kq-float';
      node.textContent = '+' + amount;
      node.style.position = 'absolute';
      node.style.left = Math.round(x) + 'px';
      node.style.top = Math.round(y) + 'px';
      node.style.pointerEvents = 'none';
      node.style.transform = 'translate(-50%, 0)';
      node.style.opacity = '1';
      node.style.transition = 'transform 520ms ease-out, opacity 520ms ease-out';
      layer.appendChild(node);

      var lift = function () {
        try {
          node.style.transform = 'translate(-50%, -38px)';
          node.style.opacity = '0';
        } catch (e) {}
      };
      if (window.requestAnimationFrame) requestAnimationFrame(lift);
      else setTimeout(lift, 16);

      setTimeout(function () {
        try {
          if (node.parentNode) node.parentNode.removeChild(node);
        } catch (e) {}
      }, 620);
    } catch (e) {}
  }

  /* ---------------------------------------------------------------- boss */

  function setupBoss() {
    var world = (run.data && run.data.world) || {};
    if (!run.isBoss) return;
    run.bossMax = Math.max(1, Number(world.boss_hp) || 100);
    run.bossHp = run.bossMax;
    setText('kq-boss-name', world.boss_name || 'BOSS');
    var sprite = $('kq-boss-sprite');
    if (sprite && world.theme && !sprite.getAttribute('data-boss-theme')) {
      try {
        sprite.setAttribute('data-boss-theme', world.theme);
      } catch (e) {}
    }
    var say = $('kq-boss-say');
    if (say) say.textContent = '';
    paintBossHp();
  }

  function paintBossHp() {
    var fill = $('kq-boss-hp-fill');
    if (!fill) return;
    var pct = Math.max(0, Math.min(100, (run.bossHp / run.bossMax) * 100));
    try {
      fill.style.width = pct.toFixed(1) + '%';
      fill.setAttribute('data-pct', String(Math.round(pct)));
    } catch (e) {}
  }

  function bossPct() {
    return Math.round(Math.max(0, Math.min(100, (run.bossHp / run.bossMax) * 100)));
  }

  function bossHit(damage) {
    run.bossHp = Math.max(0, run.bossHp - damage);
    paintBossHp();
    run.thudTick = (run.thudTick + 1) % THUD_EVERY;
    if (run.thudTick === 0) audio('hit');
    if (run.bossHp <= 0) {
      endRun(true, null); // boss down before the text ran out
      return true;
    }
    return false;
  }

  function bossHeal(amount) {
    run.bossHp = Math.min(run.bossMax, run.bossHp + amount);
    paintBossHp();
  }

  function maybeTaunt() {
    if (!run.isBoss) return;
    run.sinceTaunt += 1;
    if (run.sinceTaunt < TAUNT_EVERY) return;
    run.sinceTaunt = 0;
    var body = JSON.stringify({
      stage_id: run.stageId,
      context: { combo: run.combo, boss_hp_pct: bossPct() }
    });
    fetchJSON('/api/boss-line', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: body
    })
      .then(function (data) {
        var line = data && data.line;
        var say = $('kq-boss-say');
        if (!line || !say || run.ended) return;
        say.textContent = String(line);
        show(say);
        clearTimer('taunt');
        run.timers.taunt = setTimeout(function () {
          run.timers.taunt = null;
          try {
            say.textContent = '';
          } catch (e) {}
        }, TAUNT_MS);
      })
      ['catch'](function () {});
  }

  /* ----------------------------------------------------------- the run */

  function startRun() {
    var data = run.data;
    if (!data) return;

    run.isBoss = isBossStage(data);
    run.hpMax = run.isBoss ? HP_BOSS : HP_NORMAL;
    run.hp = run.hpMax;
    run.combo = 0;
    run.comboMax = 0;
    run.correctTotal = 0;
    run.sinceTaunt = 0;
    run.fxTick = 0;
    run.thudTick = 0;
    run.ended = false;

    clearTimer('shake');
    clearTimer('popup');
    clearTimer('taunt');
    hide($('kq-results'));
    renderHearts();
    setCombo(0);
    setText('kq-wpm', 0);
    setText('kq-accuracy', '100%');
    setText('kq-timer', formatTime(0));
    keys('reset');
    setupBoss();

    var fx = $('kq-fx');
    if (fx) {
      try {
        fx.innerHTML = '';
      } catch (e) {}
    }

    if (run.engine) {
      try {
        run.engine.destroy();
      } catch (e) {}
      run.engine = null;
    }

    run.engine = new window.TypingEngine({
      textEl: $('kq-text'),
      caretEl: $('kq-caret'),
      inputEl: $('kq-input'),
      lines: data.lines,
      onKey: onKey,
      onProgress: onProgress,
      onComplete: onComplete
    });

    var total = Math.max(1, run.engine.chars.length);
    // a clean run should drop the boss just before the text runs out
    run.dmgPerChar = run.isBoss ? run.bossMax / (total * 0.9) : 0;

    run.engine.start();
    keys('highlight', run.engine.expectedChar());
    audio('start');
  }

  function isBossStage(data) {
    if (data && data.stage && typeof data.stage.is_boss !== 'undefined') return !!data.stage.is_boss;
    var stageEl = $('kq-stage');
    return !!(stageEl && stageEl.getAttribute('data-is-boss') === 'true');
  }

  function onKey(info) {
    if (run.ended) return;
    try {
      keys('flash', info.correct ? info.expected : info.typed, info.correct);

      if (info.correct) {
        audio('key');
        run.combo += 1;
        run.correctTotal += 1;
        if (run.combo > run.comboMax) run.comboMax = run.combo;
        setCombo(run.combo);

        run.fxTick = (run.fxTick + 1) % FX_EVERY;
        if (run.fxTick === 0) floatNumber(1 + Math.floor(run.combo / 10));

        if (run.combo > 0 && run.combo % 10 === 0) comboPopup(run.combo);

        if (run.isBoss) {
          if (bossHit(run.dmgPerChar)) return;
          maybeTaunt();
        }
      } else {
        audio('error');
        run.combo = 0;
        setCombo(0);
        shake();
        if (run.isBoss) bossHeal(run.dmgPerChar * 1.5);
        run.hp = Math.max(0, run.hp - 1);
        renderHearts();
        if (run.hp <= 0) {
          endRun(false, null);
          return;
        }
      }

      if (run.engine) keys('highlight', run.engine.expectedChar());
    } catch (e) {
      try {
        console.error('[KQGame] onKey', e);
      } catch (e2) {}
    }
  }

  function onProgress(p) {
    if (!p) return;
    setText('kq-wpm', Math.round(p.wpm || 0));
    setText('kq-accuracy', Math.round((p.accuracy == null ? 1 : p.accuracy) * 100) + '%');
    setText('kq-timer', formatTime(p.elapsedMs));
  }

  function onComplete(stats) {
    endRun(true, stats);
  }

  /* --------------------------------------------------------- end of run */

  async function endRun(won, stats) {
    if (run.ended) return;
    run.ended = true;
    try {
      var finalStats = stats;
      if (run.engine) {
        if (!finalStats) finalStats = run.engine.stop();
        run.engine.destroy();
      }
      finalStats = finalStats || {
        wpm: 0,
        rawWpm: 0,
        accuracy: 0,
        durationMs: 0,
        keystrokes: []
      };
      keys('reset');
      clearTimer('taunt');

      var result = await submitSession(finalStats);
      var passed = !!(won && result && result.passed);
      run.nextStageId = result && result.next_stage_id ? result.next_stage_id : null;

      if (result && result.player && typeof result.player.level === 'number') {
        if (run.levelBefore != null && result.player.level > run.levelBefore) {
          audio('levelUp');
        }
        run.levelBefore = result.player.level;
      }

      if (won) {
        var outro = run.data && run.data.dialogue ? run.data.dialogue.outro : null;
        await playDialogue(outro);
      }
      showResults(result, finalStats, won, passed);
    } catch (err) {
      fatal(err);
    }
  }

  function submitSession(stats) {
    var payload = {
      stage_id: run.stageId,
      wpm: stats.wpm || 0,
      raw_wpm: stats.rawWpm || 0,
      accuracy: stats.accuracy || 0,
      duration_ms: stats.durationMs || stats.elapsedMs || 0,
      combo_max: run.comboMax,
      hp_left: run.hp,
      keystrokes: Array.isArray(stats.keystrokes) ? stats.keystrokes : []
    };
    return fetchJSON('/api/session', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify(payload)
    })['catch'](function (err) {
      try {
        console.error('[KQGame] /api/session failed', err);
      } catch (e) {}
      return { passed: false, stars: 0, rank: '-', xp_gained: 0, player: null, next_stage_id: null, offline: true };
    });
  }

  function renderStars(count) {
    var host = $('kq-results-stars');
    if (!host) return;
    try {
      host.innerHTML = '';
      var doc = host.ownerDocument || document;
      for (var i = 0; i < 3; i++) {
        var star = doc.createElement('span');
        star.className = 'kq-star';
        var on = i < (count || 0);
        star.setAttribute('data-on', on ? 'true' : 'false');
        star.textContent = on ? '\u2605' : '\u2606';
        host.appendChild(star);
      }
    } catch (e) {}
  }

  function showResults(result, stats, won, passed) {
    var overlay = $('kq-results');
    var res = result || {};

    setText('kq-results-rank', won ? res.rank || '-' : 'F');
    setText('kq-results-wpm', Math.round(stats.wpm || 0));
    setText('kq-results-accuracy', Math.round((stats.accuracy || 0) * 100) + '%');
    setText('kq-results-combo', run.comboMax);
    setText('kq-results-xp', '+' + (res.xp_gained || 0) + ' XP');
    renderStars(won ? res.stars || 0 : 0);

    if (overlay) {
      try {
        overlay.setAttribute('data-passed', passed ? 'true' : 'false');
        overlay.setAttribute('data-outcome', won ? (passed ? 'clear' : 'try-again') : 'defeat');
      } catch (e) {}
    }

    var next = $('kq-results-next');
    if (next) {
      if (run.nextStageId) {
        show(next);
        try {
          next.setAttribute('data-stage-id', String(run.nextStageId));
        } catch (e) {}
      } else {
        hide(next);
      }
    }

    show(overlay);
    try {
      var focusTarget = run.nextStageId ? next : $('kq-results-retry');
      if (focusTarget && focusTarget.focus) focusTarget.focus();
    } catch (e) {}
  }

  /* --------------------------------------------------------------- wiring */

  function restart() {
    if (!run.data) return;
    hide($('kq-results'));
    startRun();
  }

  function go(url) {
    try {
      window.location.href = url;
    } catch (e) {}
  }

  function wireResults() {
    var retry = $('kq-results-retry');
    if (retry && retry.getAttribute('data-kq-bound') !== 'true') {
      retry.setAttribute('data-kq-bound', 'true');
      retry.addEventListener('click', function (ev) {
        ev.preventDefault();
        audio('blip');
        restart();
      });
    }
    var next = $('kq-results-next');
    if (next && next.getAttribute('data-kq-bound') !== 'true') {
      next.setAttribute('data-kq-bound', 'true');
      next.addEventListener('click', function (ev) {
        ev.preventDefault();
        audio('blip');
        if (run.nextStageId) go('/stage/' + run.nextStageId);
      });
    }
    var map = $('kq-results-map');
    if (map && map.getAttribute('data-kq-bound') !== 'true') {
      map.setAttribute('data-kq-bound', 'true');
      map.addEventListener('click', function (ev) {
        ev.preventDefault();
        audio('blip');
        go('/map');
      });
    }
  }

  function onShortcut(ev) {
    if (dialogueOpen()) return; // never hijack keys while the story box is up
    if (ev.ctrlKey || ev.metaKey || ev.altKey) return;

    if (ev.key === 'Escape') {
      ev.preventDefault();
      go('/map');
      return;
    }
    if (ev.key === 'Tab') {
      ev.preventDefault();
      run.tabArmed = true;
      clearTimer('tab');
      run.timers.tab = setTimeout(function () {
        run.timers.tab = null;
        run.tabArmed = false;
      }, 1500);
      return;
    }
    if (ev.key === 'Enter') {
      if (run.tabArmed) {
        ev.preventDefault();
        run.tabArmed = false;
        clearTimer('tab');
        restart();
      }
      return;
    }
    run.tabArmed = false;
  }

  function applySettings() {
    try {
      var settings = window.KQ_SETTINGS || {};
      var body = document.body;
      if (!body) return;
      if (settings.scanlines === false) body.classList.add('kq-no-scanlines');
      else body.classList.remove('kq-no-scanlines');
      if (reduced()) body.classList.add('kq-reduced-motion');
    } catch (e) {}
  }

  /* ----------------------------------------------------------------- boot */

  async function boot(config) {
    try {
      if (run.booted) return;
      run.booted = true;
      var stageEl = $('kq-stage');
      var fromDom = stageEl ? parseInt(stageEl.getAttribute('data-stage-id'), 10) : NaN;
      run.stageId = Number(config && config.stageId) || (isNaN(fromDom) ? 0 : fromDom);
      if (!run.stageId) throw new Error('no stage id was given to KQGame.boot');

      applySettings();
      wireResults();
      document.addEventListener('keydown', onShortcut);
      hide($('kq-results'));

      showLoading('GENERATING...');
      loadLevel();
      var data = await loadStage(run.stageId);
      run.data = data;
      run.isBoss = isBossStage(data);
      hideLoading();

      keys('mount', data.finger_map);
      setupBoss();

      var intro = data.dialogue ? data.dialogue.intro : null;
      await playDialogue(intro);

      startRun();
    } catch (err) {
      fatal(err);
    }
  }

  window.KQGame = {
    boot: boot,
    restart: restart,
    state: run
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', applySettings);
  } else {
    applySettings();
  }
})();
