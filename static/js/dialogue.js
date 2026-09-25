/* KEYSTROKE QUEST - dialogue.js
 * window.KQDialogue : the RPG text box. Classic JRPG advance rules -
 * first press completes the revealing line, second press moves on.
 */
(function () {
  'use strict';

  var CHAR_MS = 28;
  var SPACE_MS = 10;

  var state = {
    open: false,
    lines: [],
    index: 0,
    revealing: false,
    fullText: '',
    shown: 0,
    timer: null,
    resolve: null,
    bound: false,
    autoMs: 0,
    autoTimer: null
  };

  function el(id) {
    try {
      return document.getElementById(id);
    } catch (e) {
      return null;
    }
  }

  function root() {
    return el('kq-dialogue');
  }

  function blip() {
    try {
      if (window.KQAudio && window.KQAudio.blip) window.KQAudio.blip();
    } catch (e) {}
  }

  function clearTimer() {
    if (state.timer) {
      clearTimeout(state.timer);
      state.timer = null;
    }
  }

  function clearAuto() {
    if (state.autoTimer) {
      clearTimeout(state.autoTimer);
      state.autoTimer = null;
    }
  }

  function setNextVisible(visible) {
    var next = el('kq-dialogue-next');
    if (!next) return;
    try {
      if (visible) next.removeAttribute('hidden');
      else next.setAttribute('hidden', '');
      next.style.visibility = visible ? 'visible' : 'hidden';
    } catch (e) {}
  }

  /* -------------------------------------------------------------- reveal */

  function renderLine(line) {
    var portrait = el('kq-dialogue-portrait');
    var speaker = el('kq-dialogue-speaker');
    var text = el('kq-dialogue-text');

    if (portrait) {
      try {
        portrait.setAttribute('data-portrait', String((line && line.portrait) || 'narrator'));
      } catch (e) {}
    }
    if (speaker) speaker.textContent = String((line && line.speaker) || '');
    if (text) text.textContent = '';

    state.fullText = String((line && line.text) || '');
    state.shown = 0;
    state.revealing = true;
    setNextVisible(false);
    step();
  }

  function step() {
    clearTimer();
    var text = el('kq-dialogue-text');
    if (!state.revealing) return;
    if (state.shown >= state.fullText.length) {
      finishLine();
      return;
    }
    var ch = state.fullText.charAt(state.shown);
    state.shown += 1;
    if (text) text.textContent = state.fullText.slice(0, state.shown);
    if (state.shown % 3 === 0 && ch !== ' ') blip();
    state.timer = setTimeout(step, ch === ' ' ? SPACE_MS : CHAR_MS);
  }

  function finishLine() {
    clearTimer();
    state.revealing = false;
    var text = el('kq-dialogue-text');
    if (text) text.textContent = state.fullText;
    state.shown = state.fullText.length;
    setNextVisible(true);
    if (state.autoMs > 0) {
      var words = state.fullText.trim().split(/\s+/).filter(Boolean).length || 1;
      var wait = Math.max(400, words * state.autoMs);
      clearAuto();
      state.autoTimer = setTimeout(function () {
        advance();
      }, wait);
    }
  }

  /* ------------------------------------------------------------- advance */

  function advance() {
    if (!state.open) return;
    if (state.revealing) {
      finishLine(); // first press: complete the line, do not skip it
      return;
    }
    clearAuto();
    state.index += 1;
    if (state.index >= state.lines.length) {
      close();
      return;
    }
    renderLine(state.lines[state.index]);
  }

  function onKeyDown(ev) {
    if (!state.open) return;
    var k = ev.key;
    if (k === ' ' || k === 'Spacebar' || k === 'Enter' || ev.code === 'Space') {
      try {
        ev.preventDefault();
        ev.stopPropagation();
      } catch (e) {}
      advance();
    }
  }

  function onClick(ev) {
    if (!state.open) return;
    try {
      ev.preventDefault();
    } catch (e) {}
    advance();
  }

  function bind() {
    if (state.bound) return;
    state.bound = true;
    document.addEventListener('keydown', onKeyDown, true);
    var box = root();
    if (box) box.addEventListener('click', onClick);
  }

  function unbind() {
    if (!state.bound) return;
    state.bound = false;
    document.removeEventListener('keydown', onKeyDown, true);
    var box = root();
    if (box) box.removeEventListener('click', onClick);
  }

  function close() {
    clearTimer();
    clearAuto();
    unbind();
    state.open = false;
    state.revealing = false;
    state.lines = [];
    state.index = 0;
    var box = root();
    if (box) {
      try {
        box.setAttribute('hidden', '');
      } catch (e) {}
    }
    setNextVisible(false);
    var done = state.resolve;
    state.resolve = null;
    if (done) {
      try {
        done();
      } catch (e) {}
    }
  }

  /* -------------------------------------------------------------- public */

  function play(lines) {
    return new Promise(function (resolve) {
      var box = root();
      var list = Array.isArray(lines) ? lines.filter(Boolean) : [];
      if (!box || list.length === 0) {
        resolve(); // never deadlock the game on missing markup or empty dialogue
        return;
      }
      if (state.open) close(); // resolves any previous run first

      state.lines = list;
      state.index = 0;
      state.open = true;
      state.resolve = resolve;
      try {
        box.removeAttribute('hidden');
      } catch (e) {}
      bind();
      renderLine(state.lines[0]);
    });
  }

  function skip() {
    if (state.open) close();
  }

  function isOpen() {
    return !!state.open;
  }

  function setAutoAdvance(msPerWord) {
    state.autoMs = Math.max(0, Number(msPerWord) || 0);
    if (!state.autoMs) clearAuto();
  }

  function playOne(line) {
    return play(line ? [line] : []);
  }

  window.KQDialogue = {
    play: play,
    playOne: playOne,
    skip: skip,
    isOpen: isOpen,
    setAutoAdvance: setAutoAdvance
  };
})();
